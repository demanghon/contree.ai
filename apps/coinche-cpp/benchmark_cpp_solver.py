
import sys
import os
import time
import random
from dataclasses import dataclass
from typing import List, Tuple

# Add the C++ library path
sys.path.append(os.path.join(os.path.dirname(__file__), "src", "engine"))

try:
    import cointree_cpp
except ImportError as e:
    print(f"Error importing cointree_cpp: {e}")
    sys.exit(1)

# Enums
Suit = cointree_cpp.Suit
Rank = cointree_cpp.Rank
Card = cointree_cpp.Card

def create_deck() -> List[Card]:
    deck = []
    for s in [Suit.HEARTS, Suit.DIAMONDS, Suit.CLUBS, Suit.SPADES]:
        for r in [Rank.SEVEN, Rank.EIGHT, Rank.NINE, Rank.TEN, Rank.JACK, Rank.QUEEN, Rank.KING, Rank.ACE]:
            deck.append(Card(s, r))
    return deck

def deal_hands(deck: List[Card]) -> List[List[Card]]:
    random.shuffle(deck)
    return [deck[0:8], deck[8:16], deck[16:24], deck[24:32]]

def create_god_hand() -> List[List[Card]]:
    # Create a hand where Player 0 has all top trumps in Hearts
    # This is just a specific configuration test
    # Player 0: All Hearts (Trump)
    p0 = [Card(Suit.HEARTS, r) for r in [Rank.JACK, Rank.NINE, Rank.ACE, Rank.TEN, Rank.KING, Rank.QUEEN, Rank.EIGHT, Rank.SEVEN]]
    
    # Other cards distributed to others
    others = []
    for s in [Suit.DIAMONDS, Suit.CLUBS, Suit.SPADES]:
        for r in [Rank.SEVEN, Rank.EIGHT, Rank.NINE, Rank.TEN, Rank.JACK, Rank.QUEEN, Rank.KING, Rank.ACE]:
            others.append(Card(s, r))
    
    # Shuffle others to be fair? Or deterministic? 
    # Let's keep it deterministic for "God Hand" consistency usually
    # But for now just split
    p1 = others[0:8]
    p2 = others[8:16]
    p3 = others[16:24]
    
    return [p0, p1, p2, p3]

def run_benchmark(num_random_hands: int = 100):
    print(f"Running benchmark with {num_random_hands} random hands...")
    
    # Warmup / God Hand
    print("\n--- God Hand Test ---")
    god_hands = create_god_hand()
    # Contract: Hearts, 80, Player 0
    t0 = time.time()
    # Arguments: hands, contract_suit, contract_amount, contract_player, current_trick, starter_player, ns_points, ew_points
    score = cointree_cpp.solve_game(god_hands, Suit.HEARTS, 80, 0, [], 0, 0, 0)
    dt = time.time() - t0
    print(f"God Hand Score: {score}")
    print(f"Time: {dt*1000:.2f} ms")
    
    # Random Hands
    print(f"\n--- Random Hands Test ({num_random_hands} iterations) ---")
    deck = create_deck()
    times = []
    
    for i in range(num_random_hands):
        hands = deal_hands(deck) # Shuffles inside
        # Random contract
        contract_suit = Suit(random.randint(0, 3))
        contract_player = random.randint(0, 3)
        starter = 0
        
        t_start = time.perf_counter()
        cointree_cpp.solve_game(hands, contract_suit, 80, contract_player, [], starter, 0, 0)
        t_end = time.perf_counter()
        
        times.append((t_end - t_start) * 1000)
    
    avg_time = sum(times) / len(times)
    min_time = min(times)
    max_time = max(times)
    total_time = sum(times) / 1000
    
    print(f"Total Time: {total_time:.2f} s")
    print(f"Average Time: {avg_time:.2f} ms")
    print(f"Min Time: {min_time:.2f} ms")
    print(f"Max Time: {max_time:.2f} ms")

if __name__ == "__main__":
    run_benchmark(100)
