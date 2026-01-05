
import coinche_engine
import time

# Helper to create hand (same logic as bidding tests)
# 0..7: 7, 8, 9, 10, J, Q, K, A
RANK_7 = 0
RANK_8 = 1
RANK_9 = 2
RANK_10 = 3
RANK_J = 4
RANK_Q = 5
RANK_K = 6
RANK_A = 7

DIAMONDS = 0
SPADES = 1
HEARTS = 2
CLUBS = 3

def card(suit, rank):
    return 1 << (suit * 8 + rank)

def make_weak_hand(trump_suit=HEARTS):
    # 7, 8 in all suits. 
    # Potential should be 0.
    h = 0
    h |= card(HEARTS, RANK_7)
    h |= card(HEARTS, RANK_8)
    h |= card(SPADES, RANK_7)
    h |= card(SPADES, RANK_8)
    h |= card(DIAMONDS, RANK_7)
    h |= card(DIAMONDS, RANK_8)
    h |= card(CLUBS, RANK_7)
    h |= card(CLUBS, RANK_8)
    return h

def make_capot_hand(trump_suit=HEARTS):
    # All trumps
    h = 0
    for r in range(8):
        h |= card(trump_suit, r)
    return h

def main():
    print("Creating specific hands...")
    hands = []
    
    # 1. Weak Hand
    hands.append(make_weak_hand())
    
    # 2. Capot Hand
    hands.append(make_capot_hand())
    
    # 3. Random 'Normal' Hand (Top 4 trumps + garbage)
    # Should NOT be weak, NOT be capot.
    h = 0
    h |= card(HEARTS, RANK_J)
    h |= card(HEARTS, RANK_9)
    h |= card(HEARTS, RANK_A)
    h |= card(HEARTS, RANK_10)
    h |= card(SPADES, RANK_7)
    h |= card(SPADES, RANK_8)
    h |= card(DIAMONDS, RANK_7)
    h |= card(DIAMONDS, RANK_8)
    hands.append(h)

    # Pad with 3 dummy hands for each valid hand to make full deals (S, W, N, E)
    # We only care about South (index 0) for these metrics.
    full_hands = []
    for h in hands:
        full_hands.append(h)    # South
        full_hands.append(0)    # West
        full_hands.append(0)    # North
        full_hands.append(0)    # East

    print(f"Solving batch of {len(full_hands)} hands ({len(full_hands)//4} deals)...")
    print("Expect: Weak: 1, Capot: 1")
    
    # PIMC=0, TT=None
    scores = coinche_engine.solve_bidding_batch(full_hands, 0, None)
    
    print("Solver returned.")
    print("Scores:", scores)

if __name__ == "__main__":
    main()
