#pragma once

#include "../core/cards.hpp"
#include <array>
#include <cstdint>
#include <random>
#include <vector>

namespace cointree {

// 64-bit Zobrist Hash Keys
struct ZobristTable {
  uint64_t hand[4][32]; // [player][card]
  uint64_t trick[32];   // [card] in trick
  uint64_t turn[4];     // [player] to lead/act next
  uint64_t trump[5];    // [suit] contract

  ZobristTable() {
    std::mt19937_64 rng(42);
    for (int p = 0; p < 4; ++p)
      for (int c = 0; c < 32; ++c)
        hand[p][c] = rng();

    for (int c = 0; c < 32; ++c)
      trick[c] = rng();
    for (int p = 0; p < 4; ++p)
      turn[p] = rng();
    for (int s = 0; s < 5; ++s)
      trump[s] = rng();
  }
};

struct TTEntry {
  uint64_t key;
  int value;
};

class MinimaxSolver {
public:
  static ZobristTable Zobrist;

  std::vector<TTEntry> tt;
  uint32_t mask; // Size - 1

  MinimaxSolver() {
    // 2^22 = 4M entries = 64MB.
    size_t size = 1 << 22;
    tt.resize(size);
    mask = size - 1;
    // Clear
    for (auto &e : tt) {
      e.key = 0;
      e.value = -99999;
    }
  }

  /**
   * Solves the game state using Alpha-Beta pruning.
   * Returns the maximum score the CONTRACTING TEAM can achieve from this state.
   *
   * @param hands           Current cards held by each player [0..3]
   * @param contract_suit   The Trump suit
   * @param contract_player Index (0-3) of the player who made the contract.
   *                        Determines the Attacker (Contract Team) vs Defender.
   * @param current_trick   Cards played so far in the current trick
   * @param starter_player  Index (0-3) of the player who started the current trick
   * @param ns_points       Points already secured by North/South
   * @param ew_points       Points already secured by East/West
   * @return                Final score (Trick Points + Bonuses) for the Contracting Team.
   */
  int solve(const std::array<CardSet, 4> &hands, Suit contract_suit,
            int contract_player, // 0-3
            const std::vector<std::pair<int, Card>> &current_trick,
            int starter_player, int ns_points, int ew_points);

private:
  int _alpha_beta(std::array<CardSet, 4> &hands, Suit trump,
                  std::vector<std::pair<int, Card>> &current_trick,
                  int starter_player, int ns_points, int ew_points,
                  int ns_tricks, int alpha, int beta, int contract_team,
                  uint64_t current_hash);
};

} // namespace cointree
