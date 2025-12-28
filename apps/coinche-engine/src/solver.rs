use crate::gameplay::playing::PlayingState;
use std::cmp::{max, min};
use std::collections::HashMap;

const INF: i16 = 1000;

use lazy_static::lazy_static;
use rand::rngs::StdRng;
use rand::{Rng, SeedableRng};

// Zobrist Keys
struct ZobristTable {
    // [player][card_index]
    hand: [[u64; 32]; 4],
    // [player][card_index] - Cards currently in trick
    trick: [[u64; 32]; 4],
    // [player] - Whose turn
    turn: [u64; 4],
    // [team] - If team has won at least one trick (makes opponent Capot impossible)
    has_won_trick: [u64; 2],
}

impl ZobristTable {
    fn new() -> Self {
        let mut rng = StdRng::seed_from_u64(12345); // Fixed seed for reproducibility
        let mut table = ZobristTable {
            hand: [[0; 32]; 4],
            trick: [[0; 32]; 4],
            turn: [0; 4],
            has_won_trick: [0; 2],
        };

        for p in 0..4 {
            for c in 0..32 {
                table.hand[p][c] = rng.gen();
                table.trick[p][c] = rng.gen();
            }
            table.turn[p] = rng.gen();
        }
        table.has_won_trick[0] = rng.gen();
        table.has_won_trick[1] = rng.gen();
        table
    }
}

use std::sync::atomic::{AtomicU64, AtomicUsize, Ordering};

lazy_static! {
    static ref ZOBRIST: ZobristTable = ZobristTable::new();
}

static TOTAL_NODES: AtomicU64 = AtomicU64::new(0);
static TT_HITS: AtomicU64 = AtomicU64::new(0);
static HAND_COUNT: AtomicUsize = AtomicUsize::new(0);

// Fixed-size TT
const TT_SIZE: usize = 1 << 20; // 1 Million entries ~ 16MB
const TT_MASK: u64 = (TT_SIZE as u64) - 1;

#[derive(Clone, Copy)]
struct TTEntry {
    key: u64, // For collision detection
    score: i16,
    best_move: u8,
    flag: u8,
    depth: u8, // Added for Iterative Deepening
}

impl Default for TTEntry {
    fn default() -> Self {
        TTEntry {
            key: 0,
            score: 0,
            best_move: 0xFF,
            flag: 0,
            depth: 0, // Default depth
        }
    }
}

// Helper to check if we are solving the first hand (for debug stats)
fn is_first_hand() -> bool {
    HAND_COUNT.load(Ordering::Relaxed) == 0
}

// Optimized Zobrist Hash using bit iteration
fn compute_zobrist_hash(state: &PlayingState) -> u64 {
    let mut h: u64 = 0;

    // Hands - Iterate only set bits
    for p in 0..4 {
        let mut hand = state.hands[p];
        while hand != 0 {
            let i = hand.trailing_zeros();
            h ^= ZOBRIST.hand[p][i as usize];
            hand &= !(1 << i);
        }
    }

    // Current Trick - Sparse (0-3 cards usually) - Loop is fine or unrolled
    for p in 0..4 {
        let card = state.current_trick[p];
        if card != 0xFF {
            h ^= ZOBRIST.trick[p][card as usize];
        }
    }

    // Turn
    h ^= ZOBRIST.turn[state.current_player as usize];

    // Capot Potential
    if state.tricks_won[0] > 0 {
        h ^= ZOBRIST.has_won_trick[0];
    }
    if state.tricks_won[1] > 0 {
        h ^= ZOBRIST.has_won_trick[1];
    }

    h
}

// Heuristic Evaluation
// Returns estimated final score delta for Team 0 (NS) relative to current points?
// No, minimax returns absolute score for Team 0.
// So heuristic should return: Team0_Points + Estimate(Team0_Future)
// But since we use score normalization (relative to current),
// we want: Estimate(Team0_Future) - Estimate(Team1_Future)?
// Actually, standard minimax returns the leaf value.
// If we cut off, we return static evaluation of the state.
// Static Eval = state.points[0] + MaterialDifference?
// Coinche is zero-sum (total points fixed ~162).
// So MAXimizing Player 0 wants to maximize Pts0. MINimizing Player 1 wants to minimize Pts0.
// Eval = state.points[0] + (Material0 / (Material0 + Material1)) * RemainingPoints?
// Simpler: Eval = state.points[0] + MaterialHeuristic(Team0) - MaterialHeuristic(Team1)?
// Let's use a weighted material sum.
fn evaluate_state(state: &PlayingState) -> i16 {
    let current_score = state.points[0] as i32;
    let opponent_score = state.points[1] as i32;

    // Total points in a standard game is 162 (excluding Belote)
    // Remaining points to fight for
    let remaining_points = 162 - current_score - opponent_score;

    if remaining_points <= 0 {
        return current_score as i16;
    }

    let mut strength0: i32 = 0;
    let mut strength1: i32 = 0;

    let trump = state.trump;

    for p in 0..4 {
        let mut hand = state.hands[p];
        let is_team0 = p % 2 == 0;

        while hand != 0 {
            let c = hand.trailing_zeros() as u8;
            hand &= !(1 << c);

            let s = c / 8;
            let r = (c % 8) as usize;

            let val;
            let control;

            if s == trump {
                val = crate::gameplay::playing::POINTS_TRUMP[r] as i32;
                control = match r {
                    4 => 50, // J
                    2 => 35, // 9
                    7 => 25, // A
                    3 => 20, // 10
                    6 => 15, // K
                    5 => 10, // Q
                    _ => 0,
                };
            } else {
                val = crate::gameplay::playing::POINTS_NON_TRUMP[r] as i32;
                control = match r {
                    7 => 30, // A
                    3 => 20, // 10
                    6 => 10, // K
                    _ => 0,
                };
            }

            // Add to respective team's strength
            if is_team0 {
                strength0 += val + control;
            } else {
                strength1 += val + control;
            }
        }
    }

    // Calculate expected additional points based on strength ratio
    let total_strength = strength0 + strength1;
    let estimated_future = if total_strength > 0 {
        (remaining_points * strength0) / total_strength
    } else {
        remaining_points / 2 // Fallback if no cards valuable (unlikely)
    };

    (current_score + estimated_future) as i16
}

// Iterative Deepening Solve
pub fn solve(state: &PlayingState, generate_graph: bool) -> (i16, u8) {
    let mut tt = vec![TTEntry::default(); TT_SIZE];

    let is_first = HAND_COUNT.fetch_add(1, Ordering::Relaxed) == 0;
    if is_first {
        TOTAL_NODES.store(0, Ordering::Relaxed);
        TT_HITS.store(0, Ordering::Relaxed);
    }

    let hash = compute_zobrist_hash(state);

    // Iterative Deepening
    // Max depth = remaining cards in hand?
    // state.hands[0].count_ones() is cards per player.
    // Total depth = 32? No, 8 tricks. Minimax depth is usually counted in ply (player moves).
    // 8 tricks * 4 players = 32 ply max.

    let cards_left = state.hands[state.current_player as usize].count_ones() as u8;
    let max_depth = min(cards_left * 4, 8); // Depth 8 (2 tricks) for speed

    let mut best_score = 0;
    let mut best_move = 0xFF;

    // We use a small window or full window? Full window for now.

    for depth in 1..=max_depth {
        let (score, mv) = minimax(state, hash, -INF, INF, &mut tt, depth, is_first);
        best_score = score;
        best_move = mv;

        // Timer check could go here to abort early
    }

    if is_first {
        let nodes = TOTAL_NODES.load(Ordering::Relaxed);
        let hits = TT_HITS.load(Ordering::Relaxed);
        // debug print
    }

    (best_score, best_move)
}

/*
fn generate_dot_file(root_state: &PlayingState, tt: &HashMap<u64, TTEntry>) {
    // ... (content commented out for now as it needs update for Vec TT and Zobrist)
}
*/

fn minimax(
    state: &PlayingState,
    hash: u64,
    mut alpha: i16,
    mut beta: i16,
    tt: &mut [TTEntry],
    depth: u8,
    debug: bool,
) -> (i16, u8) {
    if debug {
        TOTAL_NODES.fetch_add(1, Ordering::Relaxed);
    }
    if state.is_terminal() {
        return (state.points[0] as i16, 0xFF);
    }
    if depth == 0 {
        return (evaluate_state(state), 0xFF);
    }

    // Score Normalization
    let current_points = state.points[0] as i16;
    let alpha_norm = alpha.saturating_sub(current_points);
    let beta_norm = beta.saturating_sub(current_points);

    // 1. TT Lookup
    let tt_idx = (hash & TT_MASK) as usize;
    let entry = tt[tt_idx];

    if entry.key == hash && entry.depth >= depth {
        // Only use if entry is from a deeper or equal search
        if debug {
            TT_HITS.fetch_add(1, Ordering::Relaxed);
        }

        if entry.flag == 0 {
            // Exact score
            return (entry.score + current_points, entry.best_move);
        } else if entry.flag == 1 {
            // Lowerbound
            if entry.score >= beta_norm {
                return (entry.score + current_points, entry.best_move);
            }
            alpha = max(alpha, entry.score + current_points);
        } else if entry.flag == 2 {
            // Upperbound
            if entry.score <= alpha_norm {
                return (entry.score + current_points, entry.best_move);
            }
            beta = min(beta, entry.score + current_points);
        }
        if alpha >= beta {
            return (entry.score + current_points, entry.best_move);
        }
    }

    let legal_moves_mask = state.get_legal_moves();
    let mut best_move = 0xFF;
    let is_maximizing = state.current_player % 2 == 0;

    let mut moves = Vec::with_capacity(8);
    for i in 0..32 {
        if (legal_moves_mask & (1 << i)) != 0 {
            moves.push(i as u8);
        }
    }

    moves.sort_by(|&a, &b| {
        if entry.key == hash && a == entry.best_move {
            return std::cmp::Ordering::Less;
        }
        if entry.key == hash && b == entry.best_move {
            return std::cmp::Ordering::Greater;
        }

        let suit_a = a / 8;
        let suit_b = b / 8;
        let rank_a = (a % 8) as usize;
        let rank_b = (b % 8) as usize;
        let is_trump_a = suit_a == state.trump;
        let is_trump_b = suit_b == state.trump;

        if is_trump_a && !is_trump_b {
            return std::cmp::Ordering::Less;
        }
        if !is_trump_a && is_trump_b {
            return std::cmp::Ordering::Greater;
        }

        let str_a = if is_trump_a {
            crate::gameplay::playing::RANK_STRENGTH_TRUMP[rank_a]
        } else {
            crate::gameplay::playing::RANK_STRENGTH_NON_TRUMP[rank_a]
        };
        let str_b = if is_trump_b {
            crate::gameplay::playing::RANK_STRENGTH_TRUMP[rank_b]
        } else {
            crate::gameplay::playing::RANK_STRENGTH_NON_TRUMP[rank_b]
        };

        str_b.cmp(&str_a)
    });

    let mut val;
    let original_alpha = alpha;

    if is_maximizing {
        val = -INF;
        for &i in &moves {
            let mut next_state = *state;
            next_state.play_card(i);
            let next_hash = compute_zobrist_hash(&next_state);
            let (eval, _) = minimax(&next_state, next_hash, alpha, beta, tt, depth - 1, debug);
            if eval > val {
                val = eval;
                best_move = i;
            }
            alpha = max(alpha, val);
            if beta <= alpha {
                break;
            }
        }
    } else {
        val = INF;
        for &i in &moves {
            let mut next_state = *state;
            next_state.play_card(i);
            let next_hash = compute_zobrist_hash(&next_state);
            let (eval, _) = minimax(&next_state, next_hash, alpha, beta, tt, depth - 1, debug);
            if eval < val {
                val = eval;
                best_move = i;
            }
            beta = min(beta, val);
            if beta <= alpha {
                break;
            }
        }
    }

    let val_norm = val.saturating_sub(current_points);
    let flag = if val <= original_alpha {
        2
    } else if val >= beta {
        1
    } else {
        0
    };

    tt[tt_idx] = TTEntry {
        key: hash,
        score: val_norm,
        best_move,
        flag,
        depth, // Store the depth at which this entry was computed
    };

    (val, best_move)
}
#[cfg(test)]
mod tests {
    use super::*;
    use crate::gameplay::playing::{PlayingState, CLUBS, HEARTS, SPADES};

    fn card(suit: u8, rank: u8) -> u8 {
        suit * 8 + rank
    }

    #[test]
    fn test_solve_last_trick() {
        let mut state = PlayingState::new(HEARTS);
        // P0: Ace Hearts (Trump)
        // P1: 7 Hearts
        // P2: 8 Hearts
        // P3: 9 Spades (No trump)

        state.hands[0] = 1 << card(HEARTS, 7);
        state.hands[1] = 1 << card(HEARTS, 0);
        state.hands[2] = 1 << card(HEARTS, 1);
        state.hands[3] = 1 << card(SPADES, 2);

        // P0 leads. Should win.
        // Points: A(11) + 7(0) + 8(0) + 9(0) + 10(der) = 21.

        let (score, best_move) = solve(&state, false);

        assert_eq!(best_move, card(HEARTS, 7));
        assert_eq!(score, 21);
    }

    #[test]
    fn test_solve_two_tricks_simple() {
        let mut state = PlayingState::new(HEARTS);
        // P0: A(H), K(H)
        // P1: 7(H), 8(H)
        // P2: 7(S), 8(S)
        // P3: 9(S), 10(S)

        state.hands[0] = (1 << card(HEARTS, 7)) | (1 << card(HEARTS, 6));
        state.hands[1] = (1 << card(HEARTS, 0)) | (1 << card(HEARTS, 1));
        state.hands[2] = (1 << card(SPADES, 0)) | (1 << card(SPADES, 1));
        state.hands[3] = (1 << card(SPADES, 2)) | (1 << card(SPADES, 3));

        // P0 should play A then K (or K then A, doesn't matter much here but A is safer/better usually).
        // Score:
        // T1: A(11) + 7(0) + 7(0) + 9(0) = 11.
        // T2: K(4) + 8(0) + 8(0) + 10(10) = 14.
        // Der: 10
        // Total: 35.

        let (score, _) = solve(&state, false);
        assert_eq!(score, 35);
    }

    #[test]
    fn test_capot_recognition() {
        let mut state = PlayingState::new(HEARTS);
        // P0 has a winning hand for 8 tricks.
        // To make test fast, simulate 4 tricks already played/won.
        state.tricks_won[0] = 4;

        // Give P0 top trumps remaining: J, 9, A, 10
        state.hands[0] = (1 << card(HEARTS, 4))
            | (1 << card(HEARTS, 2))
            | (1 << card(HEARTS, 7))
            | (1 << card(HEARTS, 3));
        // Give others garbage
        state.hands[1] = (1 << card(CLUBS, 0))
            | (1 << card(CLUBS, 1))
            | (1 << card(CLUBS, 2))
            | (1 << card(CLUBS, 3));
        state.hands[2] = (1 << card(CLUBS, 4))
            | (1 << card(CLUBS, 5))
            | (1 << card(CLUBS, 6))
            | (1 << card(CLUBS, 7));
        state.hands[3] = (1 << card(SPADES, 0))
            | (1 << card(SPADES, 1))
            | (1 << card(SPADES, 2))
            | (1 << card(SPADES, 3));

        // Points Calculation:
        // Cards in hand P0: J(20)+9(14)+A(11)+10(10) = 55.
        // Cards owned by others: 0 points (all 7,8s or non-valued).
        // Tricks won so far: 4. Assuming 0 points in them for simplicity of this test setup?
        // Wait, solver returns TOTAL points including what's already in state.points.
        // state.points is 0.
        // So expected = 55 + 10(der) + 90(capot) = 155.

        // BUT, solver might see "Total points = 162" if tricks so far had points.
        // Since we didn't populate previous tricks or points, the "Total Pts" is just what's left + bonuses.
        // Total available on board = 162.
        // Points currently accounted for = 0.
        // Points in hands = 55.
        // Missing points (played in first 4 tricks) = 162 - 55 = 107? No.
        // The solver sums points won in FUTURE moves.
        // The 162 logic is constant.

        // Total = 55 (My hand) + 40 (Captured from opps) + 10 (Der) + 90 (Capot) = 195.
        // Opp Points: P1(10C=10), P2(QC=3, KC=4, AC=11, JC=2 = 20), P3(10S=10). Total 40.

        let (score, _) = solve(&state, false);
        assert_eq!(score, 195);
    }
}
