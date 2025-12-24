use crate::game::GameState;
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
    // 50% Endgame (Tricks 6-8 -> 5-7 index)
    // 30% Midgame (Tricks 3-5 -> 2-4 index)
    // 20% Opening (Tricks 1-2 -> 0-1 index)
    let r = rng.gen_range(0..100);
    let target_trick = if r < 50 {
        rng.gen_range(5..8)
    } else if r < 80 {
        rng.gen_range(2..5)
    } else {
        rng.gen_range(0..2)
    };

    let hands = generate_random_hands();
    let trump = rng.gen_range(0..4) as u8;

    let mut state = GameState::new(trump);
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
                // Should not happen theoretically if logic correct
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
    players: Vec<u8>,
) -> (Vec<u8>, Vec<i16>, Vec<bool>) {
    // flattened_hands is size N*4.
    let num_samples = boards.len();

    let results: Vec<SolvedGameplaySample> = (0..num_samples)
        .into_par_iter()
        .map(|i| {
            // Reconstruct State
            let mut state = GameState::new(trumps[i]);

            // Reconstruct hands
            for h in 0..4 {
                state.hands[h] = flattened_hands[i * 4 + h];
            }

            state.current_player = players[i];
            state.tricks_won[0] = tricks_won[i][0];
            state.tricks_won[1] = tricks_won[i][1];

            // Reconstruct current trick
            for (idx, &card) in boards[i].iter().enumerate() {
                let len = boards[i].len();
                let start_player = (state.current_player as i8 - len as i8).rem_euclid(4) as usize;
                let seat = (start_player + idx) % 4;
                state.current_trick[seat] = card;
            }

            // --- Logic from generate_single_sample (Perturbation & Filtering) ---

            if state.is_terminal() {
                return SolvedGameplaySample {
                    best_card: 0,
                    best_score: 0,
                    valid: false,
                };
            }

            let legal_moves_mask = state.get_legal_moves();
            let mut moves_scores = Vec::new();

            for j in 0..32 {
                if (legal_moves_mask & (1 << j)) != 0 {
                    let mut next_state = state.clone();
                    next_state.play_card(j as u8);
                    let (score, _) = solve(&next_state, false);
                    moves_scores.push((j as u8, score));
                }
            }

            if moves_scores.len() < 2 {
                return SolvedGameplaySample {
                    best_card: 0,
                    best_score: 0,
                    valid: false,
                };
            }

            // Sort moves
            let is_maximizing = state.current_player % 2 == 0;
            if is_maximizing {
                moves_scores.sort_by(|a, b| b.1.cmp(&a.1));
            } else {
                moves_scores.sort_by(|a, b| a.1.cmp(&b.1));
            }

            let best_move = moves_scores[0].0;
            let best_score = moves_scores[0].1;
            let second_move = moves_scores[1].0;
            let second_score = moves_scores[1].1;
            let delta = (best_score - second_score).abs();

            let mut rng = rand::thread_rng();
            let perturbation = rng.gen_bool(0.2);

            if perturbation {
                let mut perturbed_state = state.clone();
                perturbed_state.play_card(second_move);

                if perturbed_state.is_terminal() {
                    return SolvedGameplaySample {
                        best_card: 0,
                        best_score: 0,
                        valid: false,
                    };
                }

                let (recovery_score, recovery_best_move) = solve(&perturbed_state, false);

                return SolvedGameplaySample {
                    best_card: recovery_best_move,
                    best_score: recovery_score,
                    valid: true,
                };
            } else {
                if delta == 0 {
                    return SolvedGameplaySample {
                        best_card: 0,
                        best_score: 0,
                        valid: false,
                    };
                }
                return SolvedGameplaySample {
                    best_card: best_move,
                    best_score: best_score,
                    valid: true,
                };
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
