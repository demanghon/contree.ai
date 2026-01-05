import sys
import os
import cointree_cpp
import time

# Enums
Suit = cointree_cpp.Suit
Rank = cointree_cpp.Rank
Card = cointree_cpp.Card

def create_god_hand_hearts() -> list[list[Card]]:
    # Player 0: All Hearts (Trump)
    p0 = [Card(Suit.HEARTS, r) for r in [Rank.JACK, Rank.NINE, Rank.ACE, Rank.TEN, Rank.KING, Rank.QUEEN, Rank.EIGHT, Rank.SEVEN]]
    
    deck = []
    for s in [Suit.DIAMONDS, Suit.CLUBS, Suit.SPADES]:
        for r in [Rank.SEVEN, Rank.EIGHT, Rank.NINE, Rank.TEN, Rank.JACK, Rank.QUEEN, Rank.KING, Rank.ACE]:
            deck.append(Card(s, r))
            
    p1 = deck[0:8]
    p2 = deck[8:16]
    p3 = deck[16:24]
    
    return [p0, p1, p2, p3]

def test_solve_all():
    print("Testing solve_all_suits...")
    
    # 1. God Hand in Hearts
    hands = create_god_hand_hearts()
    
    # Solve for all suits
    # Contract: 80 (Value doesn't affect raw points much unless we check contract success, but solver returns score)
    # Player 0 declares.
    t0 = time.time()
    scores = cointree_cpp.solve_all_suits(hands, 0, [], 0, 0, 0)
    dt = time.time() - t0
    
    print(f"Time: {dt*1000:.2f} ms")
    print("Scores by Suit:")
    for suit, score in scores.items():
        print(f"  {suit}: {score}")
        
    # Validation
    # Hearts: Should be 272 (Capot + Belote)
    hearts_score = scores[Suit.HEARTS]
    print(f"Hearts Score: {hearts_score} (Expected 272)")
    
    if hearts_score != 272:
        print("FAIL: Hearts score incorrect")
        sys.exit(1)
        
    # Spades/Diamonds/Clubs: Should be much lower as P0 has no trumps in those
    # Actually P0 has *NO* cards of those suits, so he cannot follow suit or trump.
    # However, his partner might have some.
    # But generally, with 8 small hearts when Hearts is NOT trump, they are just generic cards.
    # Assuming standard distribution for others, the score should be low.
    
    other_suits = [Suit.DIAMONDS, Suit.CLUBS, Suit.SPADES]
    for s in other_suits:
        if scores[s] > 100:
            print(f"WARNING: Score for {s} seems high: {scores[s]}")
            
    print("test_solve_all PASSED")

if __name__ == "__main__":
    test_solve_all()
