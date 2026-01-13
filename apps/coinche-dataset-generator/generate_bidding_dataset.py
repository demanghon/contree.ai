import sys
import os
import random
import time
import threading
import argparse
import numpy as np
import pandas as pd
from typing import List, Tuple, Optional
from dataclasses import dataclass
from enum import Enum, auto

# Add bindings to path
BINDINGS_PATH = os.path.join(os.path.dirname(__file__), "../coinche-cpp/bin")
sys.path.append(BINDINGS_PATH)

import cointree_cpp
from cointree_cpp import Card, Suit, Rank

# Ranks mapping
RANK_7 = Rank.SEVEN
RANK_8 = Rank.EIGHT
RANK_9 = Rank.NINE
RANK_10 = Rank.TEN
RANK_J = Rank.JACK
RANK_Q = Rank.QUEEN
RANK_K = Rank.KING
RANK_A = Rank.ACE

RANK_MAP = [RANK_7, RANK_8, RANK_9, RANK_10, RANK_J, RANK_Q, RANK_K, RANK_A]

# Trump Order: J, 9, A, 10, K, Q, 8, 7
TRUMP_ORDER_RANKS = [RANK_J, RANK_9, RANK_A, RANK_10, RANK_K, RANK_Q, RANK_8, RANK_7]
# Side Order: A, 10, K, Q, J, 9, 8, 7
SIDE_ORDER_RANKS = [RANK_A, RANK_10, RANK_K, RANK_Q, RANK_J, RANK_9, RANK_8, RANK_7]

def create_full_deck() -> List[int]:
    """Returns list of card IDs (0..31)"""
    return list(range(32))

class GenStrategy(Enum):
    RANDOM = auto()
    FORCE_CAPOT = auto()
    FORCE_BELOTE = auto()
    FORCE_SHAPE = auto()

class HandBuilder:
    def __init__(self, trump: int):
        self.trump = trump
        self.forced_cards: List[int] = [] # List of Card IDs
        self.shape: Optional[List[int]] = None # [count_trump, count_s1, count_s2, count_s3]

    def force_card(self, suit: int, rank_enum: Rank):
        # Convert Rank Enum to integer 0..7
        # Actually bindings might expose rank as enum. 
        # Card ID = suit * 8 + rank_index
        # We need check how Rank maps to int in C++. 
        # Usually SEVEN=0, ACE=7.
        # Let's assume standard mapping: 
        # SEVEN=0, EIGHT=1, NINE=2, TEN=3, JACK=4, QUEEN=5, KING=6, ACE=7
        # bindings.cpp: .value("SEVEN", Rank::SEVEN) etc.
        # We can reconstruct card ID.
        r_int = int(rank_enum)
        c_id = suit * 8 + r_int
        if c_id not in self.forced_cards:
            self.forced_cards.append(c_id)

    def force_shape(self, shape: List[int]):
        self.shape = shape

    def _count_suit_in_hand(self, hand_ids: List[int], suit: int) -> int:
        return sum(1 for c in hand_ids if (c // 8) == suit)

    def build(self) -> List[List[Card]]:
        deck = create_full_deck()
        
        # Remove forced cards from deck
        for c in self.forced_cards:
            if c in deck:
                deck.remove(c)
        
        # 1. Assign forced cards to South (P0)
        p0_cards = list(self.forced_cards)
        
        # 2. Fulfill Shape
        if self.shape:
            # shape: [trump, s1, s2, s3]
            # s1 = (trump+1)%4 ...
            suits = [
                self.trump,
                (self.trump + 1) % 4,
                (self.trump + 2) % 4,
                (self.trump + 3) % 4
            ]
            
            for i, count in enumerate(self.shape):
                suit = suits[i]
                current_count = self._count_suit_in_hand(p0_cards, suit)
                
                if current_count < count:
                    needed = count - current_count
                    available = [c for c in deck if (c // 8) == suit]
                    random.shuffle(available)
                    
                    for _ in range(needed):
                        if available:
                            c = available.pop()
                            p0_cards.append(c)
                            deck.remove(c)

        # 3. Fill remaining p0 slots (up to 8)
        if len(p0_cards) < 8:
            needed = 8 - len(p0_cards)
            random.shuffle(deck)
            for _ in range(needed):
                p0_cards.append(deck.pop())
        
        # 4. Deal remaining to others
        random.shuffle(deck)
        p1_cards = deck[0:8]
        p2_cards = deck[8:16]
        p3_cards = deck[16:24]
        
        # Convert IDs to Card objects
        hands_ids = [p0_cards, p1_cards, p2_cards, p3_cards]
        hands_obj = []
        for h in hands_ids:
            # Sort for neatness (optional)
            h.sort()
            cards = [Card(c) for c in h]
            hands_obj.append(cards)
            
        return hands_obj

def generate_biased_hands(trump: int, strategy: GenStrategy, shape_arg: Optional[List[int]] = None) -> List[List[Card]]:
    builder = HandBuilder(trump)
    
    if strategy == GenStrategy.RANDOM:
        pass
        
    elif strategy == GenStrategy.FORCE_BELOTE:
        # K + Q of Trump
        builder.force_card(trump, RANK_K)
        builder.force_card(trump, RANK_Q)
        
    elif strategy == GenStrategy.FORCE_CAPOT:
        # Master Hand
        # 1. Trumps: Length 4..8. Top sequence.
        trump_len = random.randint(4, 8)
        for i in range(trump_len):
            builder.force_card(trump, TRUMP_ORDER_RANKS[i])
            
        remaining = 8 - trump_len
        
        if remaining > 0:
            # Distribute remaining among side suits
            side_indices = [1, 2, 3] # Relative to trump
            counts = [0] * 4
            for _ in range(remaining):
                idx = random.choice(side_indices)
                counts[idx] += 1
                
            for i in range(1, 4):
                if counts[i] > 0:
                    suit = (trump + i) % 4
                    cnt = counts[i]
                    for r in range(cnt):
                        builder.force_card(suit, SIDE_ORDER_RANKS[r])
                        
    elif strategy == GenStrategy.FORCE_SHAPE:
        if shape_arg:
            builder.force_shape(shape_arg)
            
    return builder.build()

def card_to_id(c: Card) -> int:
    return c.id

def format_hand(cards: List[Card]) -> str:
    # C++ Enum: HEARTS=0, DIAMONDS=1, CLUBS=2, SPADES=3
    suit_map = ['♥', '♦', '♣', '♠']
    rank_map = ['7', '8', '9', '10', 'J', 'Q', 'K', 'A'] # 0..7
    
    # Group by suit
    by_suit = {0:[], 1:[], 2:[], 3:[]}
    for c in cards:
        by_suit[int(c.suit())].append(int(c.rank()))
        
    parts = []
    for s_idx in [3, 0, 1, 2]: # Spades, Hearts, Diamonds, Clubs order purely cosmetic
            if by_suit[s_idx]:
                ranks = sorted(by_suit[s_idx], reverse=True) # A, K ...
                s_str = "".join([rank_map[r] for r in ranks])
                parts.append(f"{s_str}{suit_map[s_idx]}")
    return " ".join(parts)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=1000, help="Total number of hands to generate")
    parser.add_argument("--batch_size", type=int, default=1000, help="Hands per batch")
    parser.add_argument("--output", type=str, default="bidding_dataset.parquet", help="Final output file")
    parser.add_argument("--pimc", type=int, default=0, help="PIMC iterations (0 = Double Dummy)")
    
    args = parser.parse_args()
    
    TOTAL_COUNT = args.count
    BATCH_SIZE = args.batch_size
    OUTPUT_FILE = args.output
    
    # Setup Worker Directories
    WORK_DIR = "dist/bidding"
    os.makedirs(WORK_DIR, exist_ok=True)
    
    # Calculate number of batches
    num_batches = (TOTAL_COUNT + BATCH_SIZE - 1) // BATCH_SIZE
    
    print(f"Goal: {TOTAL_COUNT} hands in {num_batches} batches of ~{BATCH_SIZE}.")
    
    # Batch Loop
    for batch_idx in range(num_batches):
        batch_file = os.path.join(WORK_DIR, f"batch_{batch_idx}.parquet")
        
        if os.path.exists(batch_file):
            print(f"Batch {batch_idx+1}/{num_batches} already exists. Skipping.")
            continue
            
        # Determine actual size for this batch
        current_batch_size = BATCH_SIZE
        if (batch_idx + 1) * BATCH_SIZE > TOTAL_COUNT:
            current_batch_size = TOTAL_COUNT - (batch_idx * BATCH_SIZE)
            
        print(f"Processing Batch {batch_idx+1}/{num_batches} ({current_batch_size} hands)...")
        
        # 1. Generate Hands
        t_gen = time.time()
        print("  Generating hands...", end="", flush=True)
        
        # Strategy Weights
        strategies = []
        choices = [GenStrategy.RANDOM, GenStrategy.FORCE_CAPOT, GenStrategy.FORCE_BELOTE, GenStrategy.FORCE_SHAPE]
        weights = [0.4, 0.2, 0.2, 0.2]
        shapes_pool = [[5, 2, 1, 0], [4, 3, 1, 0], [4, 2, 1, 1], [3, 3, 2, 0]]
        
        generated_hands_batch = []
        for _ in range(current_batch_size):
            s = random.choices(choices, weights=weights, k=1)[0]
            shp = None
            if s == GenStrategy.FORCE_SHAPE:
                shp = random.choice(shapes_pool)
            trump = random.randint(0, 3)
            hands = generate_biased_hands(trump, s, shp)
            generated_hands_batch.append(hands)
            
        print(f" Done ({time.time() - t_gen:.2f}s)")
        
        # 2. Solve Hands
        print("  Solving...", end="")
        cointree_cpp.reset_stats()
        cointree_cpp.reset_progress()
        
        t0 = time.time()
        result_container = {}
        
        def solve_worker():
            try:
                # GIL released manually in bindings.cpp
                res = cointree_cpp.solve_batch(generated_hands_batch, 0)
                result_container['scores'] = res
            except Exception as e:
                result_container['error'] = e

        solver_thread = threading.Thread(target=solve_worker)
        solver_thread.start()
        
        while solver_thread.is_alive():
            completed = cointree_cpp.get_hands_solved()
            elapsed = time.time() - t0
            rate = completed / elapsed if elapsed > 0 else 0
            
            stats = cointree_cpp.get_stats()
            weak = stats.get('weak_hand_hits', 0)
            capot = stats.get('capot_hits', 0)
            
            # Simple in-line progress for batch
            sys.stdout.write(f"\r  Solving... {completed}/{current_batch_size} ({(completed/current_batch_size)*100:.0f}%) | Breaks: W:{weak} C:{capot} | Rate: {rate:.1f}/s")
            sys.stdout.flush()
            time.sleep(0.1)
            
        solver_thread.join()
        
        if 'error' in result_container:
            print(f"\nError in solver: {result_container['error']}")
            sys.exit(1)
            
        final_scores = result_container['scores']
        print(f"\n  Batch Solved in {time.time() - t0:.2f}s")
        
        # 3. Save Batch
        print("  Saving batch...", end="", flush=True)
        
        # Prepare Data
        south_hands_bitmaps = []
        hand_south_humans = []
        hand_west_humans = []
        hand_north_humans = []
        hand_east_humans = []
        
        for game in generated_hands_batch:
            # Human Readable
            hand_south_humans.append(format_hand(game[0]))
            hand_west_humans.append(format_hand(game[1]))
            hand_north_humans.append(format_hand(game[2]))
            hand_east_humans.append(format_hand(game[3]))
            
            # Bitmap for South
            p0 = game[0]
            bitmap = 0
            for c in p0:
                bitmap |= (1 << c.id)
            south_hands_bitmaps.append(bitmap)
            
        scores_list = final_scores.tolist()
        
        
        df = pd.DataFrame({
            "hand_south": pd.Series(south_hands_bitmaps, dtype="uint32"),
            "hand_south_human": hand_south_humans,
            "hand_west_human": hand_west_humans,
            "hand_north_human": hand_north_humans,
            "hand_east_human": hand_east_humans,
            "scores": scores_list
        })
        
        df.to_parquet(batch_file)
        print(" Done.\n")
        
    print("All batches processed. Merging...")
    
    # Merge
    all_files = sorted([os.path.join(WORK_DIR, f) for f in os.listdir(WORK_DIR) if f.endswith(".parquet")])
    if not all_files:
        print("No files to merge!")
        return

    # Use pandas concat
    dfs = []
    for f in all_files:
        dfs.append(pd.read_parquet(f))
        
    final_df = pd.concat(dfs, ignore_index=True)
    
    # Ensure output directory exists
    output_dir = os.path.dirname(OUTPUT_FILE)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        
    final_df.to_parquet(OUTPUT_FILE)
    
    print(f"Comparison: Target {TOTAL_COUNT} | Actual {len(final_df)}")
    print(f"Saved merged dataset to {OUTPUT_FILE}")
    
    # Cleanup
    print("Cleaning up intermediate files...")
    import shutil
    shutil.rmtree(WORK_DIR)
    print("Done.")

if __name__ == "__main__":
    main()
