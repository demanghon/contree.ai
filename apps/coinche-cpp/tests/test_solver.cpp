#include <iostream>
#include <cassert>
#include <vector>
#include <algorithm>
#include <random>
#include "search/minimax.hpp"
#include "core/cards.hpp"

using namespace cointree;

void test_random_hands() {
    std::cout << "Running test_random_hands..." << std::endl;

    // Create Deck
    std::vector<Card> deck;
    for (int s = 0; s < 4; ++s) {
        for (int r = 0; r < 8; ++r) {
            deck.emplace_back(Suit(s), Rank(r));
        }
    }

    // Shuffle
    std::random_device rd;
    std::mt19937 g(rd());
    std::shuffle(deck.begin(), deck.end(), g);

    // Deal
    std::array<CardSet, 4> hands;
    for(int i=0; i<8; ++i) hands[0].add(deck[i]);
    for(int i=8; i<16; ++i) hands[1].add(deck[i]);
    for(int i=16; i<24; ++i) hands[2].add(deck[i]);
    for(int i=24; i<32; ++i) hands[3].add(deck[i]);

    MinimaxSolver solver;
    std::vector<std::pair<int, Card>> current_trick;
    
    // Solve with random contract
    // Contract: Spades, 80, Player 1
    int score = solver.solve(hands, Suit::SPADES, 1, current_trick, 1, 0, 0);

    std::cout << "Random Hand Score: " << score << std::endl;

    // Sanity check: score should be between 0 and 252
    assert(score >= 0 && score <= 252);

    std::cout << "test_random_hands PASSED" << std::endl;
}

void test_belote_split() {
    std::cout << "Running test_belote_split..." << std::endl;

    // Test a case where the team has K and Q of trumps, but SPLIT between partners.
    // Result should be Capot (252) but NO Belote (20).
    // Total: 252.

    std::array<CardSet, 4> hands;
    
    // Player 0 (North): All Hearts EXCEPT King.
    // 7, 8, 9, 10, J, Q, A
    hands[0].add(Card(Suit::HEARTS, Rank::SEVEN));
    hands[0].add(Card(Suit::HEARTS, Rank::EIGHT));
    hands[0].add(Card(Suit::HEARTS, Rank::NINE));
    hands[0].add(Card(Suit::HEARTS, Rank::TEN));
    hands[0].add(Card(Suit::HEARTS, Rank::JACK));
    hands[0].add(Card(Suit::HEARTS, Rank::QUEEN));
    hands[0].add(Card(Suit::HEARTS, Rank::ACE));
    // And one side ace to ensure 8 cards. Ace of Spades.
    hands[0].add(Card(Suit::SPADES, Rank::ACE));

    // Player 2 (South): King of Hearts + 7 others (Winners/Solids)
    hands[2].add(Card(Suit::HEARTS, Rank::KING));
    // Give P2 Ace of Clubs, Ace of Diamonds to ensure strength
    hands[2].add(Card(Suit::CLUBS, Rank::ACE));
    hands[2].add(Card(Suit::DIAMONDS, Rank::ACE));
    
    // Fill rest with low cards for P1, P3 and remaining for P2
    std::vector<Card> deck;
    for (int s = 0; s < 4; ++s) {
        for (int r = 0; r < 8; ++r) {
            Card c{Suit(s), Rank(r)};
            if (hands[0].contains(c) || hands[2].contains(c)) continue;
            deck.push_back(c);
        }
    }
    
    // Distribute remaining cards
    // P2 needs 5 more
    // P1 needs 8
    // P3 needs 8
    // Deck size should be 32 - 8 - 3 = 21. Wait.
    // P0 has 8. P2 has 3. Total 11. Remaining 21.
    // P2 needs 5. P1 8. P3 8. 5+8+8 = 21. perfect.
    
    int deck_idx = 0;
    for(int i=0; i<5; ++i) hands[2].add(deck[deck_idx++]);
    for(int i=0; i<8; ++i) hands[1].add(deck[deck_idx++]);
    for(int i=0; i<8; ++i) hands[3].add(deck[deck_idx++]);

    MinimaxSolver solver;
    std::vector<std::pair<int, Card>> current_trick;
    
    // Contract: Hearts, 80, Player 0
    // Partners P0 and P2 have all trumps + aces. Capot is guaranteed.
    int score = solver.solve(hands, Suit::HEARTS, 0, current_trick, 0, 0, 0);

    std::cout << "Score obtained (Split Belote): " << score << std::endl;

    // Expected: 252 (Capot)
    // If Belote was wrongly awarded (merged team hands check?), it would be 272.
    assert(score == 252);
    
    std::cout << "test_belote_split PASSED" << std::endl;
}

void test_capot_scoring() {
    std::cout << "Running test_capot_scoring..." << std::endl;

    // Setup "God Hand" for Player 0 (North) -> All Hearts
    std::array<CardSet, 4> hands;
    
    // Player 0: All Hearts (Trump)
    std::vector<Rank> ranks = {Rank::SEVEN, Rank::EIGHT, Rank::NINE, Rank::TEN, 
                               Rank::JACK, Rank::QUEEN, Rank::KING, Rank::ACE};
    
    for (auto r : ranks) {
        hands[0].add(Card(Suit::HEARTS, r));
    }

    // Distribute other cards to P1, P2, P3
    // We just need valid cards, exact distribution matters less as P0 wins everything
    // But we must ensure no overlap.
    std::vector<Card> others;
    for (int s = 1; s <= 3; ++s) { // DIAMONDS, CLUBS, SPADES
        for (auto r : ranks) {
            others.push_back(Card((Suit)s, r));
        }
    }

    // P1 gets 8, P2 gets 8, P3 gets 8
    for(int i=0; i<8; ++i) hands[1].add(others[i]);
    for(int i=8; i<16; ++i) hands[2].add(others[i]);
    for(int i=16; i<24; ++i) hands[3].add(others[i]);

    MinimaxSolver solver;
    std::vector<std::pair<int, Card>> current_trick;
    
    // Contract: Hearts, 80, Player 0 (North)
    // Starter: 0
    int score = solver.solve(hands, Suit::HEARTS, 0, current_trick, 0, 0, 0);

    std::cout << "Score obtained: " << score << std::endl;

    // Expected: 162 (points) + 90 (capot) + 20 (Belote) = 272
    assert(score == 272);
    
    std::cout << "test_capot_scoring PASSED" << std::endl;
}

int main() {
    try {
        test_capot_scoring();
        test_random_hands();
        test_belote_split();
    } catch (const std::exception& e) {
        std::cerr << "Test failed with exception: " << e.what() << std::endl;
        return 1;
    }
    return 0;
}
