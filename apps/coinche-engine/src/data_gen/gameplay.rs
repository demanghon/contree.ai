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

struct GameplaySample {
    hand: u32,
    board: Vec<u8>,
    history: u32,
    trump: u8,
    best_card: u8,
    best_score: i16,
}

pub fn generate_gameplay_batch(
    batch_size: usize,
) -> (Vec<u32>, Vec<Vec<u8>>, Vec<u32>, Vec<u8>, Vec<u8>, Vec<i16>) {
    // Parallel generation using Rayon
    let samples: Vec<GameplaySample> = (0..batch_size)
        .into_par_iter()
        .progress_count(batch_size as u64)
        .map(|_| generate_single_sample())
        .filter_map(|s| s)
        .collect();

    // Unzip samples into separate vectors
    let mut hands_data = Vec::with_capacity(samples.len());
    let mut boards_data = Vec::with_capacity(samples.len());
    let mut history_data = Vec::with_capacity(samples.len());
    let mut trumps_data = Vec::with_capacity(samples.len());
    let mut best_cards_data = Vec::with_capacity(samples.len());
    let mut best_scores_data = Vec::with_capacity(samples.len());

    for s in samples {
        hands_data.push(s.hand);
        boards_data.push(s.board);
        history_data.push(s.history);
        trumps_data.push(s.trump);
        best_cards_data.push(s.best_card);
        best_scores_data.push(s.best_score);
    }

    (
        hands_data,
        boards_data,
        history_data,
        trumps_data,
        best_cards_data,
        best_scores_data,
    )
}

fn generate_single_sample() -> Option<GameplaySample> {
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
                return None;
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
            return None;
        }
        let m = moves[rng.gen_range(0..moves.len())];
        state.play_card(m);
        history_mask |= 1 << m;
    }

    if state.is_terminal() {
        return None;
    }

    // 2. Critical Decision Filtering & Perturbation
    // We need to evaluate all legal moves to find Best and SecondBest
    let legal_moves_mask = state.get_legal_moves();
    let mut moves_scores = Vec::new();

    for i in 0..32 {
        if (legal_moves_mask & (1 << i)) != 0 {
            let mut next_state = state.clone();
            next_state.play_card(i as u8);
            let (score, _) = solve(&next_state, false);
            moves_scores.push((i as u8, score));
        }
    }

    if moves_scores.len() < 2 {
        // Forced move, skip
        return None;
    }

    // Sort moves based on current player's objective
    let is_maximizing = state.current_player % 2 == 0; // NS maximizes
    if is_maximizing {
        moves_scores.sort_by(|a, b| b.1.cmp(&a.1)); // Descending
    } else {
        moves_scores.sort_by(|a, b| a.1.cmp(&b.1)); // Ascending (minimize NS score)
    }

    let best_move = moves_scores[0].0;
    let best_score = moves_scores[0].1;
    let second_move = moves_scores[1].0;
    let second_score = moves_scores[1].1;

    let delta = (best_score - second_score).abs();

    // 3. Perturbation (20% chance)
    let perturbation = rng.gen_bool(0.2);

    if perturbation {
        // Play sub-optimal move (second best)

        let mut perturbed_state = state.clone();
        perturbed_state.play_card(second_move);

        // Now we want to record this new state
        // We need the optimal move from here
        if perturbed_state.is_terminal() {
            return None;
        }

        let (recovery_score, recovery_best_move) = solve(&perturbed_state, false);

        // Prepare sample
        let mut board = Vec::new();
        for i in 0..4 {
            if perturbed_state.current_trick[i] != 0xFF {
                board.push(perturbed_state.current_trick[i]);
            }
        }

        return Some(GameplaySample {
            hand: perturbed_state.hands[perturbed_state.current_player as usize],
            board,
            history: history_mask | (1 << second_move),
            trump: perturbed_state.trump,
            best_card: recovery_best_move,
            best_score: recovery_score,
        });
    } else {
        // Normal Critical Filtering
        // Keep only if delta > 0 (strictly better)
        if delta == 0 {
            return None;
        }

        // Prepare sample
        let mut board = Vec::new();
        for i in 0..4 {
            if state.current_trick[i] != 0xFF {
                board.push(state.current_trick[i]);
            }
        }

        return Some(GameplaySample {
            hand: state.hands[state.current_player as usize],
            board,
            history: history_mask,
            trump: state.trump,
            best_card: best_move,
            best_score: best_score,
        });
    }
}

pub fn write_gameplay_parquet(
    path: &str,
    hands: &[u32],
    boards: &[Vec<u8>],
    history: &[u32],
    trumps: &[u8],
    best_cards: &[u8],
    best_scores: &[i16],
) -> Result<(), Box<dyn std::error::Error>> {
    let file = File::create(path)?;
    let props = WriterProperties::builder().build();

    let schema = Arc::new(Schema::new(vec![
        Field::new("hand", DataType::UInt32, false),
        Field::new(
            "board",
            DataType::List(Arc::new(Field::new("item", DataType::UInt8, true))),
            false,
        ),
        Field::new("history", DataType::UInt32, false),
        Field::new("trump", DataType::UInt8, false),
        Field::new("best_card", DataType::UInt8, false),
        Field::new("best_score", DataType::Int16, false),
    ]));

    let hand_array = UInt32Array::from(hands.to_vec());
    let history_array = UInt32Array::from(history.to_vec());
    let trump_array = UInt8Array::from(trumps.to_vec());
    let best_card_array = UInt8Array::from(best_cards.to_vec());

    // Flatten boards
    let mut flattened_boards = Vec::new();
    let mut offsets = Vec::new();
    offsets.push(0);
    for b in boards {
        flattened_boards.extend_from_slice(b);
        offsets.push(flattened_boards.len() as i32);
    }
    let values_array = UInt8Array::from(flattened_boards);
    let offsets_buffer = arrow::buffer::Buffer::from_slice_ref(&offsets);

    let boards_array = ListArray::new(
        Arc::new(Field::new("item", DataType::UInt8, true)),
        arrow::buffer::OffsetBuffer::new(offsets_buffer.into()),
        Arc::new(values_array),
        None,
    );

    let best_scores_array = arrow::array::Int16Array::from(best_scores.to_vec());

    let batch = RecordBatch::try_new(
        schema.clone(),
        vec![
            Arc::new(hand_array),
            Arc::new(boards_array),
            Arc::new(history_array),
            Arc::new(trump_array),
            Arc::new(best_card_array),
            Arc::new(best_scores_array),
        ],
    )?;

    let mut writer = ArrowWriter::try_new(file, schema, Some(props))?;
    writer.write(&batch)?;
    writer.close()?;

    Ok(())
}
