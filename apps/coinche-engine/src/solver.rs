use crate::gameplay::playing::PlayingState;
use std::cmp::{max, min};
use std::collections::HashMap;

const INF: i16 = 1000;

// Transposition Table Entry
struct TTEntry {
    score: i16,
    best_move: u8,
    flag: u8, // 0: Exact, 1: Lowerbound, 2: Upperbound
              // depth: u8, // Not strictly needed for end-game solver (always solves to end), but good practice
}

pub fn solve(state: &PlayingState, generate_graph: bool) -> (i16, u8) {
    let mut tt = HashMap::new();
    let (score, best_move) = minimax(state, -INF, INF, &mut tt);

    if generate_graph {
        generate_dot_file(state, &tt);
    }

    (score, best_move)
}

fn generate_dot_file(root_state: &PlayingState, tt: &HashMap<u64, TTEntry>) {
    use std::fs::File;
    use std::io::Write;

    let mut file = File::create("tree.dot").expect("Unable to create file");
    writeln!(file, "digraph GameTree {{").unwrap();
    writeln!(file, "  node [shape=box, fontname=\"Courier\"];").unwrap();

    // Helper to get move name
    let get_card_name = |c: u8| -> String {
        let suits = ["D", "S", "H", "C"];
        let ranks = ["7", "8", "9", "10", "J", "Q", "K", "A"];
        if c == 0xFF {
            return "None".to_string();
        }
        format!("{}{}", ranks[(c % 8) as usize], suits[(c / 8) as usize])
    };

    // Helper to get hand string
    let get_hand_str = |hand_mask: u32| -> String {
        let mut cards = Vec::new();
        for i in 0..32 {
            if (hand_mask & (1 << i)) != 0 {
                cards.push(get_card_name(i as u8));
            }
        }
        if cards.is_empty() {
            return "Empty".to_string();
        }
        cards.join(" ")
    };

    // Helper to get trick string
    let get_trick_str = |trick: &[u8; 4]| -> String {
        let mut parts = Vec::new();
        for i in 0..4 {
            if trick[i] != 0xFF {
                parts.push(format!("P{}:{}", i, get_card_name(trick[i])));
            }
        }
        if parts.is_empty() {
            return "Empty".to_string();
        }
        parts.join(", ")
    };

    // 1. Find top moves at root
    let legal_moves_mask = root_state.get_legal_moves();
    let mut moves = Vec::new();

    let is_maximizing = root_state.current_player % 2 == 0;

    for i in 0..32 {
        if (legal_moves_mask & (1 << i)) != 0 {
            let mut next_state = root_state.clone();
            next_state.play_card(i as u8);
            let key = compute_hash(&next_state);

            if let Some(entry) = tt.get(&key) {
                moves.push((i as u8, entry.score));
            }
        }
    }

    // Sort moves: Best first
    if is_maximizing {
        moves.sort_by(|a, b| b.1.cmp(&a.1));
    } else {
        moves.sort_by(|a, b| a.1.cmp(&b.1));
    }

    // Take top 3
    let top_moves = moves.into_iter().take(3).collect::<Vec<_>>();

    let root_id = compute_hash(root_state);

    // Root Label: Show all hands
    let mut root_label = format!(
        "ROOT\\nPlayer: {}\\nTrump: {}\\n",
        root_state.current_player, root_state.trump
    );
    for i in 0..4 {
        root_label.push_str(&format!("P{}: {}\\n", i, get_hand_str(root_state.hands[i])));
    }
    root_label.push_str(&format!(
        "Trick: {}\\n",
        get_trick_str(&root_state.current_trick)
    ));
    root_label.push_str(&format!(
        "Points: NS={}, EW={}",
        root_state.points[0], root_state.points[1]
    ));

    writeln!(file, "  {} [label=\"{}\"];", root_id, root_label).unwrap();

    for (move_idx, score) in top_moves {
        let mut current_state = root_state.clone();
        current_state.play_card(move_idx);

        let mut current_id = root_id;
        let mut next_id = compute_hash(&current_state);

        writeln!(
            file,
            "  {} -> {} [label=\"{} ({})\"];",
            current_id,
            next_id,
            get_card_name(move_idx),
            score
        )
        .unwrap();

        // Node Label
        let label = format!(
            "Player: {}\\nTrick: {}\\nScore: {}\\nPoints: NS={}, EW={}",
            current_state.current_player,
            get_trick_str(&current_state.current_trick),
            score,
            current_state.points[0],
            current_state.points[1]
        );
        writeln!(file, "  {} [label=\"{}\"];", next_id, label).unwrap();

        // Trace PV for this move
        let mut depth = 0;
        while depth < 32 {
            if current_state.is_terminal() {
                break;
            }

            let key = compute_hash(&current_state);
            if let Some(entry) = tt.get(&key) {
                if entry.best_move == 0xFF {
                    break;
                }

                let best_move = entry.best_move;
                current_id = next_id;

                current_state.play_card(best_move);
                next_id = compute_hash(&current_state);

                writeln!(
                    file,
                    "  {} -> {} [label=\"{}\"];",
                    current_id,
                    next_id,
                    get_card_name(best_move)
                )
                .unwrap();

                let label = format!(
                    "Player: {}\\nTrick: {}\\nScore: {}\\nPoints: NS={}, EW={}",
                    current_state.current_player,
                    get_trick_str(&current_state.current_trick),
                    entry.score,
                    current_state.points[0],
                    current_state.points[1]
                );
                writeln!(file, "  {} [label=\"{}\"];", next_id, label).unwrap();

                depth += 1;
            } else {
                break;
            }
        }
    }

    writeln!(file, "}}").unwrap();
}

fn minimax(
    state: &PlayingState,
    mut alpha: i16,
    mut beta: i16,
    tt: &mut HashMap<u64, TTEntry>,
) -> (i16, u8) {
    if state.is_terminal() {
        return (state.points[0] as i16, 0xFF);
    }

    // 0. Memory Safety Check
    // If the TT gets too huge (> 5M items ~ 300MB-500MB), purge it to prevent OOM.
    // This is a tradeoff: we lose cached positions (slower) but we don't crash.
    if tt.len() > 5_000_000 {
        tt.clear();
    }

    // 1. Check TT
    let key = compute_hash(state);
    if let Some(entry) = tt.get(&key) {
        if entry.flag == 0 {
            return (entry.score, entry.best_move);
        } else if entry.flag == 1 {
            // Lowerbound
            alpha = max(alpha, entry.score);
        } else if entry.flag == 2 {
            // Upperbound
            beta = min(beta, entry.score);
        }
        if alpha >= beta {
            return (entry.score, entry.best_move);
        }
    }

    let legal_moves_mask = state.get_legal_moves();
    let mut best_move = 0xFF;
    let is_maximizing = state.current_player % 2 == 0;

    // Collect moves
    let mut moves = Vec::with_capacity(8);
    for i in 0..32 {
        if (legal_moves_mask & (1 << i)) != 0 {
            moves.push(i as u8);
        }
    }

    // Move Ordering: Sort by potential strength
    // Heuristic: Try high value cards first (winning tricks early is good for pruning)
    // Strength: Trump > Non-Trump. Within suit: Rank Strength.
    moves.sort_by(|&a, &b| {
        let suit_a = a / 8;
        let suit_b = b / 8;
        let rank_a = (a % 8) as usize;
        let rank_b = (b % 8) as usize;
        let is_trump_a = suit_a == state.trump;
        let is_trump_b = suit_b == state.trump;

        if is_trump_a && !is_trump_b {
            return std::cmp::Ordering::Less; // a > b (Desc)
        }
        if !is_trump_a && is_trump_b {
            return std::cmp::Ordering::Greater;
        }

        // Both trump or both non-trump
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

        str_b.cmp(&str_a) // Descending
    });

    // Create optimization to avoid redundant point calculations
    let mut val;
    let original_alpha = alpha;

    if is_maximizing {
        val = -INF;
        for &i in &moves {
            let mut next_state = state.clone();
            next_state.play_card(i);

            let (eval, _) = minimax(&next_state, alpha, beta, tt);

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
            let mut next_state = state.clone();
            next_state.play_card(i);

            let (eval, _) = minimax(&next_state, alpha, beta, tt);

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

    // Store in TT
    // Store FUTURE score relative to this state?
    // No, let's just use the full state hash for now to avoid bugs.
    // If we hash full state (including points), we don't need math.
    // But we lose transposition benefits if points differ.
    // In Coinche, points only increase.
    // It's rare to reach same hands/trick with different points?
    // Yes, because points come from captured tricks. Different capture order = different hands?
    // No, same hands can be reached via different trick orders.
    // Example: A takes trick 1, B takes trick 2 vs B takes 1, A takes 2.
    // Hands are same. Points are same.
    // So full state hash is fine.

    let flag = if val <= original_alpha {
        2 // Upperbound (failed low)
    } else if val >= beta {
        1 // Lowerbound (failed high)
    } else {
        0 // Exact
    };

    tt.insert(
        key,
        TTEntry {
            score: val,
            best_move,
            flag,
            // depth: 0,
        },
    );

    (val, best_move)
}

fn compute_hash(state: &PlayingState) -> u64 {
    // Simple hash: XOR of hands + trick + turn + points
    // Use a simple mixing function
    let mut h: u64 = 0;
    for i in 0..4 {
        h = h.wrapping_add(state.hands[i] as u64).rotate_left(13);
        h ^= state.current_trick[i] as u64;
    }
    h = h.wrapping_add(state.current_player as u64).rotate_left(7);
    h ^= (state.points[0] as u64) << 32;
    h ^= state.points[1] as u64;
    h ^= (state.tricks_won[0] as u64).rotate_left(20);
    h ^= (state.tricks_won[1] as u64).rotate_left(50);
    h
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
