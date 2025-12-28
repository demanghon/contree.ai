
import coinche_engine
import sys

def count_bits(n):
    return bin(n).count('1')

try:
    print("Generating hands...")
    hands_flat, strategies = coinche_engine.generate_bidding_hands(100) # Check 100 samples
    
    # hands_flat is [h0, h1, h2, h3, h0, h1...]
    for i in range(len(hands_flat)):
        h = hands_flat[i]
        c = count_bits(h)
        if c != 8:
            print(f"ERROR: Hand {i} has {c} cards! Expected 8.")
            sys.exit(1)
            
    print("SUCCESS: All 400 hands have 8 cards.")
    
except Exception as e:
    print(f"Crash: {e}")
    sys.exit(1)
