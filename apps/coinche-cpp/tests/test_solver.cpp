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
    int score = solver.solve(hands, Suit::SPADES, 80, 1, current_trick, 1, 0, 0);

    std::cout << "Random Hand Score: " << score << std::endl;

    // Sanity check: score should be between 0 and 252
    assert(score >= 0 && score <= 252);

    std::cout << "test_random_hands PASSED" << std::endl;
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
    int score = solver.solve(hands, Suit::HEARTS, 80, 0, current_trick, 0, 0, 0);

    std::cout << "Score obtained: " << score << std::endl;

    // Expected: 162 (points) + 90 (capot) = 252
    assert(score == 252);
    
    std::cout << "test_capot_scoring PASSED" << std::endl;
}

int main() {
    try {
        test_capot_scoring();
        test_random_hands();
    } catch (const std::exception& e) {
        std::cerr << "Test failed with exception: " << e.what() << std::endl;
        return 1;
    }
    return 0;
}
