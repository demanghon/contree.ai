import sys
import os
import time
import pickle
import json
import argparse
import random
from datetime import datetime
from enum import Enum, auto
from typing import List, Optional

# Add bindings to path (../bin relative to benchmark dir)
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
# coinche-cpp/benchmark -> coinche-cpp/bin
BINDINGS_PATH = os.path.join(SCRIPT_DIR, "../bin")
sys.path.append(BINDINGS_PATH)

try:
    import cointree_cpp
    from cointree_cpp import Card, Suit, Rank
except ImportError:
    print(f"Error: cointree_cpp module not found in {BINDINGS_PATH}")
    sys.exit(1)

# Hand Generation Logic (Duplicated for standalone capability)
class GenStrategy(Enum):
    RANDOM = auto()
    FORCE_CAPOT = auto()
    FORCE_BELOTE = auto()
    FORCE_SHAPE = auto()

RANK_7 = Rank.SEVEN; RANK_8 = Rank.EIGHT; RANK_9 = Rank.NINE; RANK_10 = Rank.TEN
RANK_J = Rank.JACK; RANK_Q = Rank.QUEEN; RANK_K = Rank.KING; RANK_A = Rank.ACE
RANK_MAP = [RANK_7, RANK_8, RANK_9, RANK_10, RANK_J, RANK_Q, RANK_K, RANK_A]
TRUMP_ORDER_RANKS = [RANK_J, RANK_9, RANK_A, RANK_10, RANK_K, RANK_Q, RANK_8, RANK_7]
SIDE_ORDER_RANKS = [RANK_A, RANK_10, RANK_K, RANK_Q, RANK_J, RANK_9, RANK_8, RANK_7]

def create_full_deck() -> List[int]:
    return list(range(32))

class HandBuilder:
    def __init__(self, trump: int):
        self.trump = trump
        self.forced_cards: List[int] = [] 
        self.shape: Optional[List[int]] = None

    def force_card(self, suit: int, rank_enum: Rank):
        r_int = int(rank_enum)
        c_id = suit * 8 + r_int
        if c_id not in self.forced_cards:
            self.forced_cards.append(c_id)

    def force_shape(self, shape: List[int]):
        self.shape = shape

    def _count_suit_in_hand(self, hand_ids: List[int], suit: int) -> int:
        return sum(1 for c in hand_ids if (c // 8) == suit)

    def build(self) -> List[List[int]]:
        deck = create_full_deck()
        for c in self.forced_cards:
            if c in deck: deck.remove(c)
        p0_cards = list(self.forced_cards)
        if self.shape:
            suits = [self.trump, (self.trump+1)%4, (self.trump+2)%4, (self.trump+3)%4]
            for i, count in enumerate(self.shape):
                suit = suits[i]
                current = self._count_suit_in_hand(p0_cards, suit)
                if current < count:
                    needed = count - current
                    available = [c for c in deck if (c // 8) == suit]
                    random.shuffle(available)
                    for _ in range(needed):
                        if available:
                            c = available.pop()
                            p0_cards.append(c)
                            deck.remove(c)
        if len(p0_cards) < 8:
            needed = 8 - len(p0_cards)
            random.shuffle(deck)
            for _ in range(needed):
                p0_cards.append(deck.pop())
        random.shuffle(deck)
        p1_cards = deck[0:8]; p2_cards = deck[8:16]; p3_cards = deck[16:24]
        hands_ids = [p0_cards, p1_cards, p2_cards, p3_cards]
        for h in hands_ids: h.sort()
        return hands_ids

def generate_biased_hand_ids(trump: int, strategy: GenStrategy, shape_arg=None) -> List[List[int]]:
    builder = HandBuilder(trump)
    if strategy == GenStrategy.FORCE_BELOTE:
        builder.force_card(trump, RANK_K); builder.force_card(trump, RANK_Q)
    elif strategy == GenStrategy.FORCE_CAPOT:
        trump_len = random.randint(4, 8)
        for i in range(trump_len): builder.force_card(trump, TRUMP_ORDER_RANKS[i])
        remaining = 8 - trump_len
        if remaining > 0:
            side_indices = [1, 2, 3]; counts = [0]*4
            for _ in range(remaining): counts[random.choice(side_indices)] += 1
            for i in range(1, 4):
                if counts[i] > 0:
                    suit = (trump + i) % 4
                    for r in range(counts[i]): builder.force_card(suit, SIDE_ORDER_RANKS[r])
    elif strategy == GenStrategy.FORCE_SHAPE and shape_arg:
        builder.force_shape(shape_arg)
    return builder.build()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", type=str, required=True, help="Benchmark run name")
    parser.add_argument("--count", type=int, default=500, help="Number of hands")
    parser.add_argument("--reset", action="store_true", help="Force new hands")
    parser.add_argument("--loops", type=int, default=5, help="Number of runs to average")
    args = parser.parse_args()

    HANDS_FILE = os.path.join(SCRIPT_DIR, "benchmark_hands.pkl")
    RESULTS_FILE = os.path.join(SCRIPT_DIR, "benchmark_results.json")

    # 1. Load/Generate Hands
    hands_data = [] # (trump, h_ids)
    if os.path.exists(HANDS_FILE) and not args.reset:
        with open(HANDS_FILE, "rb") as f:
            hands_data = pickle.load(f)
        if len(hands_data) != args.count:
            print(f"Warning: Existing hands count {len(hands_data)} != requested {args.count}. Using existing.")
    else:
        print(f"Generating {args.count} hands...")
        choices = [GenStrategy.RANDOM, GenStrategy.FORCE_CAPOT, GenStrategy.FORCE_BELOTE, GenStrategy.FORCE_SHAPE]
        weights = [0.4, 0.2, 0.2, 0.2]
        shapes_pool = [[5, 2, 1, 0], [4, 3, 1, 0], [4, 2, 1, 1], [3, 3, 2, 0]]
        for _ in range(args.count):
            s = random.choices(choices, weights=weights, k=1)[0]
            shp = None
            if s == GenStrategy.FORCE_SHAPE: shp = random.choice(shapes_pool)
            trump = random.randint(0, 3)
            h_ids = generate_biased_hand_ids(trump, s, shp)
            hands_data.append((trump, h_ids))
        with open(HANDS_FILE, "wb") as f:
            pickle.dump(hands_data, f)
        print("Hands generated and saved.")

    # 2. Prepare for Solving
    cpp_hands_batch = []
    for trump, h_ids in hands_data:
        game_hands = []
        for p_hand in h_ids:
            game_hands.append([Card(c) for c in p_hand])
        cpp_hands_batch.append(game_hands)

    # 3. Solves (Averaged)
    print(f"Solving {len(cpp_hands_batch)} games (x4 suits) x {args.loops} loops...")
    
    total_duration = 0
    last_stats = {}
    
    for l in range(args.loops):
        cointree_cpp.reset_stats()
        # Ensure correct progress reset if needed, though stats reset should cover it.
        # But 'solve_batch' calls 'increment_hands_solved'.
        # We might want to verify.
        
        start_time = time.time()
        scores = cointree_cpp.solve_batch(cpp_hands_batch, 0)
        iter_duration = time.time() - start_time
        total_duration += iter_duration
        print(f"  Loop {l+1}/{args.loops}: {iter_duration:.4f}s")
        
        if l == args.loops - 1:
            last_stats = cointree_cpp.get_stats()
            
    avg_duration = total_duration / args.loops
    
    # 4. Metrics
    weak_hits = last_stats.get('weak_hand_hits', 0)
    capot_hits = last_stats.get('capot_hits', 0)
    nodes = last_stats.get('nodes_explored', 0)
    
    total_solves = len(cpp_hands_batch) * 4
    minimax_solves = total_solves - (weak_hits + capot_hits)
    
    # CPU Info
    cpu_count = os.cpu_count() or 1
    omp_threads = os.environ.get('OMP_NUM_THREADS', f"{cpu_count} (Default)")

    run_metrics = {
        "timestamp": datetime.now().isoformat(),
        "name": args.name,
        "hands_count": len(cpp_hands_batch),
        "loops": args.loops,
        "cpu_count": cpu_count,
        "omp_threads": omp_threads,
        "avg_duration_sec": avg_duration,
        "throughput_hands_sec": len(cpp_hands_batch) / avg_duration,
        "total_solves_by_suit": total_solves,
        "solves_minimax": minimax_solves,
        "solves_circuit_breaker": weak_hits + capot_hits,
        "cb_weak_hits": weak_hits,
        "cb_capot_hits": capot_hits,
        "nodes_explored_per_run": nodes,
        "nodes_per_second": nodes / avg_duration if avg_duration > 0 else 0
    }
    
    print("\n--- Benchmark Results JSON ---")
    print(json.dumps(run_metrics, indent=2))
    
    def format_human(num):
        for unit in ['', 'K', 'M', 'B', 'T']:
            if abs(num) < 1000.0:
                return f"{num:3.1f}{unit}"
            num /= 1000.0
        return f"{num:.1f}P"

    print("\n--- Summary Indicators (Average of {} Runs) ---".format(args.loops))
    print(f"System:                        {cpu_count} CPUs (OMP_NUM_THREADS={omp_threads})")
    print(f"Total Solves:                  {total_solves}")
    print(f"  - Full Minimax Solves:       {minimax_solves}")
    print(f"  - Circuit Breaker Solves:    {weak_hits + capot_hits} ({(weak_hits + capot_hits)/total_solves*100:.1f}%)")
    print(f"      - Weak Hand Detected:    {weak_hits}")
    print(f"      - Capot Detected:        {capot_hits}")
    print(f"Avg Duration:                  {avg_duration:.4f}s")
    print(f"Throughput:                    {run_metrics['throughput_hands_sec']:.2f} hands/s")
    print(f"Nodes Explored (Avg Rate):     {format_human(nodes)} ({nodes/avg_duration/1e6:.1f} M/s)")
    
    # 5. Save & Compare (JSON)
    history = []
    if os.path.exists(RESULTS_FILE):
        with open(RESULTS_FILE, "r") as f:
            try:
                history = json.load(f)
            except json.JSONDecodeError:
                pass
    
    # Comparison
    print("\n--- Comparison (vs Last Run) ---")
    if history:
        old = history[-1]
        print(f"Previous Run: '{old['name']}' at {old['timestamp']}")
        
        # Duration / Avg Duration
        old_duration = old.get('avg_duration_sec', old.get('duration_sec', 0)) # Handle legacy format
        print(f"  Avg Duration:        {old_duration:.4f}s  -> New: {avg_duration:.4f}s")
        
        # Throughput
        old_thr = old.get('throughput_hands_sec', 0)
        thr_diff = run_metrics['throughput_hands_sec'] - old_thr
        print(f"  Throughput:          {old_thr:.2f} h/s -> New: {run_metrics['throughput_hands_sec']:.2f} h/s ({'+' if thr_diff>=0 else ''}{thr_diff:.2f})")

        # Nodes
        # Handle 'nodes_explored' (legacy) vs 'nodes_explored_per_run'
        old_nodes = old.get('nodes_explored_per_run', old.get('nodes_explored', 0))
        print(f"  Nodes Explored:      {old_nodes} -> New: {nodes}")
        
        # NPS
        old_nps = old.get('nodes_per_second', 0)
        nps_diff = run_metrics['nodes_per_second'] - old_nps
        print(f"  NPS (Agg):           {old_nps/1e6:.1f} M/s -> New: {run_metrics['nodes_per_second']/1e6:.1f} M/s")
        
        # CB Hits
        old_cb = old.get('solves_circuit_breaker', 0)
        new_cb = weak_hits + capot_hits
        print(f"  CB Hits:             {old_cb} -> New: {new_cb}")
        
    else:
        print("No previous runs to compare against.")
        
    history.append(run_metrics)
    with open(RESULTS_FILE, "w") as f:
        json.dump(history, f, indent=2)

    # 6. Parquet Persistence & Score Verification
    try:
        import pandas as pd
        import numpy as np
        
        SCORES_PARQUET = os.path.join(SCRIPT_DIR, "benchmark_scores.parquet")
        
        # Flatten scores from last loop
        # scores is numpy array (N, 4)
        # We want: run_name, timestamp, hand_idx, suit, score
        # Using numpy for speed
        
        N = scores.shape[0]
        rows = []
        # Vectorized dataframe creation
        df_new = pd.DataFrame({
            'timestamp': [run_metrics['timestamp']] * (N * 4),
            'run_name': [args.name] * (N * 4),
            'hand_idx': np.repeat(np.arange(N), 4),
            'suit': np.tile(np.arange(4), N),
            'score': scores.flatten()
        })
        
        print("\n--- Score Verification ---")
        if os.path.exists(SCORES_PARQUET):
            df_hist = pd.read_parquet(SCORES_PARQUET)
            
            # Use the most recent run for comparison
            last_run_name = df_hist['run_name'].iloc[-1]
            last_run_ts = df_hist['timestamp'].iloc[-1]
            
            df_last = df_hist[df_hist['timestamp'] == last_run_ts]
            
            print(f"Comparing against last run: '{last_run_name}' ({last_run_ts})")
            
            # Merge on hand_idx and suit
            merged = pd.merge(df_new, df_last, on=['hand_idx', 'suit'], suffixes=('_new', '_old'))
            
            diffs = merged[merged['score_new'] != merged['score_old']]
            
            if len(diffs) == 0:
                print("  [SUCCESS] All scores match identical to previous run!")
            else:
                print(f"  [WARNING] Score Mismatch Detected in {len(diffs)} / {len(merged)} cases!")
                print(diffs[['hand_idx', 'suit', 'score_old', 'score_new']].head(10))
            
            # Append
            df_final = pd.concat([df_hist, df_new], ignore_index=True)
        else:
            print("No previous scores to verify against. Creating new Parquet store.")
            df_final = df_new
            
        df_final.to_parquet(SCORES_PARQUET)
        print(f"Scores saved to {SCORES_PARQUET}")
        
    except ImportError:
        print("\n[WARNING] Pandas not found. Skipping Parquet persistence and score verification.")
    except Exception as e:
        print(f"\n[ERROR] Parquet processing failed: {e}")

if __name__ == "__main__":
    main()
