
import torch
from torch.utils.data import Dataset
import pandas as pd
import numpy as np

class GameplayDataset(Dataset):
    def __init__(self, parquet_file):
        self.data = pd.read_parquet(parquet_file)
        
    def __len__(self):
        return len(self.data)
    
    def __getitem__(self, idx):
        row = self.data.iloc[idx]
        
        # --- Feature Engineering ---
        # 1. Hand (32 bits) -> One-hot (32 floats)
        hand = row['hand']
        hand_vec = self._bits_to_vec(hand)
        
        # 2. History (32 bits) -> One-hot (32 floats)
        history = row['history']
        history_vec = self._bits_to_vec(history)
        
        # 3. Board (List of u8) -> One-hot (32 floats)
        board = row['board']
        board_vec = np.zeros(32, dtype=np.float32)
        for card in board:
            if card < 32:
                board_vec[card] = 1.0
                
        # 4. Trump (scalar) -> One-hot (4 floats, actually 0-5)
        # 0=Diamonds, 1=Spades, 2=Hearts, 3=Clubs, 4=NoTrump, 5=AllTrump
        trump = row['trump']
        trump_vec = np.zeros(6, dtype=np.float32) # Fixed: Size 6 for all trump types
        if trump < 6:
            trump_vec[trump] = 1.0
            
        # Concatenate all features
        # 32 + 32 + 32 + 6 = 102
        features = np.concatenate([hand_vec, history_vec, board_vec, trump_vec])
        
        # Targets
        best_card = row['best_card']
        best_score = row['best_score']
        
        return {
            'features': torch.from_numpy(features),
            'best_card': torch.tensor(best_card, dtype=torch.long),
            'best_score': torch.tensor(best_score, dtype=torch.float32) / 162.0 # Normalize score
        }

    def _bits_to_vec(self, bits):
        vec = np.zeros(32, dtype=np.float32)
        for i in range(32):
            if (bits & (1 << i)) != 0:
                vec[i] = 1.0
        return vec
