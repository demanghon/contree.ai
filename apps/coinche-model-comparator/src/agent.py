
import torch
import numpy as np
import sys
import os
import random
from abc import ABC, abstractmethod

# Allow importing from coinche-ml src
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../coinche-ml/src")))

try:
    from bidding_model import BiddingValueNet
    from gameplay_model import GameplayResNet
except ImportError:
    pass # Might not be needed for Heuristic/Random

class BaseAgent(ABC):
    def __init__(self, name):
        self.name = name

    @abstractmethod
    def get_bid(self, hand_int, current_contract=None, partner_contract=None):
        """
        Returns (suit_idx, est_score)
        """
        pass

    @abstractmethod
    def get_card(self, hand_int, history_int, board_cards, is_trump, legal_mask):
        """
        Returns best card (0-31)
        """
        pass

class AI_Agent(BaseAgent):
    def __init__(self, bidding_model_path, playing_model_path, device, name="AI"):
        super().__init__(name)
        self.device = device
        
        # Load Bidding Model
        self.bidding_model = BiddingValueNet().to(device)
        self.bidding_model.load_state_dict(torch.load(bidding_model_path, map_location=device))
        self.bidding_model.eval()
        
        # Load Playing Model
        self.playing_model = GameplayResNet(input_dim=102).to(device)
        try:
            self.playing_model.load_state_dict(torch.load(playing_model_path, map_location=device))
        except Exception:
            print(f"Warning: Could not load {playing_model_path} into default GameplayResNet. Architecture mismatch?")
            # Try loading with strict=False or different arch? For now raise.
            raise
        self.playing_model.eval()

    def get_bid(self, hand_int, current_contract=None, partner_contract=None):
        # Feature Engineering: 32-bit hand to One Hot
        hand_vec = np.zeros(32, dtype=np.float32)
        for i in range(32):
            if (hand_int & (1 << i)) != 0:
                hand_vec[i] = 1.0
        
        input_tensor = torch.from_numpy(hand_vec).unsqueeze(0).to(self.device)
        
        with torch.no_grad():
            output_scores = self.bidding_model(input_tensor)
            raw_scores = output_scores * 162.0
            
        best_suit_idx = torch.argmax(raw_scores).item()
        best_score = raw_scores[0, best_suit_idx].item()
        
        return best_suit_idx, best_score

    def get_card(self, hand_int, history_int, board_cards, trump_val, legal_mask):
        # Feature Engineering
        hand_vec = np.zeros(32, dtype=np.float32)
        for i in range(32):
            if (hand_int & (1 << i)) != 0:
                hand_vec[i] = 1.0
        
        history_vec = np.zeros(32, dtype=np.float32)
        for i in range(32):
            if (history_int & (1 << i)) != 0:
                history_vec[i] = 1.0
                
        board_vec = np.zeros(32, dtype=np.float32)
        for card in board_cards:
            if card < 32:
                board_vec[card] = 1.0
                
        trump_vec = np.zeros(6, dtype=np.float32)
        if trump_val < 6:
            trump_vec[trump_val] = 1.0
            
        features = np.concatenate([hand_vec, history_vec, board_vec, trump_vec])
        input_tensor = torch.from_numpy(features).unsqueeze(0).to(self.device)
        
        with torch.no_grad():
            _, policy_logits = self.playing_model(input_tensor)
            
        masked_logits = policy_logits.squeeze(0).clone()
        for i in range(32):
            if (legal_mask & (1 << i)) == 0:
                masked_logits[i] = -float('inf')
                
        best_card = torch.argmax(masked_logits).item()
        return best_card

class RandomAgent(BaseAgent):
    def __init__(self, name="Random"):
        super().__init__(name)

    def get_bid(self, hand_int, current_contract=None, partner_contract=None):
        # Random suit, random score between 80-160? 
        # Or just PASS mostly?
        # Let's say it evaluates random potential.
        return random.randint(0, 3), random.uniform(70, 100)

    def get_card(self, hand_int, history_int, board_cards, trump_val, legal_mask):
        legal_moves = []
        for i in range(32):
            if (legal_mask & (1 << i)) != 0:
                legal_moves.append(i)
        return random.choice(legal_moves)

class HeuristicAgent(BaseAgent):
    def __init__(self, name="Heuristic"):
        super().__init__(name)

    def get_bid(self, hand_int, current_contract=None, partner_contract=None):
        # Count points (Belote standard)
        # Jacks=20, 9s=14, Aces=11, 10s=10, K=4, Q=3
        # Estimate points in hand + some helper
        # Logic: Pick best suit based on point density.
        
        best_suit = 0
        max_points = 0
        
        # Iterate suits 0-3
        for suit in range(4):
            points = 0
            # Cards in suit: offset 8*suit.
            # Ranks: 7,8,9,10,J,Q,K,A
            # Values (Trump): 0,0,14,10,20,3,4,11
            # Values (NoTrump): 0,0,0,10,2,3,4,11
            # Check cards in hand_int
            
            # Simple point counter for validation
            # J(4)=20, 9(2)=14, A(7)=11, 10(3)=10, K(6)=4, Q(5)=3
            has_valet = (hand_int & (1 << (suit*8 + 4))) != 0
            has_neuf = (hand_int & (1 << (suit*8 + 2))) != 0
            has_as = (hand_int & (1 << (suit*8 + 7))) != 0
            
            if has_valet: points += 20
            if has_neuf: points += 14
            if has_as: points += 11
            
            # Add length bonus
            count = 0
            for r in range(8):
                if (hand_int & (1 << (suit*8 + r))) != 0:
                    count += 1
            points += count * 10
            
            if points > max_points:
                max_points = points
                best_suit = suit
        
        # Expected score ~= points + partner help (20?)
        return best_suit, max_points + 20

    def get_card(self, hand_int, history_int, board_cards, trump_val, legal_mask):
        # Deterministic Rules
        # 1. If partner controls trick and I don't need to cut -> Play small score (dump trash) or points (if safe)?
        # 2. If valid to cut, do I?
        # Simple Heuristic: Play Highest Legal Card (Power)
        
        legal_cards = []
        for i in range(32):
            if (legal_mask & (1 << i)) != 0:
                legal_cards.append(i)
        
        # Rank is (card % 8). 
        # Standard Order: 7(0) < 8(1) < 9(2) < 10(3) < J(4) < Q(5) < K(6) < A(7)
        # Trump Order: 7 < 8 < Q < K < 10 < A < 9 < J
        
        best_card = legal_cards[0]
        max_power = -1
        
        for c in legal_cards:
            suit = c // 8
            rank = c % 8
            is_trump_card = (suit == trump_val) or (trump_val == 5) # AllTrump=5
            
            # Simplified Power
            if is_trump_card:
                # J=7, 9=6, A=5, 10=4, K=3, Q=2, 8=1, 7=0
                power_map = {4:7, 2:6, 7:5, 3:4, 6:3, 5:2, 1:1, 0:0}
                power = 100 + power_map.get(rank, 0)
            else:
                # A=7, 10=6, K=5, Q=4, J=3, 9=2, 8=1, 7=0
                power_map = {7:7, 3:6, 6:5, 5:4, 4:3, 2:2, 1:1, 0:0}
                power = power_map.get(rank, 0)
            
            if power > max_power:
                max_power = power
                best_card = c
                
        return best_card

def load_agent(bidding_path, playing_path, device, name):
    # If paths are 'heuristic' or 'random'
    if bidding_path.lower() == 'heuristic':
        return HeuristicAgent(name)
    elif bidding_path.lower() == 'random':
        return RandomAgent(name)
    else:
        return AI_Agent(bidding_path, playing_path, device, name)
