use crate::gameplay::playing::PlayingState;
use crate::solver::solve;
use arrow::array::{ListArray, UInt32Array, UInt8Array};
use arrow::datatypes::{DataType, Field, Schema};
use arrow::record_batch::RecordBatch;
use indicatif::ParallelProgressIterator;
use parquet::arrow::ArrowWriter;
use parquet::file::properties::WriterProperties;
use rand::prelude::*;
use rayon::prelude::*;
use std::fs::File;
use std::sync::Arc;

use super::common::generate_random_hands;

// Phase 1 Output: Just the state snapshot
pub struct RawGameplayState {
    pub hands: [u32; 4], // ALL 4 hands
    pub board: Vec<u8>,
    pub history: u32,
    pub trump: u8,
    pub tricks_won: [u8; 2],
    pub player: u8,
}

// Phase 2 Output: The solved sample
pub struct SolvedGameplaySample {
    pub best_card: u8,
    pub best_score: i16,
    pub valid: bool, // If filtered out
}

pub fn generate_raw_gameplay_batch(
    batch_size: usize,
) -> (
    Vec<u32>,
    Vec<Vec<u8>>,
    Vec<u32>,
    Vec<u8>,
    Vec<Vec<u8>>,
    Vec<u8>,
) {
    // Returns: (flattened_hands, boards, history, trumps, tricks_won_pair, current_player)

    let states: Vec<RawGameplayState> = (0..batch_size)
        .into_par_iter()
        .progress_count(batch_size as u64)
        .map(|_| generate_single_raw_state())
        .collect();

    let mut hands_data = Vec::with_capacity(batch_size * 4);
    let mut boards_data = Vec::with_capacity(batch_size);
    let mut history_data = Vec::with_capacity(batch_size);
    let mut trumps_data = Vec::with_capacity(batch_size);
    let mut tricks_won_data = Vec::with_capacity(batch_size);
    let mut player_data = Vec::with_capacity(batch_size);

    for s in states {
        hands_data.extend_from_slice(&s.hands);
        boards_data.push(s.board);
        history_data.push(s.history);
        trumps_data.push(s.trump);
        tricks_won_data.push(s.tricks_won.to_vec());
        player_data.push(s.player);
    }

    (
        hands_data,
        boards_data,
        history_data,
        trumps_data,
        tricks_won_data,
        player_data,
    )
}

fn generate_single_raw_state() -> RawGameplayState {
    let mut rng = rand::thread_rng();

    // 1. Temporal Bias
    // 50% Endgame (Played 5-7 tricks -> 3-1 remaining)
    // 30% Midgame (Played 3-4 tricks -> 5-4 remaining)
    // 20% Opening (Played 0-2 tricks -> 8-6 remaining) - SLOW PART
    let r = rng.gen_range(0..100);
    let target_trick = if r < 50 {
        rng.gen_range(5..8)
    } else if r < 80 {
        rng.gen_range(3..5)
    } else {
        rng.gen_range(0..3)
    };

    let hands = generate_random_hands();
    let trump = rng.gen_range(0..4) as u8;

    let mut state = PlayingState::new(trump);
    state.hands = hands;
    let mut history_mask = 0u32;

    // Simulate to target trick
    for _ in 0..target_trick {
        for _ in 0..4 {
            let legal_moves = state.get_legal_moves();
            // Pick random legal move
            let mut moves = Vec::new();
            for i in 0..32 {
                if (legal_moves & (1 << i)) != 0 {
                    moves.push(i as u8);
                }
            }
            if moves.is_empty() {
                break;
            }
            let m = moves[rng.gen_range(0..moves.len())];
            state.play_card(m);
            history_mask |= 1 << m;
        }
    }

    // Simulate partial trick (0-3 cards)
    let partial = rng.gen_range(0..4);
    for _ in 0..partial {
        let legal_moves = state.get_legal_moves();
        let mut moves = Vec::new();
        for i in 0..32 {
            if (legal_moves & (1 << i)) != 0 {
                moves.push(i as u8);
            }
        }
        if moves.is_empty() {
            break;
        }
        let m = moves[rng.gen_range(0..moves.len())];
        state.play_card(m);
        history_mask |= 1 << m;
    }

    // Capture board snapshot
    let mut board = Vec::new();
    for i in 0..4 {
        if state.current_trick[i] != 0xFF {
            board.push(state.current_trick[i]);
        }
    }

    RawGameplayState {
        hands: state.hands,
        board,
        history: history_mask,
        trump: state.trump,
        tricks_won: state.tricks_won,
        player: state.current_player,
    }
}

pub fn solve_gameplay_batch(
    flattened_hands: Vec<u32>,
    boards: Vec<Vec<u8>>,
    history: Vec<u32>,
    trumps: Vec<u8>,
    tricks_won: Vec<Vec<u8>>,
    pimc_iterations: usize,
) -> (Vec<u8>, Vec<i16>, Vec<bool>) {
    // flattened_hands is size N*4.
    let num_samples = boards.len();

    let results: Vec<SolvedGameplaySample> = (0..num_samples)
        .into_par_iter()
        .map(|i| {
            // ... Reconstruct State ...
            let mut state = PlayingState::new(trumps[i]);

            // Reconstruct hands
            for h in 0..4 {
                state.hands[h] = flattened_hands[i * 4 + h];
            }

            state.current_player = players[i];
            state.tricks_won[0] = tricks_won[i][0];
            state.tricks_won[1] = tricks_won[i][1];

            // Reconstruct current trick
            let trick_len = boards[i].len() as u8;
            state.trick_size = trick_len;
            if trick_len > 0 {
                // Current player is the one to move NEXT.
                // So the starter is (current - len) % 4.
                state.trick_starter =
                    (state.current_player as i8 - trick_len as i8).rem_euclid(4) as u8;
            } else {
                state.trick_starter = state.current_player;
            }

            for (idx, &card) in boards[i].iter().enumerate() {
                // ...
                let start_player = state.trick_starter as usize;
                let seat = (start_player + idx) % 4;
                state.current_trick[seat] = card;
            }

            if state.is_terminal() || state.get_legal_moves() == 0 {
                return SolvedGameplaySample {
                    best_card: 0,
                    best_score: 0,
                    valid: false,
                };
            }

            // PIMC Logic
            if pimc_iterations > 1 {
                let mut rng = rand::thread_rng();
                let mut votes = [0; 32];

                // Identify hidden cards (belonging to others)
                let mut hidden_cards = Vec::new();
                let my_player = state.current_player as usize;

                let mut hand_sizes = [0; 4];

                for p in 0..4 {
                    hand_sizes[p] = state.hands[p].count_ones(); // u32::count_ones
                    if p != my_player {
                        let mut h = state.hands[p];
                        while h != 0 {
                            let c = h.trailing_zeros();
                            hidden_cards.push(c);
                            h &= !(1 << c);
                        }
                    }
                }

                if hidden_cards.is_empty() {
                    // No hidden info (e.g. 2 players left or all revealed?), just solve
                    let (best_score, best_card) = solve(&state, false);
                    return SolvedGameplaySample {
                        best_card,
                        best_score,
                        valid: true,
                    };
                }

                for _ in 0..pimc_iterations {
                    // Shuffle
                    hidden_cards.shuffle(&mut rng);

                    // Re-deal consistent with counts
                    let mut temp_state = state.clone();
                    let mut idx = 0;
                    for p in 0..4 {
                        if p != my_player {
                            let mut new_hand = 0;
                            let count = hand_sizes[p];
                            for _ in 0..count {
                                new_hand |= 1 << hidden_cards[idx];
                                idx += 1;
                            }
                            temp_state.hands[p] = new_hand;
                        }
                    }

                    let (_, move_) = solve(&temp_state, false);
                    votes[move_ as usize] += 1;
                }

                // Majority Vote
                let mut max_votes = -1;
                let mut best_card_pimc = 0;
                for c in 0..32 {
                    if votes[c] > max_votes {
                        max_votes = votes[c];
                        best_card_pimc = c as u8;
                    }
                }

                // Score: Use Perfect Information Value of the TRUE state
                let (best_score, _) = solve(&state, false);

                SolvedGameplaySample {
                    best_card: best_card_pimc,
                    best_score,
                    valid: true,
                }
            } else {
                // Determine Double Dummy
                let (best_score, best_card) = solve(&state, false);
                SolvedGameplaySample {
                    best_card,
                    best_score,
                    valid: true,
                }
            }
        })
        .collect();

    // Unzip results
    let mut best_cards = Vec::with_capacity(num_samples);
    let mut best_scores = Vec::with_capacity(num_samples);
    let mut valid_mask = Vec::with_capacity(num_samples);

    for r in results {
        best_cards.push(r.best_card);
        best_scores.push(r.best_score);
        valid_mask.push(r.valid);
    }

    (best_cards, best_scores, valid_mask)
}
