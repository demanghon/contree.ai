
import sys
import os
import time
import random
import coinche_engine

# Enums (Rust version uses u8 constants usually, unless exposed as Enums)
# From playing.rs:
DIAMONDS = 0
SPADES = 1
HEARTS = 2
CLUBS = 3

RANK_7 = 0
RANK_8 = 1
RANK_9 = 2
RANK_10 = 3
RANK_J = 4
RANK_Q = 5
RANK_K = 6
RANK_A = 7

def card(suit, rank):
    # Rust uses bitmasks for hands: u32
    # 1 << (suit * 8 + rank)
    return 1 << (suit * 8 + rank)

def create_deck_cards():
    deck = []
    for s in [HEARTS, DIAMONDS, CLUBS, SPADES]:
        for r in [RANK_SEVEN, RANK_EIGHT, RANK_NINE, RANK_TEN, RANK_JACK, RANK_QUEEN, RANK_KING, RANK_ACE]:
            deck.append((s, r))
    return deck

# Re-map ranks for convenience if needed
RANK_SEVEN = 0
RANK_EIGHT = 1
RANK_NINE = 2
RANK_TEN = 3
RANK_JACK = 4
RANK_QUEEN = 5
RANK_KING = 6
RANK_ACE = 7

def create_god_hand_state():
    state = coinche_engine.PlayingState(HEARTS)
    
    # P0: Top Trumps (Hearts)
    h0 = 0
    for r in [RANK_JACK, RANK_NINE, RANK_ACE, RANK_TEN, RANK_KING, RANK_QUEEN, RANK_EIGHT, RANK_SEVEN]:
        h0 |= card(HEARTS, r)
    state.set_hand(0, h0)
    
    # Others
    deck = []
    for s in [DIAMONDS, CLUBS, SPADES]:
        for r in range(8):
            deck.append((s, r))
    
    # Deterministic split
    h1 = 0
    for i in range(8):
        h1 |= card(deck[i][0], deck[i][1])
    state.set_hand(1, h1)
    
    h2 = 0
    for i in range(8, 16):
        h2 |= card(deck[i][0], deck[i][1])
    state.set_hand(2, h2)
        
    h3 = 0
    for i in range(16, 24):
        h3 |= card(deck[i][0], deck[i][1])
    state.set_hand(3, h3)
    
    return state

def deal_random_hands(state):
    deck = []
    for s in range(4):
        for r in range(8):
            deck.append((s, r))
    
    random.shuffle(deck)
    
    h0 = 0
    for i in range(0, 8):
        h0 |= card(deck[i][0], deck[i][1])
    state.set_hand(0, h0)
    
    h1 = 0
    for i in range(8, 16):
        h1 |= card(deck[i][0], deck[i][1])
    state.set_hand(1, h1)
    
    h2 = 0
    for i in range(16, 24):
        h2 |= card(deck[i][0], deck[i][1])
    state.set_hand(2, h2)
    
    h3 = 0
    for i in range(24, 32):
        h3 |= card(deck[i][0], deck[i][1])
    state.set_hand(3, h3)

def run_benchmark(num_random_hands: int = 100):
    print(f"Running Rust Benchmark with {num_random_hands} random hands...")
    
    # God Hand
    print("\n--- God Hand Test ---")
    god_state = create_god_hand_state()
    t0 = time.time()
    # solve_game returns (score, best_move)
    score, best_move = coinche_engine.solve_game(god_state, max_depth=32)
    dt = time.time() - t0
    print(f"God Hand Score: {score}")
    print(f"Time: {dt*1000:.2f} ms")
    
    # Random Hands
    print(f"\n--- Random Hands Test ({num_random_hands} iterations) ---")
    times = []
    
    for i in range(num_random_hands):
        trump = random.randint(0, 3)
        state = coinche_engine.PlayingState(trump)
        deal_random_hands(state)
        # Random starter? state.current_player is read-only (starts at 0)
        # state.current_player = random.randint(0, 3) 
        # state.trick_starter = state.current_player
        
        t_start = time.perf_counter()
        coinche_engine.solve_game(state, max_depth=32)
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
