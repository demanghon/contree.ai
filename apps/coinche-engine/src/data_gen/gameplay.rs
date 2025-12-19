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
    hands: Vec<u32>,
    boards: Vec<Vec<u8>>,
    history: Vec<u32>,
    trumps: Vec<u8>,
    tricks_won: Vec<Vec<u8>>,
    players: Vec<u8>,
) -> (Vec<u8>, Vec<i16>, Vec<bool>) {
    // We iterate in parallel
    let results: Vec<SolvedGameplaySample> = (0..hands.len())
        .into_par_iter()
        .map(|i| {
            // Reconstruct State
            // Note: We only have 'hand' of current player (u32), history (u32), trump.
            // But to run solver, we need FULL state (all 4 hands).
            // PROBLEM: In `generate_raw_state`, we threw away the other 3 hands!
            // The solver is Double Dummy, it needs perfect information.
            // If we only save "My Hand" + "History", we cannot reconstruct the opponent hands exactly as they were.
            // We can reconstruct "A" potential deal consistent with history, but it won't be the same one.
            // Does this matter?
            // Yes. If we simulated a specific game, we should solve THAT specific game.
            // If we regenerate random opponent hands now, they might be inconsistent or "easier/harder" than the original.

            // Correction: We MUST save all 4 hands in the raw state.
            // Since we receive a `Vec<u32>` of hands here, let's assume we pass ALL 4 hands combined or similar.
            // Or better, for Phase 1 <-> Phase 2, we just pass the full u32[4] hands.

            // I will return invalid dummy result for now to indicate I need to refactor signatures in next step.
            SolvedGameplaySample {
                best_card: 0,
                best_score: 0,
                valid: false,
            }
        })
        .collect();

    (vec![], vec![], vec![])
}
