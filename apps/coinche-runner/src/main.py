import random
import coinche_engine

# Card constants
SUITS = ["Diamonds", "Spades", "Hearts", "Clubs"]
RANKS = ["7", "8", "9", "10", "J", "Q", "K", "A"]

def get_card_name(card_idx):
    suit = card_idx // 8
    rank = card_idx % 8
    return f"{RANKS[rank]} of {SUITS[suit]}"

def distribute_cards():
    deck = list(range(32))
    random.shuffle(deck)
    hands = [0] * 4
    for i in range(4):
        player_cards = deck[i*8 : (i+1)*8]
        hand_mask = 0
        for card in player_cards:
            hand_mask |= (1 << card)
        hands[i] = hand_mask
    return hands

def print_state(state, trick_num):
    print(f"\n--- Trick {trick_num + 1}/8 ---")
    print(f"Current Player: {state.current_player}")
    print(f"Trump: {SUITS[state.trump] if state.trump < 4 else 'No/All Trump'}")
    
    # Print current trick
    trick_cards = []
    for i in range(4):
        card = state.current_trick[i]
        if card != 255:
            trick_cards.append(f"P{i}: {get_card_name(card)}")
    print(f"Trick: {', '.join(trick_cards)}")

import argparse
import subprocess
import os

def main():
    parser = argparse.ArgumentParser(description="Coinche Runner")
    parser.add_argument("--generate-graph", action="store_true", help="Generate PV graph")
    args = parser.parse_args()

    print("Initializing Coinche Game...")
    
    # 1. Setup
    hands = distribute_cards()
    trump = random.randint(0, 3) # Random suit trump for now
    
    # 2. Initialize GameState
    state = coinche_solver.GameState(trump)
    for i in range(4):
        state.set_hand(i, hands[i])
        
    print(f"Trump is {SUITS[trump]}")
    
    # Display Initial Hands
    print("\n=== Initial Hands ===")
    for i in range(4):
        hand_mask = hands[i]
        cards = []
        for c in range(32):
            if (hand_mask & (1 << c)) != 0:
                cards.append(get_card_name(c))
        print(f"Player {i}: {', '.join(cards)}")
    print("=====================\n")
    
    # 3. Game Loop
    for trick_num in range(8):
        for _ in range(4): # 4 cards per trick
            print_state(state, trick_num)
            
            # Solve
            # Only generate graph for the very first move if requested (otherwise it's too much)
            gen_graph = args.generate_graph and trick_num == 0 and state.trick_size == 0
            
            score, best_move = coinche_solver.solve(state, gen_graph)
            
            if gen_graph:
                print("Graph generated: tree.dot")
                try:
                    subprocess.run(["dot", "-Tpng", "tree.dot", "-o", "tree.png"], check=True)
                    print("Graph rendered: tree.png")
                except FileNotFoundError:
                    print("Error: 'dot' command not found. Install graphviz.")
                except Exception as e:
                    print(f"Error rendering graph: {e}")
            
            print(f"Solver suggests: {get_card_name(best_move)} (Expected Score: {score})")
            
            # Play
            state.play_card(best_move)
            
    # 4. Result
    print("\n=== Game Over ===")
    print(f"Final Scores: NS={state.points[0]}, EW={state.points[1]}")

if __name__ == "__main__":
    main()
