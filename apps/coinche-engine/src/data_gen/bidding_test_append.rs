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
        hand |= card(HEARTS, 4); // Valet
        hand |= card(HEARTS, 2); // 9
        hand |= card(SPADES, 7); // As

        let score = evaluate_hand_potential(hand, trump);
        assert!(score >= 45);
    }

    #[test]
    fn test_hand_potential_weak() {
        // Just small trumps and small cards
        // 7, 8 Trumps (0), 7, 8 Spades (0), 7, 8 Clubs (0)
        let trump = HEARTS;
        let mut hand = 0;
        hand |= card(HEARTS, 0);
        hand |= card(HEARTS, 1);
        hand |= card(SPADES, 0);
        hand |= card(SPADES, 1);

        let score = evaluate_hand_potential(hand, trump);
        assert!(score < 40);
        assert_eq!(score, 0);
    }

    #[test]
    fn test_hand_potential_belote() {
        // K + Q Trumps = 20
        let trump = HEARTS;
        let mut hand = 0;
        hand |= card(HEARTS, 6); // K
        hand |= card(HEARTS, 5); // Q

        let score = evaluate_hand_potential(hand, trump);
        assert_eq!(score, 20);
    }
}
