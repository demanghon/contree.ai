//! Contree bidding rules implementation.

use crate::gameplay::playing::PlayingState;
use pyo3::prelude::*;

/// Represents a Contree bid.
#[pyclass]
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub struct Bid {
    /// Bid value in points (e.g., 80, 90, ... 160).
    #[pyo3(get, set)]
    pub value: u8,
    /// Trump suit: 0=Clubs,1=Spades,2=Hearts,3=Clubs,4=NoTrump,5=AllTrump (same encoding as PlayingState).
    #[pyo3(get, set)]
    pub trump: u8,
}

#[pymethods]
impl Bid {
    /// Create a new bid.
    #[new]
    pub fn new(value: u8, trump: u8) -> Self {
        Self { value, trump }
    }
}

/// State of the bidding phase.
#[pyclass]
#[derive(Debug, Clone)]
pub struct BiddingState {
    #[pyo3(get)]
    pub history: Vec<Option<Bid>>, // None = Pass
    #[pyo3(get)]
    pub current_player: u8,
    #[pyo3(get)]
    pub contract: Option<Bid>,
    #[pyo3(get)]
    pub contract_owner: Option<u8>,
    #[pyo3(get)]
    pub coinche_level: u8, // 0=None, 1=Coinche, 2=Surcoinche
    #[pyo3(get)]
    pub consecutive_passes: u8,
}

impl BiddingState {
    pub fn new(dealer: u8) -> Self {
        Self {
            history: Vec::new(),
            current_player: (dealer + 1) % 4,
            contract: None,
            contract_owner: None,
            coinche_level: 0,
            consecutive_passes: 0,
        }
    }

    pub fn apply_bid(&mut self, bid: Option<Bid>) -> Result<(), &'static str> {
        match bid {
            None => {
                // Pass
                self.consecutive_passes += 1;
            }
            Some(b) => {
                // Validate bid
                if self.coinche_level > 0 {
                    return Err("Cannot bid after coinche");
                }
                if let Some(current) = self.contract {
                    if !beats(Some(current), b) {
                        return Err("Bid does not beat current contract");
                    }
                }
                self.contract = Some(b);
                self.contract_owner = Some(self.current_player);
                self.consecutive_passes = 0;
            }
        }
        self.history.push(bid);
        self.current_player = (self.current_player + 1) % 4;
        Ok(())
    }

    pub fn is_finished(&self) -> bool {
        // Auction ends if:
        // 1. 3 consecutive passes AFTER a contract is established.
        // 2. 4 consecutive passes at the START (everyone passes).
        // 3. Surcoinche happened (not implemented fully here yet, but standard rule).
        if self.contract.is_some() {
            self.consecutive_passes >= 3
        } else {
            self.consecutive_passes >= 4
        }
    }
}

/// Returns the list of legal bids given the current highest bid (or `None` if no bid yet).
/// The ordering follows Contree rules: a higher value always beats a lower one;
/// for equal values the suit order is Clubs < Diamonds < Hearts < Spades < AllTrump < NoTrump.
pub fn legal_bids(current: Option<Bid>) -> Vec<Bid> {
    // All possible values and suits.
    const VALUES: [u8; 9] = [80, 90, 100, 110, 120, 130, 140, 150, 160];
    const SUITS: [u8; 6] = [0, 1, 2, 3, 4, 5]; // same encoding as PlayingState constants.

    let mut bids = Vec::new();
    // Pass is always allowed – represented by the empty vector (caller can add a pass option).
    match current {
        None => {
            // First player can bid any value/suit.
            for &v in VALUES.iter() {
                for &s in SUITS.iter() {
                    bids.push(Bid::new(v, s));
                }
            }
        }
        Some(cur) => {
            // Higher value bids.
            for &v in VALUES.iter() {
                if v > cur.value {
                    for &s in SUITS.iter() {
                        bids.push(Bid::new(v, s));
                    }
                } else if v == cur.value {
                    // Same value, higher suit.
                    for &s in SUITS.iter() {
                        if s > cur.trump {
                            bids.push(Bid::new(v, s));
                        }
                    }
                }
            }
        }
    }
    bids
}

/// Helper to check if a given bid beats the current one.
pub fn beats(current: Option<Bid>, candidate: Bid) -> bool {
    match current {
        None => true,
        Some(cur) => {
            if candidate.value > cur.value {
                true
            } else if candidate.value == cur.value && candidate.trump > cur.trump {
                true
            } else {
                false
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_initial_legal_bids() {
        // No current bid -> all bids are legal.
        let bids = legal_bids(None);
        // 9 values * 6 suits = 54 possible bids.
        assert_eq!(bids.len(), 54);
        // First bid should be the lowest value and suit (80, Clubs).
        assert_eq!(bids[0], Bid::new(80, 0));
    }

    #[test]
    fn test_higher_value_beats() {
        let cur = Some(Bid::new(100, 2)); // 100 Hearts
                                          // Any bid with value > 100 should be legal.
        let higher = legal_bids(cur);
        for b in higher.iter() {
            assert!(b.value >= 100);
            if b.value == 100 {
                assert!(b.trump > 2);
            }
        }
        // No bid with value == 100 should appear because suit 2 is not higher than itself.
        assert!(!higher.iter().any(|b| b.value == 100 && b.trump <= 2));
    }

    #[test]
    fn test_same_value_higher_suit() {
        let cur = Some(Bid::new(120, 1)); // 120 Spades
        let bids = legal_bids(cur);
        // Should contain same value with trump > 1.
        assert!(bids.iter().any(|b| b.value == 120 && b.trump > 1));
        // Should not contain same value with trump <= 1.
        assert!(!bids.iter().any(|b| b.value == 120 && b.trump <= 1));
    }

    #[test]
    fn test_beats_function() {
        let cur = Some(Bid::new(130, 3));
        assert!(beats(cur, Bid::new(140, 0)));
        assert!(!beats(cur, Bid::new(130, 2)));
        assert!(beats(cur, Bid::new(130, 4)));
    }

    #[test]
    fn test_bidding_scenario() {
        // Dealer is 3, so P0 starts.
        let mut state = BiddingState::new(3);
        assert_eq!(state.current_player, 0);

        // P0 Passes
        assert!(state.apply_bid(None).is_ok());
        assert_eq!(state.consecutive_passes, 1);
        assert_eq!(state.current_player, 1);

        // P1 Bids 80 Hearts
        let b1 = Bid::new(80, 2);
        assert!(state.apply_bid(Some(b1)).is_ok());
        assert_eq!(state.contract, Some(b1));
        assert_eq!(state.contract_owner, Some(1));
        assert_eq!(state.consecutive_passes, 0);

        // P2 Passes
        assert!(state.apply_bid(None).is_ok());
        // P3 Passes
        assert!(state.apply_bid(None).is_ok());

        // Not finished yet (only 2 passes after bid)
        assert!(!state.is_finished());

        // P0 Passes (3rd pass)
        assert!(state.apply_bid(None).is_ok());

        // Now finished
        assert!(state.is_finished());
        assert_eq!(state.contract.unwrap().value, 80);
    }

    #[test]
    fn test_capot_bid_rejection() {
        let mut state = BiddingState::new(0);
        let b1 = Bid::new(100, 0);
        state.apply_bid(Some(b1)).unwrap();

        // Try to bid lower (90) - Should fail
        let b2 = Bid::new(90, 0);
        assert!(state.apply_bid(Some(b2)).is_err());

        // Try to bid same value same suit - Should fail
        let b3 = Bid::new(100, 0);
        assert!(state.apply_bid(Some(b3)).is_err());
    }
}
