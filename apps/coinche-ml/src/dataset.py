import torch
from torch.utils.data import Dataset
import pandas as pd
import numpy as np

class CoincheDataset(Dataset):
    def __init__(self, parquet_file):
        self.data = pd.read_parquet(parquet_file)
        
    def __len__(self):
        return len(self.data)
    
    def __getitem__(self, idx):
        row = self.data.iloc[idx]
        
        # Extract features
        hand = row['hand']
        history = row['history']
        board = row['board'] # List of cards
        trump = row['trump']
        
        # --- Feature Engineering ---
        # 1. Hand (32 bits) -> One-hot (32 floats)
        hand_vec = self._bits_to_vec(hand)
        
        # 2. History (32 bits) -> One-hot (32 floats)
        history_vec = self._bits_to_vec(history)
        
        # 3. Board (List of u8) -> One-hot (32 floats)
        # Note: Ideally we want to preserve order or who played what.
        # For now, simple presence mask.
        board_vec = np.zeros(32, dtype=np.float32)
        for card in board:
            if card < 32:
                board_vec[card] = 1.0
                
        # 4. Trump (scalar) -> One-hot (4 floats)
        trump_vec = np.zeros(4, dtype=np.float32)
        if trump < 4:
            trump_vec[trump] = 1.0
            
        # Concatenate all features
        features = np.concatenate([hand_vec, history_vec, board_vec, trump_vec])
        
        # Value (Score) - Normalize to [0, 1] range (approx 0-162)
        score = row['best_score']
        
        best_card = row['best_card']
        
        return {
            'features': torch.from_numpy(features),
            'best_card': torch.tensor(best_card, dtype=torch.long),
            'score': torch.tensor(score, dtype=torch.float32) / 162.0 
        }

    def _bits_to_vec(self, bits):
        vec = np.zeros(32, dtype=np.float32)
        for i in range(32):
            if (bits & (1 << i)) != 0:
                vec[i] = 1.0
        return vec
