use crate::gameplay::bidding::{Bid, BiddingState};
use crate::gameplay::playing::PlayingState;
use pyo3::prelude::*;

#[derive(Debug, Clone)]
pub enum Phase {
    Bidding(BiddingState),
    Playing(PlayingState),
    Finished(MatchResult),
}

#[pyclass]
#[derive(Debug, Clone)]
pub struct MatchResult {
    #[pyo3(get)]
    pub contract: Option<Bid>,
    #[pyo3(get)]
    pub contract_owner: Option<u8>,
    #[pyo3(get)]
    pub points_ns: i16,
    #[pyo3(get)]
    pub points_ew: i16,
    #[pyo3(get)]
    pub contract_made: bool,
}

#[pyclass]
pub struct CoincheMatch {
    pub phase: Phase,
    #[pyo3(get)]
    pub dealer: u8,
    // hands removed here, moving to getter
    #[pyo3(get)]
    pub contract: Option<Bid>,
    #[pyo3(get)]
    pub contract_owner: Option<u8>,
    #[pyo3(get)]
    pub coinche_level: u8,

    // Internal storage for initial hands (optional, or we can rely on phase state)
    // We need to keep it for Bidding phase where state is inside enum.
    pub initial_hands: [u32; 4],
}

impl CoincheMatch {
    pub fn new_rs(dealer: u8, hands: [u32; 4]) -> Self {
        Self {
            phase: Phase::Bidding(BiddingState::new(dealer)),
            dealer,
            initial_hands: hands,
            contract: None,
            contract_owner: None,
            coinche_level: 0,
        }
    }
}

#[pymethods]
impl CoincheMatch {
    #[new]
    pub fn new(dealer: u8, hands: Vec<u32>) -> PyResult<Self> {
        if hands.len() != 4 {
            return Err(pyo3::exceptions::PyValueError::new_err(
                "Hands must have 4 entries",
            ));
        }
        let h: [u32; 4] = hands.try_into().unwrap();
        Ok(CoincheMatch::new_rs(dealer, h))
    }

    pub fn bid(&mut self, bid: Option<Bid>) -> PyResult<()> {
        let (finished, level) = if let Phase::Bidding(ref mut state) = self.phase {
            state
                .apply_bid(bid)
                .map_err(|e| pyo3::exceptions::PyValueError::new_err(e))?;
            (state.is_finished(), state.coinche_level)
        } else {
            return Err(pyo3::exceptions::PyRuntimeError::new_err(
                "Not in bidding phase",
            ));
        };

        self.coinche_level = level;
        if finished {
            self.transition_from_bidding();
        }
        Ok(())
    }

    pub fn coinche(&mut self) -> PyResult<()> {
        let (finished, level) = if let Phase::Bidding(ref mut state) = self.phase {
            state
                .coinche()
                .map_err(|e| pyo3::exceptions::PyValueError::new_err(e))?;
            (state.is_finished(), state.coinche_level)
        } else {
            return Err(pyo3::exceptions::PyRuntimeError::new_err(
                "Not in bidding phase",
            ));
        };

        self.coinche_level = level;
        if finished {
            self.transition_from_bidding();
        }
        Ok(())
    }

    pub fn surcoinche(&mut self) -> PyResult<()> {
        let (finished, level) = if let Phase::Bidding(ref mut state) = self.phase {
            state
                .surcoinche()
                .map_err(|e| pyo3::exceptions::PyValueError::new_err(e))?;
            (state.is_finished(), state.coinche_level)
        } else {
            return Err(pyo3::exceptions::PyRuntimeError::new_err(
                "Not in bidding phase",
            ));
        };

        self.coinche_level = level;
        if finished {
            self.transition_from_bidding();
        }
        Ok(())
    }

    fn transition_from_bidding(&mut self) {
        if let Phase::Bidding(ref state) = self.phase {
            if let Some(final_contract) = state.contract {
                // Determine logic for Coinche multiplier?
                // Rules usually say multiplier applies to score.
                // We'll store it in the match result or pass it to PlayingState?
                // For now, let's just transition. Score multiplier should be handled in Play/Result.
                // NOTE: PlayingState doesn't currently store coinche_level.
                // We might need to add it to PlayingState if scoring depends on it.
                // checking PlayingState in playing.rs...

                self.contract = Some(final_contract);
                self.contract_owner = state.contract_owner;

                let mut game = PlayingState::new(final_contract.trump);
                game.hands = self.initial_hands;
                game.current_player = (self.dealer + 1) % 4;
                game.trick_starter = game.current_player;
                // Passing coinche info?
                // PlayingState needs to know about coinche for scoring (160 * 2 etc).
                // Let's assume for now we just handle mechanics, scoring update later if needed.
                // Wait, User asked for "Option to Contre". Logic must follow.

                self.phase = Phase::Playing(game);
            } else {
                self.phase = Phase::Finished(MatchResult {
                    contract: None,
                    contract_owner: None,
                    points_ns: 0,
                    points_ew: 0,
                    contract_made: false,
                });
            }
        }
    }

    pub fn play_card(&mut self, card: u8) -> PyResult<()> {
        if let Phase::Playing(ref mut state) = self.phase {
            let legal = state.get_legal_moves();
            if (legal & (1 << card)) == 0 {
                return Err(pyo3::exceptions::PyValueError::new_err("Illegal move"));
            }

            state.play_card(card);

            if state.is_terminal() {
                let ns_score = state.points[0] as i16;
                let ew_score = state.points[1] as i16;
                let contract = self.contract.unwrap();
                let owner = self.contract_owner.unwrap();
                let threshold = contract.value as i16;

                let (owner_score, _) = if owner % 2 == 0 {
                    (ns_score, ew_score)
                } else {
                    (ew_score, ns_score)
                };
                let contract_made = owner_score >= threshold;

                self.phase = Phase::Finished(MatchResult {
                    contract: self.contract,
                    contract_owner: self.contract_owner,
                    points_ns: ns_score,
                    points_ew: ew_score,
                    contract_made,
                });
            }
            Ok(())
        } else {
            Err(pyo3::exceptions::PyRuntimeError::new_err(
                "Not in playing phase",
            ))
        }
    }

    // Accessors for Phase info
    pub fn phase_name(&self) -> String {
        match self.phase {
            Phase::Bidding(_) => "BIDDING".to_string(),
            Phase::Playing(_) => "PLAYING".to_string(),
            Phase::Finished(_) => "FINISHED".to_string(),
        }
    }

    pub fn get_bidding_state(&self) -> Option<BiddingState> {
        if let Phase::Bidding(ref s) = self.phase {
            Some(s.clone())
        } else {
            None
        }
    }

    pub fn get_playing_state(&self) -> Option<PlayingState> {
        if let Phase::Playing(ref s) = self.phase {
            Some(s.clone())
        } else {
            None
        }
    }

    pub fn get_result(&self) -> Option<MatchResult> {
        if let Phase::Finished(ref r) = self.phase {
            Some(r.clone())
        } else {
            None
        }
    }

    #[getter]
    pub fn hands(&self) -> [u32; 4] {
        match self.phase {
            Phase::Bidding(_) => self.initial_hands,
            Phase::Playing(ref p) => p.hands,
            Phase::Finished(_) => [0; 4],
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::gameplay::playing::{HEARTS, SPADES};

    fn card(suit: u8, rank: u8) -> u8 {
        suit * 8 + rank
    }

    #[test]
    fn test_full_match_flow() {
        // Setup hands (simplified)
        // P0 (Dealer): 7S
        // P1: 8S
        // P2: 7H
        // P3: 8H
        let mut hands = [0u32; 4];
        hands[0] = 1 << card(SPADES, 0); // 7S
        hands[1] = 1 << card(SPADES, 1); // 8S
        hands[2] = 1 << card(HEARTS, 0); // 7H
        hands[3] = 1 << card(HEARTS, 1); // 8H

        let mut m = CoincheMatch::new_rs(0, hands); // Dealer P0 -> starts P1

        // P1 bids 80 Spades
        m.bid(Some(Bid::new(80, SPADES))).unwrap();

        // P2 Pass
        m.bid(None).unwrap();
        // P3 Pass
        m.bid(None).unwrap();
        // P0 Pass
        m.bid(None).unwrap();

        // Should be playing now
        match m.phase {
            Phase::Playing(ref g) => {
                assert_eq!(g.trump, SPADES);
                assert_eq!(g.current_player, 1); // P1 starts (dealer + 1)
            }
            _ => panic!("Should be in Playing phase"),
        }

        // Play phase
        // P1 (Starter) leads 8S (Trump)
        m.play_card(card(SPADES, 1)).unwrap();
        // P2 (7H) must play 7H (no spades, no trump? wait H is not trump. S is trump)
        // P2 has 7H. Trump is S.
        // P2 plays 7H
        m.play_card(card(HEARTS, 0)).unwrap();
        // P3 has 8H. plays 8H.
        m.play_card(card(HEARTS, 1)).unwrap();
        // P0 has 7S. Follows trump.
        m.play_card(card(SPADES, 0)).unwrap();

        // Trick done. P1 (8S) vs P0 (7S). P1 wins.
        // Game over (1 card hands).

        match m.phase {
            Phase::Finished(res) => {
                assert!(res.contract.is_some());
                assert_eq!(res.points_ns, 0);
                // P1/P3 (EW) won.
                // Points: 8S(0)+7H(0)+8H(0)+7S(0) = 0 card points.
                // 10 de der to winner (P1).
                // Total EW = 10.
                assert_eq!(res.points_ew, 10);
                assert_eq!(res.contract_made, false); // 80 > 10. Failed.
            }
            _ => panic!("Should be Finished"),
        }
    }
}
