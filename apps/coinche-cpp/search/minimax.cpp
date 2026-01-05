#include "minimax.hpp"
#include <algorithm>
#include <array>

namespace cointree {

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
                         Suit contract_suit, int contract_amount,
                         int contract_player,
                         const std::vector<std::pair<int, Card>> &current_trick,
                         int starter_player, int ns_points, int ew_points) {
  std::array<CardSet, 4> mutable_hands = hands;
  std::vector<std::pair<int, Card>> mutable_trick = current_trick;
  mutable_trick.reserve(4);

  int contract_team = contract_player % 2;

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

  // Use a slightly wider window at the root if needed, but [0, 162] is strict
  return _alpha_beta(mutable_hands, contract_suit, mutable_trick,
                     starter_player, ns_points, ew_points, -1, 163,
                     contract_team, hash);
}

// Optimized Move Generation: No Vectors, Stack Only
// Returns number of moves filled into 'out_moves'
inline int generate_legal_moves(CardSet hand,
                                const std::vector<std::pair<int, Card>> &trick,
                                Suit trump, Card *out_moves) {
  uint32_t mask = hand.mask;
  if (mask == 0)
    return 0;

  int count = 0;

  // 1. Lead: Any card is legal
  if (trick.empty()) {
    while (mask) {
      int id = __builtin_ctz(mask);
      out_moves[count++] = Card(id);
      mask &= ~(1U << id);
    }
    return count;
  }

  // 2. Follow Logic
  Suit lead_suit = trick[0].second.suit();

  // Create subsets using masks
  // We can filter the hand mask directly without iterating yet
  // Actually iterating bits is fast.

  // Collect categories
  Card follow[8];
  int n_follow = 0;
  Card trumps[8];
  int n_trumps = 0;
  Card any[8];
  int n_any = 0; // All cards

  uint32_t m = mask;
  while (m) {
    int id = __builtin_ctz(m);
    Card c(id);

    any[n_any++] = c;
    if (c.suit() == lead_suit)
      follow[n_follow++] = c;
    if (c.suit() == trump)
      trumps[n_trumps++] = c;

    m &= ~(1U << id);
  }

  // Logic Tree
  if (n_follow > 0) {
    if (lead_suit == trump) {
      // Must play Higher Trump if possible
      int max_tr = get_max_strength(trick, trump, trump);

      // Filter higher
      int n_higher = 0;
      for (int i = 0; i < n_follow; ++i) {
        if (Card::strength(follow[i], trump) > max_tr) {
          out_moves[n_higher++] = follow[i];
        }
      }

      if (n_higher > 0)
        return n_higher;

      // Else play any trump
      for (int i = 0; i < n_follow; ++i)
        out_moves[i] = follow[i];
      return n_follow;

    } else {
      // Just follow suit
      for (int i = 0; i < n_follow; ++i)
        out_moves[i] = follow[i];
      return n_follow;
    }
  }

  // Cannot follow
  if (n_trumps > 0) {
    // Must trump logic (Strict)
    int max_tr = get_max_strength(trick, trump, trump);

    int n_higher = 0;
    for (int i = 0; i < n_trumps; ++i) {
      if (Card::strength(trumps[i], trump) > max_tr)
        out_moves[n_higher++] = trumps[i];
    }

    if (n_higher > 0)
      return n_higher;

    // Can't overtrump? Play any trump.
    for (int i = 0; i < n_trumps; ++i)
      out_moves[i] = trumps[i];
    return n_trumps;
  }

  // Cannot Follow, Cannot Trump
  // Any card legal
  for (int i = 0; i < n_any; ++i)
    out_moves[i] = any[i];
  return n_any;
}

int MinimaxSolver::_alpha_beta(std::array<CardSet, 4> &hands, Suit trump,
                               std::vector<std::pair<int, Card>> &current_trick,
                               int starter_player, int ns_points, int ew_points,
                               int alpha, int beta, int contract_team,
                               uint64_t current_hash) {
  // 1. Base Case: Game Over
  if (hands[0].isEmpty() && current_trick.empty()) {
    return (contract_team == 0) ? ns_points : ew_points;
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

      val = _alpha_beta(hands, trump, empty_trick, winner_idx, n_ns, n_ew,
                        alpha, beta, contract_team, trick_cleared_hash);
    } else {
      // Next Card within trick
      int next_player = (current_player + 1) % 4;
      next_hash ^= Zobrist.turn[next_player]; // New Turn

      val = _alpha_beta(hands, trump, current_trick, starter_player, ns_points,
                        ew_points, alpha, beta, contract_team, next_hash);
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
