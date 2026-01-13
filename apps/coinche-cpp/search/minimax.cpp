#include "minimax.hpp"
#include <algorithm>
#include <iostream>
#include <array>

#include <array>
#include <atomic>

// Global Stats Implementation
std::atomic<long> g_stats_weak_hand_hits(0);
std::atomic<long> g_stats_capot_hits(0);

long get_stats_weak_hand_hits() { return g_stats_weak_hand_hits.load(); }
long get_stats_capot_hits() { return g_stats_capot_hits.load(); }
void reset_stats() {
    g_stats_weak_hand_hits.store(0);
    g_stats_capot_hits.store(0);
}

namespace cointree {

// Rank Constants mapping (0..7) to Game Rank
// Ranks: 7=0, 8=1, 9=2, 10=3, J=4, Q=5, K=6, A=7
// Rank Constants mapping (0..7) to Game Rank
// Ranks: 7=0, 8=1, 9=2, 10=3, J=4, Q=5, K=6, A=7
static const int RANK_7 = 0;
static const int RANK_8 = 1;
static const int RANK_9 = 2;
static const int RANK_10 = 3;
static const int RANK_J = 4;
static const int RANK_Q = 5;
static const int RANK_K = 6;
static const int RANK_A = 7;

// Global Constant Arrays
static const int TRUMP_ORDER[] = {RANK_J, RANK_9, RANK_A, RANK_10, RANK_K, RANK_Q, RANK_8, RANK_7};
static const int TRUMP_POINTS[] = {20, 14, 11, 10, 4, 3, 0, 0};
static const int SIDE_ORDER[] = {RANK_A, RANK_10, RANK_K, RANK_Q, RANK_J, RANK_9, RANK_8, RANK_7};
static const int SIDE_POINTS[] = {11, 10, 4, 3, 2, 0, 0, 0};

// Helper to compute hand potential (Weak Hand Logic)
int calculate_potential_score(const CardSet& hand, Suit trump) {
    int score = 0;
    uint32_t mask = hand.mask;
    int t_int = static_cast<int>(trump);

    // --- 1. Trump Potential with Munitions ---
    uint32_t trump_mask = (mask >> (t_int * 8)) & 0xFF;
    int munitions = __builtin_popcount(trump_mask); 
    
    for (int i = 0; i < 8; ++i) {
        if (munitions <= 0) break; // no card left

        int r = TRUMP_ORDER[i];
        if (trump_mask & (1 << r)) {
            score += TRUMP_POINTS[i];
            munitions--; // we have the master, it pays for itself
        } else {
            // Missing card -> One of our lower cards is sacrificed to pay for the hole
            munitions--; 
        }
    }

    // --- 2. Side Suits Potential with Munitions ---
    for (int s = 0; s < 4; ++s) {
        if (s == t_int) continue;
        uint32_t suit_mask = (mask >> (s * 8)) & 0xFF;
        int s_munitions = __builtin_popcount(suit_mask);
        
        for (int i = 0; i < 8; ++i) {
            if (s_munitions <= 0) break;

            int r = SIDE_ORDER[i];
            if (suit_mask & (1 << r)) {
                score += SIDE_POINTS[i];
                s_munitions--;
            } else {
                // Sacrificed
                s_munitions--;
            }
        }
    }

    // --- 3. BONUS BELOTE ---
    bool has_k = (trump_mask & (1 << RANK_K)) != 0;
    bool has_q = (trump_mask & (1 << RANK_Q)) != 0;
    if (has_k && has_q) score += 20;

    return score;
}

// Helper: Face Value Fallback
int compute_face_value(const CardSet& hand, Suit trump) {
    int points = 0;
    uint32_t mask = hand.mask;
    int t_int = static_cast<int>(trump);
    int shift = t_int * 8;

    // Check Belote
    bool has_k = (mask & (1 << (shift + RANK_K))) != 0;
    bool has_q = (mask & (1 << (shift + RANK_Q))) != 0;
    if (has_k && has_q) {
        points += 20;
    }

    // Sum all cards
    // Iterate bits
    while (mask) {
        int id = __builtin_ctz(mask);
        Card c(id);
        points += Card::points(c, trump);
        mask &= ~(1U << id);
    }
    return points;
}

// Helper to check if a suit in hand forms a solid sequence from top
// Returns true if solid (or void).
bool is_solid_sequence(uint32_t hand, int suit, const int* rank_order, int len) {
    uint32_t suit_mask = 0xFF << (suit * 8);
    uint32_t cards = hand & suit_mask;
    if (cards == 0) return true; // Void is fine

    int count = __builtin_popcount(cards);
    int shift = suit * 8;
    
    // Check top 'count' ranks
    for (int i = 0; i < count; ++i) {
        int r = rank_order[i];
        if ((cards & (1 << (shift + r))) == 0) {
            return false;
        }
    }
    return true;
}

// Global Stats Implementation
std::atomic<long> g_stats_weak_hand_hits(0);
std::atomic<long> g_stats_capot_hits(0);

long get_stats_weak_hand_hits() { return g_stats_weak_hand_hits.load(); }
long get_stats_capot_hits() { return g_stats_capot_hits.load(); }
void reset_stats() {
    g_stats_weak_hand_hits.store(0);
    g_stats_capot_hits.store(0);
}

// Progress Implementation
std::atomic<long> g_hands_solved(0);
long get_hands_solved() { return g_hands_solved.load(); }
void increment_hands_solved() { g_hands_solved++; }
void reset_progress() { g_hands_solved.store(0); }

// Sub-method 1: Evaluate Weak Hand (Bidding Phase / 8 cards)
int evaluate_weak_hand(const CardSet& hand, Suit trump) {
    if (hand.size() == 8) {
        int potential = calculate_potential_score(hand, trump);
        if (potential < 40) {
            g_stats_weak_hand_hits++;
            return compute_face_value(hand, trump);
        }
    }
    return -1;
}

// Sub-method 2: Evaluate Capot (Master Hand)
int evaluate_capot(const CardSet& hand, Suit trump, int current_player, 
                   int ns_current_points, int ew_current_points, 
                   int ns_tricks_won) {
    
    uint32_t hand_mask = hand.mask;
    int t_int = static_cast<int>(trump);
    
    // 1. Check Trump Sequence (Must have at least 4 trumps and be solid)
    static const int TRUMP_ORDER[] = {RANK_J, RANK_9, RANK_A, RANK_10, RANK_K, RANK_Q, RANK_8, RANK_7};
    
    uint32_t trump_cards_mask = hand_mask & (0xFF << (t_int * 8));
    int trump_count = __builtin_popcount(trump_cards_mask);
    
    if (trump_count < 4) return -1;
    
    if (!is_solid_sequence(hand_mask, t_int, TRUMP_ORDER, 8)) return -1;

    // 2. Check Side Suits
    static const int SIDE_ORDER[] = {RANK_A, RANK_10, RANK_K, RANK_Q, RANK_J, RANK_9, RANK_8, RANK_7};
    
    for (int s = 0; s < 4; ++s) {
        if (s == t_int) continue;
        if (!is_solid_sequence(hand_mask, s, SIDE_ORDER, 8)) return -1;
    }
    
    // It is a Master Hand! 
    int tricks_remaining = __builtin_popcount(hand_mask);
    int tricks_played = 8 - tricks_remaining;
    
    bool is_ns = (current_player % 2 == 0);
    int ew_tricks_won = tricks_played - ns_tricks_won;
    
    // Capot Check logic
    bool capot = false;
    if (is_ns) {
        if (ew_tricks_won == 0) capot = true;
    } else {
        if (ns_tricks_won == 0) capot = true;
    }
    
    if (!capot) return -1;
    
    int score = 252;
    
    // Check Belote (K + Q of Trumps) IN current hand
    uint32_t k_mask = 1 << (t_int * 8 + RANK_K);
    uint32_t q_mask = 1 << (t_int * 8 + RANK_Q);
    
    if ((hand_mask & k_mask) && (hand_mask & q_mask)) {
        score += 20;
    }
    
    g_stats_capot_hits++;
    return score;
}

// 2. Advanced Circuit Breaker: Evaluate Hand Potential (Force Capot & Weak Hands)
// Returns 252 (or 272 with belote) if hand is guaranteed to win all remaining tricks.
// Returns score < 40 if Hand is Weak (Fallback Face Value).
// Returns -1 otherwise (Search Required).
int evaluate_hand_potential(const std::array<CardSet, 4> &hands, Suit trump, int current_player,
              int ns_current_points, int ew_current_points,
              int ns_tricks_won, int contract_team) {
  
  // 1. Weak Hand Circuit Breaker (Only valid for full hand start)
  int weak_score = evaluate_weak_hand(hands[current_player], trump);
  if (weak_score != -1) {
      return weak_score;
  }

  // 2. Capot / Master Hand Circuit Breaker
  int capot_score = evaluate_capot(hands[current_player], trump, current_player, 
                                   ns_current_points, ew_current_points, ns_tricks_won);
  if (capot_score != -1) {
      return capot_score;
  }
  
  return -1;
}


// Define Static
ZobristTable MinimaxSolver::Zobrist;

// Helper: Get best card strength in a trick for a suit
inline int get_max_strength(const std::vector<std::pair<int, Card>> &trick,
                            Suit s, Suit trump) {
  int max_str = -1;
  for (const auto &p : trick) {
    if (p.second.suit() == s) {
      max_str = std::max(max_str, Card::strength(p.second, trump));
    }
  }
  return max_str;
}

int MinimaxSolver::solve(const std::array<CardSet, 4> &hands,
                         Suit contract_suit,
                         int contract_player,
                         const std::vector<std::pair<int, Card>> &current_trick,
                         int starter_player, int ns_points, int ew_points) {
  std::array<CardSet, 4> mutable_hands = hands;
  std::vector<std::pair<int, Card>> mutable_trick = current_trick;
  mutable_trick.reserve(4);

  int contract_team = contract_player % 2;

  // Belote/Rebelote Check: King + Queen of Trump in same hand
  if (contract_suit != Suit::NONE) {
    Card king(contract_suit, Rank::KING);
    Card queen(contract_suit, Rank::QUEEN);
    for (int p = 0; p < 4; ++p) {
      if (hands[p].contains(king) && hands[p].contains(queen)) {
        if (p % 2 == 0)
          ns_points += 20;
        else
          ew_points += 20;
        break; 
      }
    }
  }

  // Calculate Initial Hash
  uint64_t hash = 0;
  for (int p = 0; p < 4; ++p) {
    uint32_t m = hands[p].mask;
    while (m) {
      int id = __builtin_ctz(m);
      hash ^= Zobrist.hand[p][id];
      m &= ~(1U << id);
    }
  }
  for (const auto &p : current_trick) {
    hash ^= Zobrist.trick[p.second.id];
  }
  // Turn hash
  int trick_size = current_trick.size();
  int current_player = (starter_player + trick_size) % 4;
  hash ^= Zobrist.turn[current_player];
  
  // Trump hash (allows TT reuse across suits)
  hash ^= Zobrist.trump[static_cast<int>(contract_suit)];

  return _alpha_beta(mutable_hands, contract_suit, mutable_trick,
                     starter_player, ns_points, ew_points, 0, -1, 253,
                     contract_team, hash);
}

// Helper to find trick winner
// Helper to find trick winner
int get_trick_winner(const std::vector<std::pair<int, Card>> &trick, Suit trump) {
  if (trick.empty()) return -1;

  int best_player = trick[0].first;
  Card best_card = trick[0].second;
  Suit lead_suit = best_card.suit();

  for (size_t i = 1; i < trick.size(); ++i) {
    int p = trick[i].first;
    Card c = trick[i].second;

    bool best_is_trump = (best_card.suit() == trump);
    bool c_is_trump = (c.suit() == trump);

    if (c_is_trump && !best_is_trump) {
      best_card = c; best_player = p;
    } else if (c_is_trump && best_is_trump) {
        if (Card::strength(c, trump) > Card::strength(best_card, trump)) {
            best_card = c; best_player = p;
        }
    } else if (!c_is_trump && !best_is_trump) {
        if (c.suit() == lead_suit && Card::strength(c, trump) > Card::strength(best_card, trump)) {
            best_card = c; best_player = p;
        }
    }
  }
  return best_player;
}

// SUPERIOR_MASKS[0] = No Trump, [1] = Trump
// Indexed by Rank (0=7 ... 7=A)
static const uint8_t SUPERIOR_MASKS[2][8] = {
    // No Trump: A(7)>10(3)>K(6)>Q(5)>J(4)>9(2)>8(1)>7(0)
    // 7(0): Beaten by 1,2,3,4,5,6,7 -> 0xFE
    // 8(1): Beaten by 2,3,4,5,6,7 -> 0xFC
    // 9(2): Beaten by 3,4,5,6,7 (10,J,Q,K,A) -> 0xF8
    // 10(3): Beaten by 7 (A) -> 0x80
    // J(4): Beaten by 3,5,6,7 (10,Q,K,A) -> 0xE8
    // Q(5): Beaten by 3,6,7 (10,K,A) -> 0xC8
    // K(6): Beaten by 3,7 (10,A) -> 0x88
    // A(7): Beaten by None -> 0x00
    {0xFE, 0xFC, 0xF8, 0x80, 0xE8, 0xC8, 0x88, 0x00},

    // Trump: J(4)>9(2)>A(7)>10(3)>K(6)>Q(5)>8(1)>7(0)
    // 7(0): Beaten by 1,2,3,4,5,6,7 -> 0xFE
    // 8(1): Beaten by 2,3,4,5,6,7 -> 0xFC
    // 9(2): Beaten by 4 (J) -> 0x10
    // 10(3): Beaten by 2,4,7 (9,J,A) -> 0x94
    // J(4): Beaten by None -> 0x00
    // Q(5): Beaten by 2,3,4,6,7 (9,10,J,K,A) -> 0xDC
    // K(6): Beaten by 2,3,4,7 (9,10,J,A) -> 0x9C
    // A(7): Beaten by 2,4 (9,J) -> 0x14
    {0xFE, 0xFC, 0x10, 0x94, 0x00, 0xDC, 0x9C, 0x14}
};

int generate_legal_moves(CardSet hand,
                         const std::vector<std::pair<int, Card>> &trick,
                         Suit trump, Card *out_moves) {
  uint32_t mask = hand.mask;
  if (mask == 0) return 0;

  // 1. Lead: Any card is legal
  if (trick.empty()) {
    int count = 0;
    while (mask) {
      int id = __builtin_ctz(mask);
      out_moves[count++] = Card(id);
      mask &= ~(1U << id);
    }
    return count;
  }

  int t_int = static_cast<int>(trump);
  uint32_t legal_mask = 0;
  
  // 2. Analyze Trick
  Card lead_card = trick[0].second;
  Suit lead_suit = lead_card.suit();
  int l_int = static_cast<int>(lead_suit);

  // Masks per suit
  uint32_t lead_suit_mask = (mask >> (l_int * 8)) & 0xFF;
  uint32_t trump_suit_mask = (mask >> (t_int * 8)) & 0xFF;

  // Can Follow?
  if (lead_suit_mask != 0) {
      if (l_int == t_int) {
          // Trump Lead: Must Overcut if possible
          // Find highest trump on table
          int max_rank = -1;
          for(const auto& p : trick) {
              if (p.second.suit() == trump) {
                   // Optimization: We could track max rank directly, but iterating 3 cards is fast.
                   // We need the *Rank* index for SUPERIOR_MASKS.
                   // Card::strength logic logic handles the 'value', but we need 'rank index'.
                   // Actually, we need to compare STRENGTH. SUPERIOR_MASKS is based on Rank Index?
                   // Yes, [Rank] gives mask of STRONGER ranks.
                   // So we need to find the card C in trick such that no other card in trick is stronger.
                   // Then use C.rank() to lookup mask.
                   // But "Highest Trump On Table" logic:
                   // Is it strictly the highest rank? Trump ordering J>9>A...
                   // SUPERIOR_MASKS[1] handles this strength ordering.
                   // So we just need the Rank of the best trump played.
                   
                   // Start with best_trump_rank = -1. Use strength to compare.
                   // But we need the Rank Index of the best trump.
                   int r = static_cast<int>(p.second.rank());
                   if (max_rank == -1) {
                       max_rank = r;
                   } else {
                       // Compare r vs max_rank using TRUMP strength
                       // We can use Card::strength or just check if 'r' is in SUPERIOR_MASKS[1][max_rank]?
                       // No, SUPERIOR_MASKS tells us what BEATS max_rank.
                       // If 'r' bit is set in SUPERIOR_MASKS[1][max_rank], then r > max_rank.
                       if ((SUPERIOR_MASKS[1][max_rank] >> r) & 1) {
                           max_rank = r;
                       }
                   }
              }
          }
           
          if (max_rank != -1) {
               uint8_t higher = lead_suit_mask & SUPERIOR_MASKS[1][max_rank];
               if (higher != 0) {
                   legal_mask = (static_cast<uint32_t>(higher) << (l_int * 8));
               } else {
                   // Undercut allowed if can't overcut
                   legal_mask = (static_cast<uint32_t>(lead_suit_mask) << (l_int * 8));
               }
          } else {
               // Should not happen if lead is trump, unless first card?
               // If trick not empty and lead is trump, max_rank must be set.
               legal_mask = (static_cast<uint32_t>(lead_suit_mask) << (l_int * 8));
          }

      } else {
          // Standard Follow
          legal_mask = (static_cast<uint32_t>(lead_suit_mask) << (l_int * 8));
      }
  } 
  else {
      // Cannot Follow
      
      // Check Partner Master
      int current_player = (trick.back().first + 1) % 4;
      int partner = (current_player + 2) % 4;
      
      if (get_trick_winner(trick, trump) == partner) {
          // Partner Master -> Freedom -> Play Any
          legal_mask = mask;
      } else {
          // Adversary Master -> Must Cut if possible
          if (trump_suit_mask != 0) {
              // Have Trumps. Check Overcut.
              int max_trump_rank = -1;
              for(const auto& p : trick) {
                  if (p.second.suit() == trump) {
                      int r = static_cast<int>(p.second.rank());
                      if (max_trump_rank == -1) {
                           max_trump_rank = r;
                      } else {
                           if ((SUPERIOR_MASKS[1][max_trump_rank] >> r) & 1) {
                               max_trump_rank = r;
                           }
                      }
                  }
              }
              
              if (max_trump_rank != -1) {
                  // Trumps exist on table. Must overcut.
                  uint8_t higher = trump_suit_mask & SUPERIOR_MASKS[1][max_trump_rank];
                  if (higher != 0) {
                      legal_mask = (static_cast<uint32_t>(higher) << (t_int * 8));
                  } else {
                      // Mandatory Undercut (since we have trump and can't overcut)
                      legal_mask = (static_cast<uint32_t>(trump_suit_mask) << (t_int * 8));
                  }
              } else {
                  // No trumps on table yet. Any trump is an overcut (cut).
                  legal_mask = (static_cast<uint32_t>(trump_suit_mask) << (t_int * 8));
              }
          } else {
              // No Trump, No Follow -> Discard Any
              legal_mask = mask;
          }
      }
  }
  
  // Output
  int count = 0;
  while (legal_mask) {
      int id = __builtin_ctz(legal_mask);
      out_moves[count++] = Card(id);
      legal_mask &= ~(1U << id);
  }
  return count;
}



int MinimaxSolver::_alpha_beta(std::array<CardSet, 4> &hands, Suit trump,
                               std::vector<std::pair<int, Card>> &current_trick,
                               int starter_player, int ns_points, int ew_points,
                               int ns_tricks, int alpha, int beta,
                               int contract_team, uint64_t current_hash) {
  // 1. Base Case: Game Over
  if (hands[0].isEmpty() && current_trick.empty()) {
    int final_ns = ns_points;
    int final_ew = ew_points;

    // Capot Check (Assuming 8 tricks game)
    if (ns_tricks == 8)
      final_ns += 90;
    else if (ns_tricks == 0) // EW took all tricks
      final_ew += 90;

    return (contract_team == 0) ? final_ns : final_ew;
  }

  // 1a. Capot Circuit Breaker (IsCapot / TryClaim optimization)
  if (current_trick.empty()) {
     int trick_size = current_trick.size();
     int current_player = (starter_player + trick_size) % 4; // Should be starter_player
     
     int claim_score = evaluate_hand_potential(hands, trump, current_player, ns_points, ew_points, ns_tricks, contract_team);
     if (claim_score != -1) {
         return claim_score;
     }
  }

  // 2. Transposition Table Probe
  // Direct Index Mapping - O(1)
  uint32_t idx = current_hash & mask;
  if (tt[idx].key == current_hash) {
    return tt[idx].value;
  }

  // 3. Logic
  int trick_size = current_trick.size();
  int current_player = (starter_player + trick_size) % 4;
  bool is_attacker = (current_player % 2 == contract_team);

  // Generate Moves (Stack Allocation)
  Card moves[8];
  int n_moves =
      generate_legal_moves(hands[current_player], current_trick, trump, moves);

  // Move Ordering
  if (n_moves > 1) {
    std::pair<int, int> scores[8];
    for (int i = 0; i < n_moves; ++i)
      scores[i] = {Card::strength(moves[i], trump), i};

    std::sort(scores, scores + n_moves,
              [](const auto &a, const auto &b) { return a.first > b.first; });

    Card sorted[8];
    for (int i = 0; i < n_moves; ++i)
      sorted[i] = moves[scores[i].second];
    for (int i = 0; i < n_moves; ++i)
      moves[i] = sorted[i];
  }

  int best_val = is_attacker ? -1 : 9999;

  for (int i = 0; i < n_moves; ++i) {
    Card move = moves[i];

    // Calculate Next Hash (Incremental)
    uint64_t next_hash = current_hash;
    next_hash ^= Zobrist.hand[current_player][move.id]; // Remove from hand
    next_hash ^= Zobrist.turn[current_player];          // Remove old turn
    next_hash ^= Zobrist.trick[move.id];                // Add to trick

    // Play
    hands[current_player].remove(move);
    current_trick.push_back({current_player, move});

    int val = 0;

    if (current_trick.size() == 4) {
      // Trick Complete
      int winner_idx = -1;
      int max_str = -1;
      Suit lead = current_trick[0].second.suit();

      for (auto &p : current_trick) {
        int str = -1;
        if (p.second.suit() == trump)
          str = 1000 + Card::strength(p.second, trump);
        else if (p.second.suit() == lead)
          str = Card::strength(p.second, trump);

        if (str > max_str) {
          max_str = str;
          winner_idx = p.first;
        }
      }

      int trick_pts = 0;
      for (auto &p : current_trick)
        trick_pts += Card::points(p.second, trump);

      if (hands[0].isEmpty())
        trick_pts += 10;

      int n_ns = ns_points + (winner_idx % 2 == 0 ? trick_pts : 0);
      int n_ew = ew_points + (winner_idx % 2 == 1 ? trick_pts : 0);

      std::vector<std::pair<int, Card>> empty_trick;
      empty_trick.reserve(4);

      // Hash Update for Trick Clear
      // 1. Remove all cards from trick hash
      // 2. Winner is new starter
      uint64_t trick_cleared_hash = next_hash;
      for (auto &p : current_trick) {
        trick_cleared_hash ^= Zobrist.trick[p.second.id];
      }
      trick_cleared_hash ^= Zobrist.turn[winner_idx]; // New Turn

      int next_ns_tricks = ns_tricks + (winner_idx % 2 == 0 ? 1 : 0);

      val = _alpha_beta(hands, trump, empty_trick, winner_idx, n_ns, n_ew,
                        next_ns_tricks, alpha, beta, contract_team,
                        trick_cleared_hash);
    } else {
      // Next Card within trick
      int next_player = (current_player + 1) % 4;
      next_hash ^= Zobrist.turn[next_player]; // New Turn

      val = _alpha_beta(hands, trump, current_trick, starter_player, ns_points,
                        ew_points, ns_tricks, alpha, beta, contract_team,
                        next_hash);
    }

    // Undo
    current_trick.pop_back();
    hands[current_player].add(move);

    // Alpha Beta (Pruning)
    if (is_attacker) {
      if (val > best_val)
        best_val = val;
      alpha = std::max(alpha, best_val);
      if (beta <= alpha)
        break;
    } else {
      if (val < best_val)
        best_val = val;
      beta = std::min(beta, best_val);
      if (beta <= alpha)
        break;
    }
  }

  // Store in TT
  tt[idx].key = current_hash;
  tt[idx].value = best_val;

  return best_val;
}

} // namespace cointree
