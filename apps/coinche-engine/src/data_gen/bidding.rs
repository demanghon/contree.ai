use crate::gameplay::playing::{
    PlayingState, RANK_10, RANK_7, RANK_8, RANK_9, RANK_A, RANK_J, RANK_K, RANK_Q,
};
use crate::solver::solve;
use arrow::array::{Float32Array, Int16Array, ListArray, UInt32Array};
use arrow::datatypes::{DataType, Field, Schema};
use arrow::record_batch::RecordBatch;
use indicatif::{ParallelProgressIterator, ProgressBar, ProgressStyle};
use parquet::arrow::ArrowWriter;
use parquet::file::properties::WriterProperties;
use rand::distributions::WeightedIndex;
use rand::prelude::*;
use rayon::prelude::*;
use std::fs::File;
use std::sync::atomic::{AtomicBool, AtomicUsize, Ordering};
use std::sync::Arc;
use std::thread;
use std::time::Duration;

use super::common::{generate_biased_hands, GenStrategy};

pub fn generate_hand_batch(batch_size: usize) -> (Vec<u32>, Vec<u8>) {
    // Strategy Weights: Random=40, Capot=20, Belote=20, Shape=20
    let weights = [40, 20, 20, 20];

    // Common shapes for Shape Bias
    // Common shapes for Shape Bias (Must sum to 8)
    let shapes = [
        [5, 2, 1, 0], // Long suit
        [4, 3, 1, 0], // Two long suits
        [4, 2, 1, 1], // Solid
        [3, 3, 2, 0], // Distributional (void)
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

// Helper to check if a hand is a guaranteed "Force Capot" (Master Hand).
// A hand is a guaranteed Capot if:
// 1. Trumps form a Solid Sequence from the top (J, 9, A...) of length N >= 4.
// 2. All side suits form Solid Sequences from the top (A, 10, K...) of any length (could be 0).
fn is_force_capot(hand: u32, trump: u8) -> bool {
    let trump_mask = 0xFF << (trump * 8);
    let trump_cards = hand & trump_mask;
    let shift = trump * 8;
    let trump_count = trump_cards.count_ones();

    // 1. Check Trump Sequence
    if trump_count < 4 {
        return false;
    }

    // Order: J(4), 9(2), A(7), 10(3), K(6), Q(5), 8(1), 7(0)
    let trump_rank_order = [
        RANK_J, RANK_9, RANK_A, RANK_10, RANK_K, RANK_Q, RANK_8, RANK_7,
    ];
    for i in 0..trump_count as usize {
        let rank_idx = trump_rank_order[i];
        if (trump_cards & (1 << (shift + rank_idx))) == 0 {
            return false;
        }
    }

    // 2. Check Side Suits
    // Order: A(7), 10(3), K(6), Q(5), J(4), 9(2), 8(1), 7(0)
    let side_rank_order = [
        RANK_A, RANK_10, RANK_K, RANK_Q, RANK_J, RANK_9, RANK_8, RANK_7,
    ];
    for s in 0..4 {
        if s == trump {
            continue;
        }

        let suit_mask = 0xFF << (s * 8);
        let suit_cards = hand & suit_mask;
        if suit_cards == 0 {
            continue;
        } // Void is perfect

        let count = suit_cards.count_ones();
        let shift_s = s * 8;

        // Check if we have top 'count' cards
        for i in 0..count as usize {
            let rank_idx = side_rank_order[i];
            if (suit_cards & (1 << (shift_s + rank_idx))) == 0 {
                return false;
            }
        }
    }

    true
}

// Helper to compute hand potential
fn evaluate_hand_potential(hand: u32, trump: u8) -> i32 {
    // 1. Check Force Capot (Master Hand)
    if is_force_capot(hand, trump) {
        return 10000;
    }

    let mut score = 0;
    let mut trump_count = 0;
    let mut has_jack = false;

    // Masks
    let trump_mask = 0xFF << (trump * 8);
    let trump_cards = hand & trump_mask;

    // Check Trumps
    if trump_cards != 0 {
        // Iterate naive or bit tricks
        // Indices of trumps: (trump*8) + [0..7]
        // Ranks: 0=7, 1=8, 2=9, 3=10, 4=J, 5=Q, 6=K, 7=A

        let shift = trump * 8;
        trump_count = trump_cards.count_ones();

        // Jack check (Rank 4)
        if (trump_cards & (1 << (shift + RANK_J))) != 0 {
            score += 20;
            has_jack = true;
        }

        // 9 check (Rank 2)
        if (trump_cards & (1 << (shift + RANK_9))) != 0 {
            if has_jack {
                score += 14;
            }
        }

        // Belote/Rebelote (K+Q -> Rank 6+5)
        let has_k = (trump_cards & (1 << (shift + RANK_K))) != 0;
        let has_q = (trump_cards & (1 << (shift + RANK_Q))) != 0;
        if has_k && has_q {
            score += 20;
        }

        if trump_count >= 5 {
            score += 20;
        }
    }

    // Check Aces outside trump
    for s in 0..4 {
        if s == trump {
            continue;
        }
        // Ace is rank 7
        if (hand & (1 << (s * 8 + RANK_A))) != 0 {
            score += 11;
        }
    }

    score
}

// Helper to compute weak hand face value (heuristic fallback)
fn compute_face_value(hand: u32, trump: u8) -> f32 {
    let mut points = 0;
    for c in 0..32 {
        if (hand & (1 << c)) != 0 {
            let s = (c / 8) as u8;
            let r = (c % 8) as usize;
            if s == trump {
                points += crate::gameplay::playing::POINTS_TRUMP[r];
            } else {
                points += crate::gameplay::playing::POINTS_NON_TRUMP[r];
            }
        }
    }
    points as f32
}

pub fn solve_hand_batch(
    flattened_hands: Vec<u32>,
    pimc_iterations: usize,
    tt_log2: Option<u8>,
) -> Vec<Vec<f32>> {
    // flattened_hands length should be divisible by 4
    let num_samples = flattened_hands.len() / 4;

    let pb = ProgressBar::new(num_samples as u64);
    pb.set_style(
        ProgressStyle::default_bar()
            .template(
                "{spinner:.green} [{elapsed_precise}] [{bar:40.cyan/blue}] {pos}/{len} ({eta}) {msg}",
            )
            .unwrap()
            .progress_chars("#>-"),
    );

    let weak_count = Arc::new(AtomicUsize::new(0));
    let capot_count = Arc::new(AtomicUsize::new(0));
    let running = Arc::new(AtomicBool::new(true));

    // Spawn stats updater
    let pb_clone = pb.clone();
    let weak_clone_monitor = weak_count.clone();
    let capot_clone_monitor = capot_count.clone();
    let running_monitor = running.clone();

    thread::spawn(move || {
        while running_monitor.load(Ordering::Relaxed) {
            let w = weak_clone_monitor.load(Ordering::Relaxed);
            let c = capot_clone_monitor.load(Ordering::Relaxed);
            pb_clone.set_message(format!("Weak: {} Capot: {}", w, c));
            thread::sleep(Duration::from_millis(500));
        }
    });

    let weak_ref = weak_count.clone();
    let capot_ref = capot_count.clone();

    let scores_batch: Vec<Vec<f32>> = flattened_hands
        .par_chunks(4)
        .progress_with(pb)
        .map(|hand_chunk| {
            // hand_chunk is &[u32] of length 4
            let mut hands = [0u32; 4];
            hands.copy_from_slice(hand_chunk);

            // Contracts: 0=D, 1=S, 2=H, 3=C (No NT/AT)
            if pimc_iterations > 1 {
                // PIMC Logic: Ignore other hands, regenerate world based on South Hand
                let south_hand = hands[0];
                let mut unseen_cards = Vec::with_capacity(24);

                // Pre-calculate unseen
                for c in 0..32 {
                    if (south_hand & (1 << c)) == 0 {
                        unseen_cards.push(c);
                    }
                }

                let mut rng = rand::thread_rng();
                let mut scores = Vec::with_capacity(4);

                for trump in 0..4 {
                    // 1. FILTER WEAK HANDS (Junk Hand Heuristic)
                    let potential = evaluate_hand_potential(south_hand, trump as u8);

                    /*
                    if potential >= 10000 {
                        // FORCE CAPOT DETECTED
                        capot_ref.fetch_add(1, Ordering::Relaxed);
                        scores.push(252.0);
                        continue;
                    }

                    if potential < 40 {
                        // Skip PIMC, return fallback
                        weak_ref.fetch_add(1, Ordering::Relaxed);
                        scores.push(compute_face_value(south_hand, trump as u8));
                        continue;
                    }
                    */

                    let mut total_score: i32 = 0;

                    for _ in 0..pimc_iterations {
                        unseen_cards.shuffle(&mut rng);

                        let mut state = PlayingState::new(trump as u8);
                        state.hands[0] = south_hand;

                        // Distribute 8 to West, 8 to North, 8 to East
                        // (Indices 0..8, 8..16, 16..24)
                        let mut w = 0;
                        for i in 0..8 {
                            w |= 1 << unseen_cards[i];
                        }
                        state.hands[1] = w;

                        let mut n = 0;
                        for i in 8..16 {
                            n |= 1 << unseen_cards[i];
                        }
                        state.hands[2] = n;

                        let mut e = 0;
                        for i in 16..24 {
                            e |= 1 << unseen_cards[i];
                        }
                        state.hands[3] = e;

                        let (s, _) = solve(&state, false, Some(32), tt_log2);
                        total_score += s as i32;
                    }

                    let avg = total_score as f32 / pimc_iterations as f32;
                    scores.push(avg);
                }
                scores
            } else {
                // Double Dummy on specific deal
                let mut scores = Vec::with_capacity(4);
                for trump in 0..4 {
                    let mut state = PlayingState::new(trump as u8);
                    state.hands = hands;
                    let (score, _) = solve(&state, false, Some(32), tt_log2);
                    scores.push(score as f32);
                }
                scores
            }
        })
        .collect();

    running.store(false, Ordering::Relaxed);
    println!(
        "Stats: Weak Hands: {}, Force Capot: {}",
        weak_count.load(Ordering::Relaxed),
        capot_count.load(Ordering::Relaxed)
    );

    scores_batch
}

// NOTE: This function is kept but needs updates if we want to use it with the new format directly.
// For now, I'm assuming we do the writing in Python or update this signature later.
// The Python plan says we write Parquet from Python using PyArrow,
// so this Rust function might become obsolete or need to change to accept just south hand + scores.
pub fn write_bidding_parquet(filename: &str, hands: &[u32], scores: &[Vec<f32>]) {
    let hand_field = Field::new("hand_south", DataType::UInt32, false);
    // Scores is a list of 4 integers
    let score_item_field = Field::new("item", DataType::Float32, true);
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
    let values_array = Float32Array::from(flattened_scores);
    let offsets_buffer = arrow::buffer::Buffer::from_slice_ref(&offsets);

    // Correct way to construct ListArray in newer arrow versions
    let scores_array = ListArray::new(
        Arc::new(Field::new("item", DataType::Float32, true)),
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
#[cfg(test)]
mod tests {
    use super::*;
    use crate::gameplay::playing::{CLUBS, DIAMONDS, HEARTS, SPADES};

    fn card(suit: u8, rank: u8) -> u32 {
        1 << (suit * 8 + rank)
    }

    #[test]
    fn test_hand_potential_strong() {
        // Valet + 9 + As = 20 + 14 + 11 = 45 > 40
        let trump = HEARTS;
        let mut hand = 0;
        hand |= card(HEARTS, RANK_J); // Valet
        hand |= card(HEARTS, RANK_9); // 9
        hand |= card(SPADES, RANK_A); // As

        let score = evaluate_hand_potential(hand, trump);
        assert!(score >= 45);
    }

    #[test]
    fn test_hand_potential_weak() {
        // Just small trumps and small cards
        // 7, 8 Trumps (0), 7, 8 Spades (0), 7, 8 Clubs (0)
        let trump = HEARTS;
        let mut hand = 0;
        hand |= card(HEARTS, RANK_7);
        hand |= card(HEARTS, RANK_8);
        hand |= card(SPADES, RANK_7);
        hand |= card(SPADES, RANK_8);

        let score = evaluate_hand_potential(hand, trump);
        assert!(score < 40);
        assert_eq!(score, 0);
    }

    #[test]
    fn test_hand_potential_belote() {
        // K + Q Trumps = 20
        let trump = HEARTS;
        let mut hand = 0;
        hand |= card(HEARTS, RANK_K); // K
        hand |= card(HEARTS, RANK_Q); // Q

        let score = evaluate_hand_potential(hand, trump);
        assert_eq!(score, 20);
    }
    #[test]
    fn test_hand_potential_force_capot_all_trumps() {
        let trump = HEARTS;
        let mut hand = 0;
        // All 8 trumps
        for i in 0..8 {
            hand |= card(HEARTS, i);
        }

        let score = evaluate_hand_potential(hand, trump);
        assert_eq!(score, 10000);
    }

    #[test]
    fn test_hand_potential_force_capot_top5_3aces() {
        // Top 5 trumps: J, 9, A, 10, K
        let trump = HEARTS;
        let mut hand = 0;
        hand |= card(HEARTS, RANK_J); // J
        hand |= card(HEARTS, RANK_9); // 9
        hand |= card(HEARTS, RANK_A); // A
        hand |= card(HEARTS, RANK_10); // 10
        hand |= card(HEARTS, RANK_K); // K

        // 3 Aces Side
        hand |= card(SPADES, RANK_A);
        hand |= card(CLUBS, RANK_A);
        hand |= card(DIAMONDS, RANK_A);

        let score = evaluate_hand_potential(hand, trump);
        assert_eq!(score, 10000);
    }

    #[test]
    fn test_hand_potential_force_capot_fail_loser_card() {
        let trump = HEARTS;
        let mut hand = 0;
        // Top 4 Trumps: J(4), 9(2), A(7), 10(3)
        hand |= card(HEARTS, RANK_J);
        hand |= card(HEARTS, RANK_9);
        hand |= card(HEARTS, RANK_A);
        hand |= card(HEARTS, RANK_10);

        // 3 Aces (Spades, Clubs, Diamonds) => Rank 7
        hand |= card(SPADES, RANK_A);
        hand |= card(CLUBS, RANK_A);
        hand |= card(DIAMONDS, RANK_A);

        // 8th card garbage (7 of Clubs, rank 0) -> NOT Master (A is held, but 10/K/Q missing?)
        // Algorithm requires Solid Sequence.
        // 7 Clubs implies I have A, 10, K, Q, J, 9, 8, 7.
        // But I only have A and 7. Sequence broken.
        hand |= card(CLUBS, RANK_7);

        let score = evaluate_hand_potential(hand, trump);
        // Should NOT be 10000 (Force Capot)
        // Score should be heuristic sum:
        // J(20)+9(14)+A(11) + 3 Aces(33) + Check Belote? No.
        // Hand has J, 9 (Trumps) -> +34.
        // Aces -> +33.
        // Total ~67.
        assert!(score < 10000);
        assert!(score > 40);
    }

    #[test]
    fn test_hand_potential_force_capot_top4_a10_a10() {
        // User query: "4 first trumps and A 10 and another A 10"
        let trump = HEARTS;
        let mut hand = 0;

        // 1. Top 4 Trumps: J, 9, A, 10
        hand |= card(HEARTS, RANK_J); // J
        hand |= card(HEARTS, RANK_9); // 9
        hand |= card(HEARTS, RANK_A); // A
        hand |= card(HEARTS, RANK_10); // 10

        // 2. Spades: A, 10 (Top 2 cards of suit)
        hand |= card(SPADES, RANK_A); // A (Rank 7)
        hand |= card(SPADES, RANK_10); // 10 (Rank 3)

        // 3. Clubs: A, 10 (Top 2 cards of suit)
        hand |= card(CLUBS, RANK_A); // A
        hand |= card(CLUBS, RANK_10); // 10

        // 4. Diamonds: Void (Solid sequence of length 0)

        let score = evaluate_hand_potential(hand, trump);
        assert_eq!(score, 10000);
    }

    #[test]
    fn test_generated_force_capot_hands() {
        // Test that hands generated by GenStrategy::ForceCapot are actually detected as such.
        // run 100 times to cover random variations
        for _ in 0..100 {
            let trump = rand::thread_rng().gen_range(0..4);
            let hands = generate_biased_hands(trump, GenStrategy::ForceCapot);
            let south_hand = hands[0];

            let score = evaluate_hand_potential(south_hand, trump);
            assert_eq!(
                score, 10000,
                "Generated hand was not detected as Force Capot: {:032b}",
                south_hand
            );
        }
    }
}
