#include "../core/cards.hpp"
#include "../search/minimax.hpp"
#include <iostream>
#include <vector>
#include <cassert>
#include <algorithm>
#include <set>
#include <string>

using namespace cointree;

// Helper to print cards
std::string card_to_str(const Card& c) {
    std::string suits[] = {"♥", "♦", "♣", "♠"};
    std::string ranks[] = {"7", "8", "9", "10", "J", "Q", "K", "A"};
    return ranks[(int)c.rank()] + suits[(int)c.suit()];
}

// Helper to check expectations
void verify_moves(const std::string& test_name, 
                  int count, Card* moves, 
                  const std::vector<Card>& expected) {
    if (count != expected.size()) {
        std::cout << "[FAIL] " << test_name << ": Expected " << expected.size() << " moves, got " << count << std::endl;
        std::cout << "  Got: ";
        for(int i=0; i<count; ++i) std::cout << card_to_str(moves[i]) << " ";
        std::cout << "\n  Exp: ";
        for(const auto& c : expected) std::cout << card_to_str(c) << " ";
        std::cout << std::endl;
        return;
    }

    // Check content (exact match)
    // Convert to sets for checking
    std::set<int> move_ids;
    for(int i=0; i<count; ++i) move_ids.insert(moves[i].id);

    std::set<int> exp_ids;
    for(const auto& c : expected) exp_ids.insert(c.id);

    if (move_ids != exp_ids) {
        std::cout << "[FAIL] " << test_name << ": Content Mismatch" << std::endl;
        std::cout << "  Got: ";
        for(int i=0; i<count; ++i) std::cout << card_to_str(moves[i]) << " ";
        std::cout << "\n  Exp: ";
        for(const auto& c : expected) std::cout << card_to_str(c) << " ";
        std::cout << std::endl;
    } else {
        std::cout << "[PASS] " << test_name << std::endl;
    }
}

int main() {
    Card moves[32];
    int count;

    // --- TEST_FOLLOW_SUIT ---
    {
        std::vector<std::pair<int, Card>> trick;
        trick.emplace_back(0, Card(Suit::HEARTS, Rank::ACE)); // J0 plays Ah
        
        CardSet hand;
        hand.add(Card(Suit::HEARTS, Rank::SEVEN));
        hand.add(Card(Suit::HEARTS, Rank::KING));
        hand.add(Card(Suit::DIAMONDS, Rank::TEN));

        count = generate_legal_moves(hand, trick, Suit::CLUBS, moves);
        verify_moves("TEST_FOLLOW_SUIT", count, moves, {
            Card(Suit::HEARTS, Rank::SEVEN),
            Card(Suit::HEARTS, Rank::KING)
        });
    }

    // --- TEST_TRUMP_OVERCUT ---
    {
        std::vector<std::pair<int, Card>> trick;
        trick.emplace_back(0, Card(Suit::CLUBS, Rank::SEVEN));
        trick.emplace_back(1, Card(Suit::CLUBS, Rank::TEN)); // Master is 10C

        CardSet hand;
        hand.add(Card(Suit::CLUBS, Rank::JACK));
        hand.add(Card(Suit::CLUBS, Rank::EIGHT));
        hand.add(Card(Suit::SPADES, Rank::ACE));

        count = generate_legal_moves(hand, trick, Suit::CLUBS, moves);
        verify_moves("TEST_TRUMP_OVERCUT", count, moves, {
            Card(Suit::CLUBS, Rank::JACK)
        });
    }

    // --- TEST_MANDATORY_CUT_ADVERSARY ---
    {
        std::vector<std::pair<int, Card>> trick;
        trick.emplace_back(0, Card(Suit::SPADES, Rank::ACE)); // Master

        CardSet hand;
        hand.add(Card(Suit::HEARTS, Rank::SEVEN));
        hand.add(Card(Suit::HEARTS, Rank::EIGHT));
        hand.add(Card(Suit::DIAMONDS, Rank::KING));

        count = generate_legal_moves(hand, trick, Suit::HEARTS, moves);
        verify_moves("TEST_MANDATORY_CUT_ADVERSARY", count, moves, {
            Card(Suit::HEARTS, Rank::SEVEN),
            Card(Suit::HEARTS, Rank::EIGHT)
        });
    }

    // --- TEST_MANDATORY_UNDERCUT ---
    {
        std::vector<std::pair<int, Card>> trick;
        trick.emplace_back(0, Card(Suit::SPADES, Rank::SEVEN));
        trick.emplace_back(1, Card(Suit::SPADES, Rank::EIGHT));
        trick.emplace_back(2, Card(Suit::HEARTS, Rank::ACE)); // Cut Master

        CardSet hand;
        hand.add(Card(Suit::HEARTS, Rank::SEVEN));
        hand.add(Card(Suit::DIAMONDS, Rank::EIGHT));
        hand.add(Card(Suit::DIAMONDS, Rank::NINE));

        count = generate_legal_moves(hand, trick, Suit::HEARTS, moves);
        verify_moves("TEST_MANDATORY_UNDERCUT", count, moves, {
            Card(Suit::HEARTS, Rank::SEVEN)
        });
    }

    // --- TEST_PARTNER_MASTER_FREEDOM (La Pisse) ---
    {
        std::vector<std::pair<int, Card>> trick;
        trick.emplace_back(0, Card(Suit::SPADES, Rank::SEVEN));
        trick.emplace_back(1, Card(Suit::SPADES, Rank::ACE)); // Partner Master
        trick.emplace_back(2, Card(Suit::SPADES, Rank::EIGHT));

        CardSet hand;
        hand.add(Card(Suit::HEARTS, Rank::SEVEN)); // Trump
        hand.add(Card(Suit::DIAMONDS, Rank::EIGHT));

        count = generate_legal_moves(hand, trick, Suit::HEARTS, moves);
        verify_moves("TEST_PARTNER_MASTER_FREEDOM", count, moves, {
            Card(Suit::HEARTS, Rank::SEVEN),
            Card(Suit::DIAMONDS, Rank::EIGHT)
        });
    }

    // --- TEST_TOTAL_DISCARD ---
    {
        std::vector<std::pair<int, Card>> trick;
        trick.emplace_back(0, Card(Suit::SPADES, Rank::ACE));

        CardSet hand;
        hand.add(Card(Suit::DIAMONDS, Rank::SEVEN));
        hand.add(Card(Suit::CLUBS, Rank::EIGHT));
        hand.add(Card(Suit::CLUBS, Rank::KING));

        count = generate_legal_moves(hand, trick, Suit::HEARTS, moves);
        verify_moves("TEST_TOTAL_DISCARD", count, moves, {
            Card(Suit::DIAMONDS, Rank::SEVEN),
            Card(Suit::CLUBS, Rank::EIGHT),
            Card(Suit::CLUBS, Rank::KING)
        });
    }

    // --- TEST_LEAD_PLAY_ANY ---
    {
        std::vector<std::pair<int, Card>> trick; // Empty

        CardSet hand;
        hand.add(Card(Suit::SPADES, Rank::SEVEN));
        hand.add(Card(Suit::HEARTS, Rank::EIGHT));
        hand.add(Card(Suit::CLUBS, Rank::NINE));
        hand.add(Card(Suit::DIAMONDS, Rank::TEN));

        count = generate_legal_moves(hand, trick, Suit::HEARTS, moves);
        verify_moves("TEST_LEAD_PLAY_ANY", count, moves, {
            Card(Suit::SPADES, Rank::SEVEN),
            Card(Suit::HEARTS, Rank::EIGHT),
            Card(Suit::CLUBS, Rank::NINE),
            Card(Suit::DIAMONDS, Rank::TEN)
        });
    }

    return 0;
}
