use crate::game::GameState;
use crate::solver::solve;
use arrow::array::{Int16Array, ListArray, UInt32Array};
use arrow::datatypes::{DataType, Field, Schema};
use arrow::record_batch::RecordBatch;
use indicatif::ProgressIterator;
use parquet::arrow::ArrowWriter;
use parquet::file::properties::WriterProperties;
use rand::distributions::WeightedIndex;
use rand::prelude::*;
use std::fs::File;
use std::sync::Arc;

use super::common::{generate_biased_hands, GenStrategy};

pub fn generate_bidding_batch(batch_size: usize) -> (Vec<u32>, Vec<Vec<i16>>) {
    let mut hands_south = Vec::with_capacity(batch_size);
    let mut scores_batch = Vec::with_capacity(batch_size);
    let mut rng = rand::thread_rng();

    // Strategy Weights: Random=40, Capot=20, Belote=20, Shape=20
    let _strategies = [
        GenStrategy::Random,
        GenStrategy::ForceCapot,
        GenStrategy::ForceBelote,
        GenStrategy::ForceShape([0; 4]),
    ]; // Shape placeholder
    let weights = [40, 20, 20, 20];
    let dist = WeightedIndex::new(&weights).unwrap();

    // Common shapes for Shape Bias
    let shapes = [
        [6, 3, 2, 1], // Long suit
        [5, 5, 2, 1], // Two long suits
        [5, 4, 2, 1], // Solid
        [4, 4, 4, 0], // Distributional (void)
    ];

    for _ in (0..batch_size).progress() {
        let target_trump = rng.gen_range(0..4) as u8;

        let strategy_idx = dist.sample(&mut rng);
        let strategy = match strategy_idx {
            0 => GenStrategy::Random,
            1 => GenStrategy::ForceCapot,
            2 => GenStrategy::ForceBelote,
            3 => {
                let shape = shapes[rng.gen_range(0..shapes.len())];
                GenStrategy::ForceShape(shape)
            }
            _ => GenStrategy::Random,
        };

        let hands = generate_biased_hands(target_trump, strategy);

        hands_south.push(hands[0]);

        let mut scores = Vec::with_capacity(4);
        // Contracts: 0=D, 1=S, 2=H, 3=C (No NT/AT)
        for trump in 0..4 {
            let mut state = GameState::new(trump as u8);
            state.hands = hands;

            // Solver returns (score, best_move). Score is for the current player's team.
            // At root, current player is 0 (South). So score is NS score.
            let (score, _) = solve(&state, false);

            // Belote is handled in GameState::play_card now.

            scores.push(score);
        }
        scores_batch.push(scores);
    }

    (hands_south, scores_batch)
}

pub fn write_bidding_parquet(filename: &str, hands: &[u32], scores: &[Vec<i16>]) {
    let hand_field = Field::new("hand_south", DataType::UInt32, false);
    // Scores is a list of 4 integers
    let score_item_field = Field::new("item", DataType::Int16, true);
    let scores_field = Field::new("scores", DataType::List(Arc::new(score_item_field)), false);

    let schema = Arc::new(Schema::new(vec![hand_field, scores_field]));

    let hand_array = UInt32Array::from(hands.to_vec());

    // Flatten scores for ListArray
    let mut flattened_scores = Vec::new();
    let mut offsets = Vec::new();
    offsets.push(0);
    for s in scores {
        flattened_scores.extend_from_slice(s);
        offsets.push(flattened_scores.len() as i32);
    }
    let values_array = Int16Array::from(flattened_scores);
    let offsets_buffer = arrow::buffer::Buffer::from_slice_ref(&offsets);

    // Correct way to construct ListArray in newer arrow versions
    let scores_array = ListArray::new(
        Arc::new(Field::new("item", DataType::Int16, true)),
        arrow::buffer::OffsetBuffer::new(offsets_buffer.into()),
        Arc::new(values_array),
        None,
    );

    let batch = RecordBatch::try_new(
        schema.clone(),
        vec![Arc::new(hand_array), Arc::new(scores_array)],
    )
    .unwrap();

    let file = File::create(filename).unwrap();
    let props = WriterProperties::builder().build();
    let mut writer = ArrowWriter::try_new(file, schema, Some(props)).unwrap();
    writer.write(&batch).unwrap();
    writer.close().unwrap();
}
