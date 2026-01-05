#pragma once

#include <cstdint>
#include <string>
#include <vector>
// #include <immintrin.h> // SIMD intrinsics removed for ARM compatibility
// (Apple Silicon)

namespace cointree {

// Suits
enum class Suit : uint8_t {
  HEARTS = 0,
  DIAMONDS = 1,
  CLUBS = 2,
  SPADES = 3,
  NONE = 4
};

// Ranks (0-7 for 7, 8, 9, 10, J, Q, K, A)
enum class Rank : uint8_t {
  SEVEN = 0,
  EIGHT = 1,
  NINE = 2,
  TEN = 3,
  JACK = 4,
  QUEEN = 5,
  KING = 6,
  ACE = 7
};

// Card represented as a single byte: 2 bits Suit | 3 bits Rank
// 00-SS-RRR
class Card {
public:
  uint8_t id; // 0-31

  constexpr Card() : id(255) {}
  constexpr Card(uint8_t val) : id(val) {}
  constexpr Card(Suit s, Rank r)
      : id(static_cast<uint8_t>(s) * 8 + static_cast<uint8_t>(r)) {}

  constexpr Suit suit() const { return static_cast<Suit>(id / 8); }
  constexpr Rank rank() const { return static_cast<Rank>(id % 8); }

  constexpr bool isValid() const { return id < 32; }

  // Equality
  bool operator==(const Card &other) const { return id == other.id; }
  bool operator!=(const Card &other) const { return id != other.id; }
  bool operator<(const Card &other) const { return id < other.id; }

  std::string toString() const {
    if (!isValid())
      return "INVALID";
    const char *suits[] = {"H", "D", "C", "S"};
    const char *ranks[] = {"7", "8", "9", "10", "J", "Q", "K", "A"};
    return std::string(ranks[static_cast<int>(rank())]) +
           suits[static_cast<int>(suit())];
  }

  // Static Helpers
  // Static Helpers
  static int strength(Card c, Suit trump) {
    if (c.suit() == trump) {
      static constexpr int STRENGTH_TRUMP[] = {50,  60, 150, 90,
                                               200, 70, 80,  100};
      return STRENGTH_TRUMP[static_cast<int>(c.rank())];
    }
    static constexpr int STRENGTH_NO_TRUMP[] = {0, 0, 10, 100, 20, 30, 40, 110};
    return STRENGTH_NO_TRUMP[static_cast<int>(c.rank())];
  }

  static int points(Card c, Suit trump) {
    if (c.suit() == trump) {
      static constexpr int POINTS_TRUMP[] = {0, 0, 14, 10, 20, 3, 4, 11};
      return POINTS_TRUMP[static_cast<int>(c.rank())];
    }
    static constexpr int POINTS_NO_TRUMP[] = {0, 0, 0, 10, 2, 3, 4, 11};
    return POINTS_NO_TRUMP[static_cast<int>(c.rank())];
  }
};

// Bitboard representation for a Set of Cards (Hand)
// 32 bits is perfect for 32 cards.
// Operations become single CPU instructions.
struct CardSet {
  uint32_t mask;

  constexpr CardSet() : mask(0) {}
  constexpr CardSet(uint32_t m) : mask(m) {}

  void add(Card c) { mask |= (1U << c.id); }
  void remove(Card c) { mask &= ~(1U << c.id); }
  bool contains(Card c) const { return (mask >> c.id) & 1U; }
  bool isEmpty() const { return mask == 0; }
  int size() const { return __builtin_popcount(mask); } // GCC/Clang intrinsic

  // Set Iteration Helper
  std::vector<Card> toVector() const {
    std::vector<Card> cards;
    cards.reserve(size());
    uint32_t temp = mask;
    while (temp) {
      int idx = __builtin_ctz(temp); // Count trailing zeros
      cards.emplace_back(static_cast<uint8_t>(idx));
      temp &= ~(1U << idx);
    }
    return cards;
  }
};

} // namespace cointree
