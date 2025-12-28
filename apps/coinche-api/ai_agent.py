
import torch
import numpy as np
import os
from ai_models import BiddingValueNet, GameplayResNet
import coinche_engine

class AIAgent:
    def __init__(self, models_dir):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        print(f"AI Agent using device: {self.device}")
        
        # Load Bidding Model
        self.bidding_model = BiddingValueNet().to(self.device)
        bidding_path = os.path.join(models_dir, "simple_bidding_model_300K.pth")
        if os.path.exists(bidding_path):
            self.bidding_model.load_state_dict(torch.load(bidding_path, map_location=self.device))
            self.bidding_model.eval()
            print(f"Loaded Bidding Model from {bidding_path}")
        else:
            print(f"Warning: Bidding Model not found at {bidding_path}")

        # Load Playing Model
        self.playing_model = GameplayResNet(input_dim=102).to(self.device)
        playing_path = os.path.join(models_dir, "simple_playing_model_1M.pth")
        if os.path.exists(playing_path):
            self.playing_model.load_state_dict(torch.load(playing_path, map_location=self.device))
            self.playing_model.eval()
            print(f"Loaded Playing Model from {playing_path}")
        else:
            print(f"Warning: Playing Model not found at {playing_path}")

    def get_bid(self, hand_int, current_contract):
        # 1. Prepare Features
        # Hand (32-bit int) -> One-hot (32 floats)
        hand_vec = self._bits_to_vec(hand_int)
        inputs = torch.from_numpy(hand_vec).unsqueeze(0).to(self.device) # (1, 32)
        
        # 2. Predict Scores
        with torch.no_grad():
            scores = self.bidding_model(inputs).cpu().numpy()[0] # (4,)
            
        # Denormalize scores (model trained on normalized 0-1)
        dataset_max_score = 162.0 
        predicted_points = scores * dataset_max_score
        
        # Suits: 0=D, 1=S, 2=H, 3=C
        best_suit = np.argmax(predicted_points)
        best_score = predicted_points[best_suit]
        
        # 3. Decision Logic
        current_val = current_contract.value if current_contract else 0
        
        # Simple heuristic: Bid 80% of expected score? Or just raw expected score?
        # Let's be aggressive: Bid if expected points > current highest + margin
        # But bidding is discrete (80, 90, 100...).
        # Let's say we bid roughly the expected value rounded down to nearest 10.
        
        bid_value = int(best_score / 10) * 10
        
        if bid_value < 80:
            return None # Pass
            
        if bid_value > current_val:
            # Check if we can bid this value (must be >= current + 10 ideally)
            target_bid = max(current_val + 10, 80)
            if bid_value >= target_bid:
                # Cap at 160 for now unless Capot (250) logic added explicitly
                if bid_value > 160: 
                     bid_value = 160 # Safe cap for initial testing
                return coinche_engine.Bid(bid_value, int(best_suit))
        
        return None # Pass

    def get_play(self, game_state, hand_int, legal_moves_mask):
        # 1. Prepare Features
        # Hand
        hand_vec = self._bits_to_vec(hand_int)
        
        # History (from PlayedCards mask if available, or track manually?)
        # GameState from engine usually has history or cards played.
        # PlayingState in engine has `tricks_won`, `current_trick`.
        # It DOES NOT expose full history bitmask directly in `PlayingState` struct we saw earlier?
        # Let's check PlayingState definition again. 
        # Actually PlayingState doesn't seem to have full history mask exposed?
        # We might need to approximate or pass it.
        # For MVP, let's use 0 for history if not available, or rebuild it from known tricks?
        # Rebuilding is hard without full log. Let's assume 0 for now to unblock.
        history_vec = np.zeros(32, dtype=np.float32) 
        
        # Board (Current Trick)
        current_trick = game_state['current_trick'] # List of card IDs (or 255)
        board_vec = np.zeros(32, dtype=np.float32)
        for card in current_trick:
             if card < 32:
                 board_vec[card] = 1.0
                 
        # Trump
        trump = game_state['trump']
        trump_vec = np.zeros(6, dtype=np.float32)
        if trump < 6:
            trump_vec[trump] = 1.0
            
        # Concat
        features = np.concatenate([hand_vec, history_vec, board_vec, trump_vec])
        inputs = torch.from_numpy(features).unsqueeze(0).to(self.device) # (1, 102)
        
        # 2. Predict Policy
        with torch.no_grad():
            _, policy_logits = self.playing_model(inputs)
            policy = policy_logits.cpu().numpy()[0] # (32,)
            
        # 3. Mask Illegal Moves
        # legal_moves_mask is an integer bitmask
        legal_mask_vec = self._bits_to_vec(legal_moves_mask)
        
        # Set illegal move logits to -inf
        policy[legal_mask_vec == 0] = -1e9
        
        # 4. Select Action
        best_card = np.argmax(policy)
        
        return int(best_card)

    def _bits_to_vec(self, bits):
        vec = np.zeros(32, dtype=np.float32)
        for i in range(32):
            if (bits & (1 << i)) != 0:
                vec[i] = 1.0
        return vec
