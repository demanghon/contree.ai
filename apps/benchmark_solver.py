import sys
import os
import time
import random

# Ensure we can import coinche_engine from the built extension
# Assuming build is done in apps/coinche-engine/target/release/libcoinche_engine.so or similar
# But usually python bindings are installed or in python path.
# User environment seems to have it available or we rely on just compiled path.

try:
    import coinche_engine
except ImportError:
    print("coinche_engine not found. Please ensure it is installed or in PYTHONPATH.")
    # Fallback to local debug build if needed?
    sys.exit(1)

def count_trumps(hand, trump_suit):
    count = 0
    # Valet and 9 checks
    has_valet = False
    has_nine = False
    
    # Iterate bits
    for i in range(32):
        if (hand & (1 << i)) != 0:
            suit = i // 8
            rank = i % 8
            if suit == trump_suit:
                count += 1
                if rank == 4: # Jack
                    has_valet = True
                if rank == 2: # 9 (if trump)
                    has_nine = True
    return count, has_valet, has_nine

def main():
    print("Generating 500 hands for benchmark...")
    
    # We need to generate hands until we have enough "Strong" hands (4+ trumps + J + 9)
    # Target: 500 total, with at least 100 strong.
    
    strong_hands_needed = 100
    total_hands = 500
    
    final_hands = [] # List of tuples (hands_array, trump)
    
    # Batch generation is 4 hands per sample? No, generate_bidding_hands returns N samples.
    # But solve_gameplay_batch needs specific inputs.
    # Let's use coinche_engine.generate_raw_gameplay_batch(N) to get raw states.
    
    collected = 0
    strong_count = 0
    
    # We will collect indices from large batch
    print("Sampling raw states...")
    
    hands_list = []
    boards_list = []
    history_list = []
    trumps_list = []
    tricks_won_list = []
    players_list = []
    
    while len(hands_list) < total_hands:
        # Generate batch of 100
        batch_size = 100
        (hands_flat, boards, history, trumps, tricks_won, players) = coinche_engine.generate_raw_gameplay_batch(batch_size)
        
        for i in range(batch_size):
            # Check if this hand is "strong" for the current player
            p = players[i]
            my_hand = hands_flat[i*4 + p]
            trump = trumps[i]
            
            cnt, has_J, has_9 = count_trumps(my_hand, trump)
            
            is_strong = (cnt >= 4 and has_J and has_9)
            
            if is_strong:
                if strong_count < strong_hands_needed or len(hands_list) < total_hands:
                   pass # Keep it
                elif len(hands_list) >= total_hands:
                    continue 
            
            # Simplified Logic: Just add if we need hands.
            # If we need strong hands specifically, prioritize them?
            # Actually, current generator creates random states (often mid-game).
            # Strong hands at START are easier to find. Mid-game 'strong' means strong remaining?
            # Let's just take 500 random hands and count how many are strong.
            # If not enough, we might need a better generator, but for now just run on 500 random phases.
            # The prompt asked "Assure-toi d'inclure au moins 100 mains avec un fort potentiel".
            
            if is_strong:
                strong_count += 1
                
            hands_list.append((hands_flat[i*4:i*4+4]))
            boards_list.append(boards[i])
            history_list.append(history[i])
            trumps_list.append(trumps[i])
            tricks_won_list.append(tricks_won[i])
            players_list.append(players[i])
            
            if len(hands_list) >= total_hands:
                if strong_count < strong_hands_needed:
                    # If we filled quota but lack strong hands, replace non-strong with strong?
                    # Remove last if not strong?
                    if not is_strong:
                        hands_list.pop()
                        boards_list.pop()
                        history_list.pop()
                        trumps_list.pop()
                        tricks_won_list.pop()
                        players_list.pop()
                        continue
                else:
                    break
        
        print(f"Collected {len(hands_list)} hands. Strong: {strong_count}")
    
    print(f"\nRunning Benchmark on {len(hands_list)} hands (Strong: {strong_count})...")
    
    # Flatten hands again
    flat_hands_in = []
    for h in hands_list:
        flat_hands_in.extend(h)
        
    start_time = time.time()
    
    # Solve batch
    # PIMC = 20
    pimc = 1
    # Solve in chunks for progress bar
    # Batch size needs to be large enough to saturate CPU cores (Rayon parallelizes within batch)
    # 1 = Single Threaded. 100 = Uses up to 100 threads comfortably.
    chunk_size = 100 
    total = len(hands_list)

    try:
        from tqdm import tqdm
        pbar = tqdm(total=total, desc="Solving", unit="hand")
    except ImportError:
        print(f"Solving {total} hands in batches of {chunk_size}...")
        pbar = None

    all_best_cards = []
    all_best_scores = []
    
    # Flatten hands is tricky because solve_gameplay_batch expects flat hands for the whole batch.
    # We need to slice the list of input arrays, THEN flatten the slice.
    
    for i in range(0, total, chunk_size):
        end = min(i + chunk_size, total)
        
        # Slice inputs
        batch_hands_lists = hands_list[i:end]
        batch_boards = boards_list[i:end]
        batch_history = history_list[i:end]
        batch_trumps = trumps_list[i:end]
        batch_tricks_won = tricks_won_list[i:end]
        batch_players = players_list[i:end]
        
        # Flatten hands for this batch
        batch_hands_flat = []
        for h in batch_hands_lists:
            batch_hands_flat.extend(h)
            
        (b_cards, b_scores, b_valid) = coinche_engine.solve_gameplay_batch(
            batch_hands_flat,
            batch_boards,
            batch_history,
            batch_trumps,
            batch_tricks_won,
            batch_players,
            pimc,
            22 # TT Log2
        )
        
        all_best_cards.extend(b_cards)
        all_best_scores.extend(b_scores)
        
        if pbar:
            pbar.update(end - i)
        else:
            print(f"Solved {end}/{total}...")
            
    if pbar:
        pbar.close()
        
    best_cards = all_best_cards
    best_scores = all_best_scores
    
    end_time = time.time()
    total_time = end_time - start_time
    avg_time = total_time / len(hands_list)
    
    max_score = max(best_scores)
    
    # Capot check
    # Capot is total > 162. Usually 162 + 90 = 252.
    # Scores can be up to 162 + 20(Belote) + 90(Capot) = 272?
    capot_count = sum(1 for s in best_scores if s >= 200) # Threshold for Capot-ish
    
    print("-" * 40)
    print("BENCHMARK RESULTS")
    print("-" * 40)
    print(f"Total Hands: {len(hands_list)}")
    print(f"Strong Hands: {strong_count}")
    print(f"Total Time: {total_time:.2f}s")
    print(f"Avg Time/Hand: {avg_time:.4f}s")
    print(f"Max Score (Random): {max_score}")
    print(f"Capots Found (Random): {capot_count}")

    # Inject a God Hand to verify Capot detection in Python Binding
    print("\nVerifying Capot with Synthetic 'God Hand'...")
    # P0 has all top trumps (J, 9, A, 10, K, Q, 8, 7)
    # P1, P2, P3 have other suits.
    # This guarantees 8 tricks and Capot.
    
    # Construct hands
    # P0: Hearts (Trump) 0..7
    # P1: Spades 0..7
    # P2: Diamonds 0..7
    # P3: Clubs 0..7
    
    # Bitmasks. 
    # Hearts is suit 2. Spades 1. Diamonds 0. Clubs 3.
    # Ranks 0-7.
    
    def make_hand(suit):
        h = 0
        for r in range(8):
            h |= (1 << (suit * 8 + r))
        return h

    god_hand_p0 = make_hand(2) # Hearts
    op1 = make_hand(1) # Spades
    op2 = make_hand(0) # Diamonds
    op3 = make_hand(3) # Clubs
    
    # Flatten
    god_hands_flat = [god_hand_p0, op1, op2, op3]
    god_board = [] # Empty board
    god_history = 0
    god_trump = 2 # Hearts
    god_player = 0 # P0 leads
    
    print("Solving Full God Hand (32 cards)...")
    # P0 has Hearts (Trump)
    # P1 Spades
    # P2 Diamonds
    # P3 Clubs
    
    def make_hand(suit):
        h = 0
        for r in range(8):
            h |= (1 << (suit * 8 + r))
        return h

    h0 = make_hand(2) # Hearts
    h1 = make_hand(1) # Spades
    h2 = make_hand(0) # Diamonds
    h3 = make_hand(3) # Clubs
    
    hands_full = [h0, h1, h2, h3]
    
    start_god = time.time()
    (g_best, g_scores, g_valid) = coinche_engine.solve_gameplay_batch(
        hands_full,
        [god_board],
        [god_history],
        [god_trump],
        [[0, 0]], # tricks_won
        [god_player],
        1, # PIMC
        22 # TT Log2 (64MB)
    )
    end_god = time.time()
    
    god_score = g_scores[0]
    print(f"God Hand Score: {god_score} (Time: {end_god - start_god:.2f}s)")
    
    if god_score >= 250:
        print("SUCCESS: Capot Detected (>= 250)!")
    else:
        print(f"FAILURE: Capot NOT Detected (Score: {god_score})")

    print("-" * 40)

if __name__ == "__main__":
    main()
