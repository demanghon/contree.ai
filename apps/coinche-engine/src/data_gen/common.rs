use crate::gameplay::playing::{RANK_10, RANK_7, RANK_8, RANK_9, RANK_A, RANK_J, RANK_K, RANK_Q};
use rand::prelude::*;

pub fn generate_random_hands() -> [u32; 4] {
    let mut rng = rand::thread_rng();
    let mut deck: Vec<u8> = (0..32).collect();
    deck.shuffle(&mut rng);

    let mut hands = [0u32; 4];
    for i in 0..4 {
        for j in 0..8 {
            hands[i] |= 1 << deck[i * 8 + j];
        }
    }
    hands
}

#[derive(Clone, Debug)]
pub enum GenStrategy {
    Random,
    ForceCapot,          // Strong hand
    ForceBelote,         // K+Q of trump
    ForceShape([u8; 4]), // Specific suit distribution (e.g. [5, 3, 2, 1])
}

pub struct HandBuilder {
    trump: u8,
    forced_cards: Vec<u8>,  // Cards forced into South's hand
    shape: Option<[u8; 4]>, // Desired shape for South (Trump, Suit 1, Suit 2, Suit 3) - relative to trump
}

impl HandBuilder {
    pub fn new(trump: u8) -> Self {
        Self {
            trump,
            forced_cards: Vec::new(),
            shape: None,
        }
    }

    pub fn force_card(&mut self, card: u8) -> &mut Self {
        if !self.forced_cards.contains(&card) {
            self.forced_cards.push(card);
        }
        self
    }

    pub fn force_shape(&mut self, shape: [u8; 4]) -> &mut Self {
        self.shape = Some(shape);
        self
    }

    pub fn build(&self) -> [u32; 4] {
        let mut rng = rand::thread_rng();
        let mut hands = [0u32; 4];
        let mut deck: Vec<u8> = (0..32).collect();

        // Remove forced cards from deck
        deck.retain(|c| !self.forced_cards.contains(c));

        // 1. Assign forced cards to South
        for &c in &self.forced_cards {
            hands[0] |= 1 << c;
        }

        // 2. Fulfill Shape for South
        if let Some(shape) = self.shape {
            // shape is [count_trump, count_s1, count_s2, count_s3]
            // We need to map s1, s2, s3 to actual suits.
            // Let's say s1 = (trump + 1) % 4, s2 = (trump + 2) % 4, etc.
            let suits = [
                self.trump,
                (self.trump + 1) % 4,
                (self.trump + 2) % 4,
                (self.trump + 3) % 4,
            ];

            for (i, &count) in shape.iter().enumerate() {
                let suit = suits[i];
                let current_count = self.count_suit(hands[0], suit);

                if current_count < count {
                    let needed = count - current_count;
                    // Find available cards of this suit in deck
                    let mut available: Vec<u8> =
                        deck.iter().cloned().filter(|&c| c / 8 == suit).collect();

                    available.shuffle(&mut rng);

                    for _ in 0..needed {
                        if let Some(c) = available.pop() {
                            hands[0] |= 1 << c;
                            // Remove from deck
                            if let Some(pos) = deck.iter().position(|&x| x == c) {
                                deck.remove(pos);
                            }
                        }
                    }
                }
            }
        }

        // 3. Fill remaining slots for South (up to 8)
        let south_count = self.count_cards(hands[0]);
        if south_count < 8 {
            let needed = 8 - south_count;

            deck.shuffle(&mut rng);
            for _ in 0..needed {
                let c = deck.pop().unwrap();
                hands[0] |= 1 << c;
            }
        }

        // 4. Deal remaining cards to other players
        deck.shuffle(&mut rng);
        for i in 1..4 {
            for _ in 0..8 {
                if let Some(c) = deck.pop() {
                    hands[i] |= 1 << c;
                }
            }
        }

        hands
    }

    fn count_suit(&self, hand: u32, suit: u8) -> u8 {
        let mut count = 0;
        for r in 0..8 {
            if (hand & (1 << (suit * 8 + r))) != 0 {
                count += 1;
            }
        }
        count
    }

    fn count_cards(&self, hand: u32) -> u8 {
        hand.count_ones() as u8
    }
}

pub fn generate_biased_hands(trump: u8, strategy: GenStrategy) -> [u32; 4] {
    let mut builder = HandBuilder::new(trump);
    let mut rng = rand::thread_rng();

    match strategy {
        GenStrategy::Random => {
            // No constraints, builder will fill randomly
        }
        GenStrategy::ForceBelote => {
            // K + Q of trump
            // K=6, Q=5
            builder.force_card(trump * 8 + 6);
            builder.force_card(trump * 8 + 5);
        }
        GenStrategy::ForceCapot => {
            // Generate a random "Master Hand" (Force Capot)
            // 1. Trumps: Length N (4..=8). Must be top N trumps.
            // 2. Side Suits: Remaining 8-N cards distributed randomly. Must be top K cards of that suit.

            let mut remaining = 8;

            // 1. Trumps
            // Weighted choice for reasonable variety? Or just uniform 4..8?
            // Uniform is fine.
            let trump_len = rng.gen_range(4..=8);
            remaining -= trump_len;

            let trump_rank_order = [
                RANK_J, RANK_9, RANK_A, RANK_10, RANK_K, RANK_Q, RANK_8, RANK_7,
            ];
            for i in 0..trump_len {
                builder.force_card(trump * 8 + trump_rank_order[i]);
            }

            // 2. Side Suits
            if remaining > 0 {
                // Distribute 'remaining' cards among 3 side suits
                let mut side_indices = Vec::new(); // indices 0, 1, 2 representing side suits relative to trump
                for i in 1..4 {
                    side_indices.push(i);
                }

                let mut counts = [0u8; 4]; // Only indices 1,2,3 will be used

                for _ in 0..remaining {
                    let idx = *side_indices.choose(&mut rng).unwrap();
                    counts[idx] += 1;
                }

                let side_rank_order = [
                    RANK_A, RANK_10, RANK_K, RANK_Q, RANK_J, RANK_9, RANK_8, RANK_7,
                ];

                for i in 1..4 {
                    if counts[i] > 0 {
                        let suit = (trump + i as u8) % 4;
                        let count = counts[i] as usize;
                        for r in 0..count {
                            builder.force_card(suit * 8 + side_rank_order[r]);
                        }
                    }
                }
            }
        }
        GenStrategy::ForceShape(shape) => {
            builder.force_shape(shape);
        }
    }

    builder.build()
}
