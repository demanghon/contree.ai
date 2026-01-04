use pyo3::prelude::*;

// Card mapping constants
// Suits
#[allow(dead_code)]
pub const DIAMONDS: u8 = 0;
#[allow(dead_code)]
pub const SPADES: u8 = 1;
#[allow(dead_code)]
pub const HEARTS: u8 = 2;
#[allow(dead_code)]
pub const CLUBS: u8 = 3;
#[allow(dead_code)]
pub const NO_TRUMP: u8 = 4;
#[allow(dead_code)]
pub const ALL_TRUMP: u8 = 5;

// Ranks (0-7)
pub const RANK_7: u8 = 0;
pub const RANK_8: u8 = 1;
pub const RANK_9: u8 = 2;
pub const RANK_10: u8 = 3;
pub const RANK_J: u8 = 4;
pub const RANK_Q: u8 = 5;
pub const RANK_K: u8 = 6;
pub const RANK_A: u8 = 7;

// Points
// Non-Trump: 7=0, 8=0, 9=0, 10=10, J=2, Q=3, K=4, A=11
pub const POINTS_NON_TRUMP: [u16; 8] = [0, 0, 0, 10, 2, 3, 4, 11];
// Trump: 7=0, 8=0, 9=14, 10=10, J=20, Q=3, K=4, A=11
pub const POINTS_TRUMP: [u16; 8] = [0, 0, 14, 10, 20, 3, 4, 11];

// Order (Strength)
// Non-Trump: 7, 8, 9, J, Q, K, 10, A (Indices: 0, 1, 2, 4, 5, 6, 3, 7)
// But wait, standard rank order in bitboard is 7,8,9,10,J,Q,K,A.
// Strength table (higher is better):
pub const RANK_STRENGTH_NON_TRUMP: [u8; 8] = [0, 1, 2, 6, 3, 4, 5, 7]; // 7<8<9<J<Q<K<10<A
pub const RANK_STRENGTH_TRUMP: [u8; 8] = [0, 1, 6, 4, 7, 2, 3, 5]; // 7<8<Q<K<10<A<9<J

#[pyclass]
#[derive(Clone, Copy, Debug)]
pub struct PlayingState {
    #[pyo3(get)]
    pub hands: [u32; 4],
    #[pyo3(get)]
    pub current_trick: [u8; 4],
    #[pyo3(get)]
    pub tricks_won: [u8; 2],
    #[pyo3(get)]
    pub points: [u16; 2],
    #[pyo3(get)]
    pub trump: u8,
    #[pyo3(get)]
    pub current_player: u8,
    #[pyo3(get)]
    pub trick_starter: u8,
    #[pyo3(get)]
    pub trick_size: u8,
    #[pyo3(get)]
    pub belote_scored: [bool; 2],
    #[pyo3(get)]
    pub last_trick: [u8; 4],
    #[pyo3(get)]
    pub last_trick_starter: u8,
    #[pyo3(get)]
    pub last_trick_winner: Option<u8>,
}

impl PlayingState {
    pub fn new(trump: u8) -> Self {
        PlayingState {
            hands: [0; 4],
            current_trick: [0xFF; 4],
            tricks_won: [0; 2],
            points: [0; 2],
            trump,
            current_player: 0,
            trick_starter: 0,
            trick_size: 0,
            belote_scored: [false; 2],
            last_trick: [255; 4],
            last_trick_starter: 0,
            last_trick_winner: None,
        }
    }
}

#[pymethods]
impl PlayingState {
    #[new]
    pub fn py_new(trump: u8) -> Self {
        PlayingState::new(trump)
    }

    pub fn set_hand(&mut self, player: u8, cards: u32) {
        if player < 4 {
            self.hands[player as usize] = cards;
        }
    }

    pub fn get_hand(&self, player: u8) -> u32 {
        if player < 4 {
            self.hands[player as usize]
        } else {
            0
        }
    }

    /// Returns a bitmask of legal moves for the current player
    pub fn get_legal_moves(&self) -> u32 {
        let hand = self.hands[self.current_player as usize];

        // If leading, any card is legal
        if self.trick_size == 0 {
            return hand;
        }

        let lead_card = self.current_trick[self.trick_starter as usize];
        let lead_suit = lead_card / 8;

        // println!("Player: {}, TrickSize: {}, Starter: {}, LeadCard: {}, LeadSuit: {}", self.current_player, self.trick_size, self.trick_starter, lead_card, lead_suit);

        // Helper to get cards of a specific suit
        let get_suit = |h: u32, s: u8| -> u32 {
            if s >= 4 {
                // println!("Warning: Invalid suit s={} lead_card={}", s, lead_card);
                return 0;
            }
            h & (0xFF << (s * 8))
        };

        let hand_lead_suit = get_suit(hand, lead_suit);

        // 1. Must follow suit
        if hand_lead_suit != 0 {
            // Special case: Over-cutting when following suit?
            // No, only if the suit LED is Trump, then we must play higher if possible.
            if lead_suit == self.trump {
                let current_winner_card = self.get_current_trick_winner();
                let winner_rank = current_winner_card % 8;
                let winner_strength = RANK_STRENGTH_TRUMP[winner_rank as usize];

                // Filter for higher trumps
                let mut higher_trumps = 0;
                for r in 0..8 {
                    if (hand_lead_suit & (1 << (lead_suit * 8 + r))) != 0 {
                        if RANK_STRENGTH_TRUMP[r as usize] > winner_strength {
                            higher_trumps |= 1 << (lead_suit * 8 + r);
                        }
                    }
                }
                if higher_trumps != 0 {
                    return higher_trumps;
                }
            }
            return hand_lead_suit;
        }

        // 2. If cannot follow suit

        // Who is currently winning?
        let partner = (self.current_player + 2) % 4;
        let current_winner = self.get_current_trick_winner_player();
        let partner_winning = current_winner == partner;

        let hand_trumps = get_suit(hand, self.trump);

        // If partner is winning, we can play anything (no need to cut)
        // UNLESS we are playing All Trump or No Trump where rules might differ slightly,
        // but standard Belote Contrée: "Si le partenaire est maître, on n'est pas obligé de couper."
        if partner_winning {
            return hand;
        }

        // If partner is NOT winning (enemy is master), we MUST cut if we have trumps.
        if hand_trumps != 0 {
            // Must over-cut?
            // If the enemy is winning with a trump, we must play a higher trump.
            let winner_card = self.current_trick[current_winner as usize];
            let winner_suit = winner_card / 8;

            if winner_suit == self.trump {
                let winner_rank = winner_card % 8;
                let winner_strength = RANK_STRENGTH_TRUMP[winner_rank as usize];

                let mut higher_trumps = 0;
                for r in 0..8 {
                    if (hand_trumps & (1 << (self.trump * 8 + r))) != 0 {
                        if RANK_STRENGTH_TRUMP[r as usize] > winner_strength {
                            higher_trumps |= 1 << (self.trump * 8 + r);
                        }
                    }
                }
                if higher_trumps != 0 {
                    return higher_trumps;
                }
                // If cannot overcut, but have trumps, must play a trump (any trump? Rule says "sous-couper" is allowed if you cannot overcut?
                // Rule: "Si on ne peut pas surmonter, on doit quand même jouer atout (pisser/sous-couper).")
                return hand_trumps;
            } else {
                // Enemy winning with non-trump, we must cut with any trump.
                return hand_trumps;
            }
        }

        // 3. Cannot follow, cannot cut (or partner winning). Play anything.
        hand
    }

    // Helper to find who is currently winning the trick
    fn get_current_trick_winner(&self) -> u8 {
        let mut best_card = self.current_trick[self.trick_starter as usize];
        let mut _best_player = self.trick_starter;
        let lead_suit = best_card / 8;

        for i in 1..self.trick_size {
            let p = (self.trick_starter + i) % 4;
            let card = self.current_trick[p as usize];
            let _suit = card / 8;

            if self.is_card_better(card, best_card, lead_suit) {
                best_card = card;
                _best_player = p;
            }
        }
        best_card
    }

    fn get_current_trick_winner_player(&self) -> u8 {
        let mut best_card = self.current_trick[self.trick_starter as usize];
        let mut best_player = self.trick_starter;
        let lead_suit = best_card / 8;

        for i in 1..self.trick_size {
            let p = (self.trick_starter + i) % 4;
            let card = self.current_trick[p as usize];

            if self.is_card_better(card, best_card, lead_suit) {
                best_card = card;
                best_player = p;
            }
        }
        best_player
    }

    fn is_card_better(&self, new_card: u8, best_card: u8, _lead_suit: u8) -> bool {
        let new_suit = new_card / 8;
        let best_suit = best_card / 8;
        let new_rank = (new_card % 8) as usize;
        let best_rank = (best_card % 8) as usize;

        // 1. Trump beats non-trump
        if new_suit == self.trump && best_suit != self.trump {
            return true;
        }
        if best_suit == self.trump && new_suit != self.trump {
            return false;
        }

        // 2. Same suit comparison
        if new_suit == best_suit {
            if new_suit == self.trump {
                return RANK_STRENGTH_TRUMP[new_rank] > RANK_STRENGTH_TRUMP[best_rank];
            } else {
                return RANK_STRENGTH_NON_TRUMP[new_rank] > RANK_STRENGTH_NON_TRUMP[best_rank];
            }
        }

        // 3. Different suits, neither is trump.
        // If new_card follows lead suit and best_card doesn't (impossible if best_card is current winner), it wins.
        // But best_card IS the current winner, so it must be either trump or lead suit.
        // If new_card is not trump and not lead suit, it loses.
        false
    }

    /// Play a card (index 0-31)
    pub fn play_card(&mut self, card: u8) {
        // Check for Belote/Rebelote
        // Only if trump is valid (0-3)
        if self.trump < 4 {
            let suit = card / 8;
            if suit == self.trump {
                let rank = card % 8;
                // K=6, Q=5
                if rank == 5 || rank == 6 {
                    let team = (self.current_player % 2) as usize;
                    if !self.belote_scored[team] {
                        // Check if player holds the other card
                        let other_rank = if rank == 5 { 6 } else { 5 };
                        let other_card = self.trump * 8 + other_rank;
                        let hand = self.hands[self.current_player as usize];

                        if (hand & (1 << other_card)) != 0 {
                            // Has Belote!
                            self.points[team] += 20;
                            self.belote_scored[team] = true;
                        }
                    }
                }
            }
        }

        // Remove from hand
        self.hands[self.current_player as usize] &= !(1 << card);

        // Add to trick
        self.current_trick[self.current_player as usize] = card;
        self.trick_size += 1;

        if self.trick_size == 4 {
            self.resolve_trick();
        } else {
            self.current_player = (self.current_player + 1) % 4;
        }
    }

    fn resolve_trick(&mut self) {
        let winner = self.get_current_trick_winner_player();
        let winning_team = (winner % 2) as usize;

        let mut points = 0;
        for i in 0..4 {
            let c = self.current_trick[i];
            let s = c / 8;
            let r = (c % 8) as usize;
            if s == self.trump {
                points += POINTS_TRUMP[r];
            } else {
                points += POINTS_NON_TRUMP[r];
            }
        }

        // Dix de Der (10 points for last trick)
        // How to know if it's the last trick? Check if hands are empty.
        // Actually, simpler: we can track turn number or just check hands.
        // Since we modify hands in play_card, if hands[0] == 0 after this trick, it was the last one.
        // But we just removed the card. So if all hands are 0 now.
        if self.hands[0] == 0 && self.hands[1] == 0 && self.hands[2] == 0 && self.hands[3] == 0 {
            points += 10;
        }

        self.points[winning_team] += points;

        // Store last trick
        self.last_trick = self.current_trick;
        self.last_trick_starter = self.trick_starter;
        self.last_trick_winner = Some(winner);

        // Reset trick
        self.current_trick = [0xFF; 4];
        self.trick_size = 0;
        self.trick_starter = winner;
        self.current_player = winner;

        self.tricks_won[winning_team] += 1;

        // Capot Bonus (252 points total = 162 + 90 bonus)
        if self.tricks_won[winning_team] == 8 {
            self.points[winning_team] += 90;
        }
    }

    pub fn is_terminal(&self) -> bool {
        self.hands[0] == 0 && self.hands[1] == 0 && self.hands[2] == 0 && self.hands[3] == 0
    }

    pub fn __repr__(&self) -> String {
        format!(
            "PlayingState(trump={}, player={}, ns_points={}, ew_points={})",
            self.trump, self.current_player, self.points[0], self.points[1]
        )
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    // Helper to create card index
    fn card(suit: u8, rank: u8) -> u8 {
        suit * 8 + rank
    }

    #[test]
    fn test_points_counting() {
        let mut state = PlayingState::new(HEARTS); // Hearts is trump

        // Trick: J(Hearts/Trump), 9(Hearts/Trump), A(Hearts/Trump), 10(Spades/NoTrump)
        // Values: J=20, 9=14, A=11, 10=10. Total = 55.
        // Winner: J (Trump) -> Player 0

        state.hands[0] = 1 << card(HEARTS, 4); // J
        state.hands[1] = 1 << card(HEARTS, 2); // 9
        state.hands[2] = 1 << card(HEARTS, 7); // A
        state.hands[3] = 1 << card(SPADES, 3); // 10

        state.play_card(card(HEARTS, 4));
        state.play_card(card(HEARTS, 2));
        state.play_card(card(HEARTS, 7));
        state.play_card(card(SPADES, 3)); // 10 Spades

        assert_eq!(state.points[0], 65); // NS won (55 + 10 de der)
        assert_eq!(state.current_player, 0); // Player 0 won
    }

    #[test]
    fn test_belote_rebelote() {
        let mut state = PlayingState::new(HEARTS);
        // Player 0 has K and Q of Hearts
        state.hands[0] = (1 << card(HEARTS, 6)) | (1 << card(HEARTS, 5));

        // Play K
        state.play_card(card(HEARTS, 6));
        assert!(state.belote_scored[0]);
        assert_eq!(state.points[0], 20); // Immediate 20 points

        // Setup others
        state.play_card(card(CLUBS, 0));
        state.play_card(card(CLUBS, 1));
        state.play_card(card(CLUBS, 2));

        // Next turn, play Q
        // Trick resolution happens, points updated.
        // Assuming P0 won the first trick (K Trump vs Clubs)
        // P0 leads again.

        // Just verify initial belote trigger
    }

    #[test]
    fn test_capot_bonus() {
        let mut state = PlayingState::new(HEARTS);
        // Team 0 (NS) needs to win 8 tricks.
        // Hack: Manually set tricks_won to 7 and play last trick
        state.tricks_won[0] = 7;

        // Last trick
        state.hands[0] = 1 << card(HEARTS, 7); // A
        state.hands[1] = 1 << card(CLUBS, 0);
        state.hands[2] = 1 << card(CLUBS, 1);
        state.hands[3] = 1 << card(CLUBS, 2);

        state.play_card(card(HEARTS, 7));
        state.play_card(card(CLUBS, 0));
        state.play_card(card(CLUBS, 1));
        state.play_card(card(CLUBS, 2));

        // Capot: 252 points.
        // Points from trick: 11 (A)
        // 10 de der: 10
        // Capot bonus: 90
        // Total added: 111.
        // We track total points.
        // Let's assume points were 0 before (unrealistic for 7 tricks but valid for unit test check)
        // But check the delta or total logic.

        // If they had 0 points (impossible), they now have 11 + 10 + 90 = 111.
        // Wait, Capot implies they took ALL points.
        // If we hacked tricks_won=7, we didn't add points for first 7 tricks.
        // This test just checks if the +90 is applied and 10 de der.

        assert_eq!(state.tricks_won[0], 8);
        assert!(state.points[0] >= 111);
    }

    #[test]
    fn test_must_follow() {
        let mut state = PlayingState::new(HEARTS);
        state.trick_size = 1;
        state.trick_starter = 0;
        state.current_trick[0] = card(CLUBS, 7); // Ace Clubs led
        state.current_player = 1;

        // P1 has Clubs (Must follow) and Hearts (Trump)
        state.hands[1] = (1 << card(CLUBS, 0)) | (1 << card(HEARTS, 0));

        let legal = state.get_legal_moves();
        assert_eq!(legal, 1 << card(CLUBS, 0)); // Must play Club
    }

    #[test]
    fn test_must_cut() {
        let mut state = PlayingState::new(HEARTS);
        state.trick_size = 1;
        state.trick_starter = 0;
        state.current_trick[0] = card(CLUBS, 7); // Ace Clubs led
        state.current_player = 1;

        // P1 has NO Clubs, but has Hearts (Trump) and Spades
        state.hands[1] = (1 << card(SPADES, 0)) | (1 << card(HEARTS, 0));

        // Partner (P3) is not winning (P0 is winning)

        let legal = state.get_legal_moves();
        assert_eq!(legal, 1 << card(HEARTS, 0)); // Must cut
    }

    #[test]
    fn test_must_overcut() {
        let mut state = PlayingState::new(HEARTS);
        state.trick_size = 2;
        state.trick_starter = 0;
        state.current_trick[0] = card(CLUBS, 7); // P0: A Clubs
        state.current_trick[1] = card(HEARTS, 3); // P1: 10 Hearts (Trump) - CUT
        state.current_player = 2; // P2 (Partner of P0)

        // P2 has no Clubs.
        // P2 has Hearts: 9 (14 pts) and Q (3 pts).
        // P1 is winning with 10 Trump (Strength 4).
        // 9 Trump (Strength 6) > 10 Trump.
        // Q Trump (Strength 2) < 10 Trump.

        state.hands[2] = (1 << card(HEARTS, 2)) | (1 << card(HEARTS, 5));

        let legal = state.get_legal_moves();
        // Must overcut with 9. Q is not high enough.
        // Wait, if can overcut, must overcut.
        // Only 9 is legal.
        // What if I can't overcut? (Say I only had Q). Then play Q.

        assert_eq!(legal, 1 << card(HEARTS, 2)); // 9 Hearts
    }

    #[test]
    fn test_partner_master_no_cut() {
        let mut state = PlayingState::new(HEARTS);
        state.trick_size = 2;
        state.trick_starter = 0;
        state.current_trick[0] = card(CLUBS, 7); // P0: A Clubs (Master)
        state.current_trick[1] = card(CLUBS, 0); // P1: 7 Clubs
        state.current_player = 2; // P2 (Partner of P0)

        // P2 has no Clubs.
        // P2 has Hearts (Trump).
        // Partner (0) is winning.

        state.hands[2] = (1 << card(SPADES, 0)) | (1 << card(HEARTS, 0));

        let legal = state.get_legal_moves();
        // Not forced to cut because partner is winning. Can play anything.
        assert_eq!(legal, state.hands[2]);
    }

    // Additional Rules Tests (Added for verification)

    // Helper to create card index: Suit * 8 + Rank
    fn c(suit: u8, rank: u8) -> u32 {
        1 << (suit * 8 + rank)
    }

    fn idx(suit: u8, rank: u8) -> u8 {
        suit * 8 + rank
    }

    #[test]
    fn test_lead_any_card() {
        let mut state = PlayingState::new(HEARTS); // Trump Hearts
        state.current_player = 0;

        // P0 has: 7H, 8H (Trump), 7S, 8S, 7C, 8C
        state.hands[0] =
            c(HEARTS, 0) | c(HEARTS, 1) | c(SPADES, 0) | c(SPADES, 1) | c(CLUBS, 0) | c(CLUBS, 1);

        // It's the lead (trick_size = 0)
        assert_eq!(state.trick_size, 0);

        let legal = state.get_legal_moves();

        // Should be equal to hand
        assert_eq!(
            legal, state.hands[0],
            "Lead player receives full hand as legal moves"
        );
    }

    #[test]
    fn test_must_follow_suit_full() {
        let mut state = PlayingState::new(HEARTS);

        // P0 leads 7 Spades
        state.current_player = 0;
        state.trick_starter = 0;
        state.hands[0] = c(SPADES, 0);
        state.play_card(idx(SPADES, 0));

        assert_eq!(state.current_player, 1);

        // P1 has 8S (Follow), 7H (Trump), 7C (Other)
        state.hands[1] = c(SPADES, 1) | c(HEARTS, 0) | c(CLUBS, 0);

        let legal = state.get_legal_moves();

        // Must play Spades (8S)
        assert_eq!(legal, c(SPADES, 1));
    }

    #[test]
    fn test_must_follow_multiple_choices_full() {
        let mut state = PlayingState::new(HEARTS);

        // P0 leads 7 Spades
        state.trick_starter = 0;
        state.current_player = 0;
        state.hands[0] = c(SPADES, 0);
        state.play_card(idx(SPADES, 0));

        // P1 has 8S, 9S and other stuff
        state.hands[1] = c(SPADES, 1) | c(SPADES, 2) | c(CLUBS, 0);

        let legal = state.get_legal_moves();

        // Must play 8S or 9S
        assert_eq!(legal, c(SPADES, 1) | c(SPADES, 2));
    }

    #[test]
    fn test_must_cut_if_void_full() {
        let mut state = PlayingState::new(HEARTS);

        // P0 leads 7 Spades
        state.trick_starter = 0;
        state.current_player = 0;
        state.hands[0] = c(SPADES, 0);
        state.play_card(idx(SPADES, 0));

        // P1 has NO Spades, but has Trump (7H) and Club
        state.hands[1] = c(HEARTS, 0) | c(CLUBS, 0);

        let legal = state.get_legal_moves();

        // Must cut (Play Trump 7H)
        assert_eq!(legal, c(HEARTS, 0));
    }

    #[test]
    fn test_play_any_if_void_and_no_trump_full() {
        let mut state = PlayingState::new(HEARTS);

        // P0 leads 7 Spades
        state.trick_starter = 0;
        state.current_player = 0;
        state.hands[0] = c(SPADES, 0);
        state.play_card(idx(SPADES, 0));

        // P1 has NO Spades, NO Trump, only Clubs/Diamonds
        state.hands[1] = c(CLUBS, 0) | c(DIAMONDS, 0);

        let legal = state.get_legal_moves();

        // Can play anything (Club or Diamond)
        assert_eq!(legal, c(CLUBS, 0) | c(DIAMONDS, 0));
    }

    #[test]
    fn test_overcut_mandatory_full() {
        let mut state = PlayingState::new(HEARTS);

        // P0 leads 7 Spades
        state.play_card(idx(SPADES, 0)); // P0

        // P1 Cuts with 10 Hearts (Trump)
        state.hands[1] = c(HEARTS, 3); // 10H
        state.play_card(idx(HEARTS, 3));

        // P2 (Partner of P0) has no Spades.
        // Has 9H (Val 14, > 10H) and 7H (Val 0, < 10H).
        // Must overcut if possible.
        state.hands[2] = c(HEARTS, 2) | c(HEARTS, 0);

        let legal = state.get_legal_moves();

        // Must play 9H (Overcut)
        assert_eq!(legal, c(HEARTS, 2));
    }

    #[test]
    fn test_cut_if_cannot_overcut_full() {
        let mut state = PlayingState::new(HEARTS);

        state.play_card(idx(SPADES, 0)); // P0

        // P1 Cuts with 10H (Val 10)
        state.hands[1] = c(HEARTS, 3);
        state.play_card(idx(HEARTS, 3));

        // P2 has no Spades.
        // Has only 7H (Val 0) and 8H (Val 0). Both lower than 10H.
        // Cannot overcut. But must still play trump ("pisser" / under-cut).
        state.hands[2] = c(HEARTS, 0) | c(HEARTS, 1) | c(CLUBS, 0);

        let legal = state.get_legal_moves();

        // Must play 7H or 8H. Cannot play Club.
        assert_eq!(legal, c(HEARTS, 0) | c(HEARTS, 1));
    }

    #[test]
    fn test_trump_lead_must_go_higher_full() {
        let mut state = PlayingState::new(HEARTS);

        // P0 leads 10 Hearts (Trump)
        state.play_card(idx(HEARTS, 3));

        // P1 has 9H (Strength 6) and QH (Strength 2).
        // 10H (Strength 4).
        // Must play higher if possible -> 9H.
        state.hands[1] = c(HEARTS, 2) | c(HEARTS, 5);

        let legal = state.get_legal_moves();

        assert_eq!(legal, c(HEARTS, 2));
    }

    #[test]
    fn test_trump_lead_play_any_trump_if_cannot_go_higher_full() {
        let mut state = PlayingState::new(HEARTS);

        // P0 leads 9 Hearts (Master Trump, Strength 6)
        state.play_card(idx(HEARTS, 2));

        // P1 has 10H (Strength 4) and QH (Strength 2).
        // Cannot beat 9H. Must follow.
        state.hands[1] = c(HEARTS, 3) | c(HEARTS, 5);

        let legal = state.get_legal_moves();

        assert_eq!(legal, c(HEARTS, 3) | c(HEARTS, 5));
    }
}
