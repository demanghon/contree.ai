
import sys
import os
import time
import random

# Add bindings to path
# Assuming we are running from project root or this file's dir, we need to find the bin dir
# relative to this file: ../coinche-cpp/bin
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
BINDINGS_PATH = os.path.normpath(os.path.join(CURRENT_DIR, "../coinche-cpp/bin"))
sys.path.append(BINDINGS_PATH)

# Also add current dir to path to import generate_bidding_dataset
sys.path.append(CURRENT_DIR)

import cointree_cpp
from generate_bidding_dataset import generate_biased_hands, GenStrategy

def main():
    COUNT = 1000
    print(f"Generating {COUNT} FORCE_CAPOT hands...")
    
    hands_data = []
    
    gen_start = time.time()
    for _ in range(COUNT):
        trump = random.randint(0, 3)
        hands = generate_biased_hands(trump, GenStrategy.FORCE_CAPOT, None)
        hands_data.append((hands, trump))
    gen_time = time.time() - gen_start
    print(f"Generation took {gen_time:.4f}s")
    
    print(f"Solving {COUNT} hands (Specific Trump only)...")
    cointree_cpp.reset_stats()
    solve_start = time.time()
    
    # Solve each hand individually for its specific trump
    for hands, trump_int in hands_data:
        # Convert int to Suit
        trump_suit = cointree_cpp.Suit(trump_int)
        # solve_game(hands, contract_suit, contract_player, current_trick, starter_player, ns_points, ew_points)
        cointree_cpp.solve_game(hands, trump_suit, 0, [], 0, 0, 0)
    
    total_time = time.time() - solve_start
    stats = cointree_cpp.get_stats()
    
    print(f"Resolution of {COUNT} hands took: {total_time:.4f} seconds")
    print(f"Average time per hand: {(total_time / COUNT) * 1000:.2f} ms")
    print(f"Hands per second: {COUNT / total_time:.2f}")
    
    print("-" * 30)
    print("Circuit Breaker Stats:")
    print(f"Weak Hand Hits: {stats.get('weak_hand_hits', 0)}")
    print(f"Capot Hits:     {stats.get('capot_hits', 0)}")
    print("-" * 30)

if __name__ == "__main__":
    main()
