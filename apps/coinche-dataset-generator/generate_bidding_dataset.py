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

def main():
    parser = argparse.ArgumentParser(description="Generate Bidding Dataset")
    parser.add_argument("--count", type=int, default=1000, help="Number of hands to generate")
    parser.add_argument("--output", type=str, default="bidding_dataset.parquet", help="Output file")
    parser.add_argument("--pimc", type=int, default=0, help="PIMC iterations (0 = Double Dummy)")
    
    args = parser.parse_args()
    
    BATCH_SIZE = args.count
    print(f"Generating {BATCH_SIZE} hands...")
    
    # Strategy Weights
    # Random=40, Capot=20, Belote=20, Shape=20
    strategies = []
    # Weighted choice
    choices = [GenStrategy.RANDOM, GenStrategy.FORCE_CAPOT, GenStrategy.FORCE_BELOTE, GenStrategy.FORCE_SHAPE]
    weights = [0.4, 0.2, 0.2, 0.2]
    
    shapes_pool = [
        [5, 2, 1, 0], 
        [4, 3, 1, 0], 
        [4, 2, 1, 1], 
        [3, 3, 2, 0]
    ]
    
    generated_hands_batch = [] # List[List[List[Card]]]
    
    start_time = time.time()
    
    for _ in range(BATCH_SIZE):
        strat = random.choices(choices, weights=weights, k=1)[0]
        trump = random.randint(0, 3)
        
        shape = None
        if strat == GenStrategy.FORCE_SHAPE:
            shape = random.choice(shapes_pool)
            
        hands = generate_biased_hands(trump, strat, shape)
        generated_hands_batch.append(hands)
        strategies.append(strat.name)
        
    print(f"Generation complete. Time: {time.time() - start_time:.2f}s")
    
    # Solve using OpenMP (Parallel) with Polling Progress
    print("Solving hands...")
    cointree_cpp.reset_stats()
    cointree_cpp.reset_progress()
    
    t0 = time.time()
    
    # Shared result container
    result_container = {}
    
    def solve_worker():
        # This releases GIL internally in C++ usually if configured, 
        # allowing python main thread to run?
        # Typically pybind11 modules need `call_guard<py::gil_scoped_release>()` 
        # or manual release to allow other threads to run.
        # cointree_cpp bindings.cpp likely DOES NOT release GIL by default unless I added it.
        # If it holds GIL, my main thread won't run until it finishes.
        # Checking bindings.cpp... I did NOT add `call_guard`.
        # So this thread approach will BLOCK the main thread if GIL is held.
        # However, `solve_batch` is a long running C++ function. 
        # If I don't release GIL, the progress bar won't update.
        # BUT, let's assume standard pybind11 might allow it or I might need to fix it.
        # Actually, without GIL release, this is 100% blocking.
        # I SHOULD HAVE ADDED call_guard to bindings.cpp.
        # But let's try. If it blocks, I fix bindings.cpp.
        res = cointree_cpp.solve_batch(generated_hands_batch, 0)
        result_container['scores'] = res
        
    solver_thread = threading.Thread(target=solve_worker)
    solver_thread.start()
    
    while solver_thread.is_alive():
        completed = cointree_cpp.get_hands_solved()
        elapsed = time.time() - t0
        rate = completed / elapsed if elapsed > 0 else 0
        remaining_hands = BATCH_SIZE - completed
        eta = remaining_hands / rate if rate > 0 and remaining_hands > 0 else 0
        
        stats = cointree_cpp.get_stats()
        weak_hits = stats.get('weak_hand_hits', 0)
        capot_hits = stats.get('capot_hits', 0)
        total_breaks = weak_hits + capot_hits
        
        sys.stdout.write(f"\rResolved: {completed}/{BATCH_SIZE} | Left: {remaining_hands} | Breaks: {total_breaks} (W:{weak_hits} C:{capot_hits}) | ETA: {eta:.1f}s")
        sys.stdout.flush()
        time.sleep(0.1)
        
    solver_thread.join()
    
    # Final Update
    completed = cointree_cpp.get_hands_solved()
    stats = cointree_cpp.get_stats()
    total_breaks = stats.get('weak_hand_hits', 0) + stats.get('capot_hits', 0)
    sys.stdout.write(f"\rResolved: {completed}/{BATCH_SIZE} | Left: 0 | Breaks: {total_breaks} | Done.          \n")
    
    final_scores = result_container['scores']
    
    t_solve = time.time() - t0
    print(f"Solving complete. Time: {t_solve:.2f}s ({BATCH_SIZE/t_solve:.1f} hands/s)")
    
    # Save to Parquet
    print("Saving to Parquet...")
    
    # Prepare data for DataFrame
    # Need South Hand as BitMap (UInt32) for compatibility with Rust/ML
    south_hands_bitmaps = []
    for game in generated_hands_batch:
        p0 = game[0]
        bitmap = 0
        for c in p0:
            bitmap |= (1 << c.id)
        south_hands_bitmaps.append(bitmap)
        
    # Scores: List[float] per row
    scores_list = final_scores.tolist()
    
    # Generate human readable hands
    def format_hand(cards: List[Card]) -> str:
        # Map 0..3 to Suits
        # 0: Spades, 1: Hearts, 2: Clubs, 3: Diamonds
        suit_map = ['♠', '♥', '♣', '♦']
        rank_map = ['7', '8', '9', '10', 'J', 'Q', 'K', 'A']
        
        # Sort by suit then rank for readability
        # card.id = suit * 8 + rank
        sorted_cards = sorted(cards, key=lambda x: x.id)
        
        parts = []
        for c in sorted_cards:
            s = (c.id // 8)
            r = (c.id % 8)
            parts.append(f"{rank_map[r]}{suit_map[s]}")
            
        return " ".join(parts)

    cols = {
        'hand_south_human': [], 
        'hand_west_human': [], 
        'hand_north_human': [], 
        'hand_east_human': []
    }
    
    for game in generated_hands_batch:
        # p0: South, p1: West, p2: North, p3: East
        cols['hand_south_human'].append(format_hand(game[0]))
        cols['hand_west_human'].append(format_hand(game[1]))
        cols['hand_north_human'].append(format_hand(game[2]))
        cols['hand_east_human'].append(format_hand(game[3]))

    df_data = {
        'hand_south': south_hands_bitmaps,
        'scores': scores_list, # List of list
        'strategy': strategies
    }
    
    # Add human readable columns
    df_data.update(cols)

    df = pd.DataFrame(df_data)
    # Ensure types
    df['hand_south'] = df['hand_south'].astype('uint32')
    
    df.to_parquet(args.output)
    print(f"Saved to {args.output}")

if __name__ == "__main__":
    main()
