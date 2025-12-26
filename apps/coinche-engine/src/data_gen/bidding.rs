use crate::gameplay::playing::PlayingState;
use crate::solver::solve;
use arrow::array::{Int16Array, ListArray, UInt32Array};
use arrow::datatypes::{DataType, Field, Schema};
use arrow::record_batch::RecordBatch;
use indicatif::{ParallelProgressIterator, ProgressIterator};
use parquet::arrow::ArrowWriter;
use parquet::file::properties::WriterProperties;
use rand::distributions::WeightedIndex;
use rand::prelude::*;
use rayon::prelude::*;
use std::fs::File;
use std::sync::Arc;

use super::common::{generate_biased_hands, GenStrategy};

pub fn generate_hand_batch(batch_size: usize) -> (Vec<u32>, Vec<u8>) {
    // Strategy Weights: Random=40, Capot=20, Belote=20, Shape=20
    let weights = [40, 20, 20, 20];

    // Common shapes for Shape Bias
    let shapes = [
        [6, 3, 2, 1], // Long suit
        [5, 5, 2, 1], // Two long suits
        [5, 4, 2, 1], // Solid
        [4, 4, 4, 0], // Distributional (void)
    ];

    // We return a tuple:
    // 1. Flattened hands: Vec<u32> of size batch_size * 4.
    //    Each block of 4 u32s represents one deal: [South, West, North, East].
    // 2. Strategies: Vec<u8> of size batch_size.
    let (hands_flattened, strategies): (Vec<Vec<u32>>, Vec<u8>) = (0..batch_size)
        .into_par_iter()
        .progress_count(batch_size as u64)
        .map_init(
            || {
                let rng = rand::thread_rng();
                let dist = WeightedIndex::new(&weights).unwrap();
                (rng, dist)
            },
            |(rng, dist), _| {
                let target_trump = rng.gen_range(0..4) as u8;

                let strategy_idx = dist.sample(rng);
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
                // hands is [u32; 4]. Convert to Vec<u32>.
                (hands.to_vec(), strategy_idx as u8)
            },
        )
        .unzip();

    // Flatten the list of lists into a single Vec<u32>
    let flattened_hands: Vec<u32> = hands_flattened.into_iter().flatten().collect();

    (flattened_hands, strategies)
}

pub fn solve_hand_batch(flattened_hands: Vec<u32>) -> Vec<Vec<i16>> {
    // flattened_hands length should be divisible by 4
    let num_samples = flattened_hands.len() / 4;

    // chunk(4) is not directly available on slice in a way that plays nice with par_iter
    // unless we use `par_chunks`.
    let scores_batch: Vec<Vec<i16>> = flattened_hands
        .par_chunks(4)
        .progress_count(num_samples as u64)
        .map(|hand_chunk| {
            // hand_chunk is &[u32] of length 4
            let mut hands = [0u32; 4];
            hands.copy_from_slice(hand_chunk);

            let mut scores = Vec::with_capacity(4);
            // Contracts: 0=D, 1=S, 2=H, 3=C (No NT/AT)
            for trump in 0..4 {
                let mut state = PlayingState::new(trump as u8);
                state.hands = hands;

                // Solver returns (score, best_move). Score is for the current player's team.
                // At root, current player is 0 (South). So score is NS score.
                let (score, _) = solve(&state, false);
                scores.push(score);
            }
            scores
        })
        .collect();

    scores_batch
}

// NOTE: This function is kept but needs updates if we want to use it with the new format directly.
// For now, I'm assuming we do the writing in Python or update this signature later.
// The Python plan says we write Parquet from Python using PyArrow,
// so this Rust function might become obsolete or need to change to accept just south hand + scores.
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

    let path = std::path::Path::new(filename);
    if let Some(parent) = path.parent() {
        std::fs::create_dir_all(parent).unwrap();
    }
    let file = File::create(filename).unwrap();
    let props = WriterProperties::builder().build();
    let mut writer = ArrowWriter::try_new(file, schema, Some(props)).unwrap();
    writer.write(&batch).unwrap();
    writer.close().unwrap();
}
