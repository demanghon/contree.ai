
import torch
from torch.utils.data import Dataset
import pandas as pd
import numpy as np

class BiddingDataset(Dataset):
    def __init__(self, parquet_file):
        self.data = pd.read_parquet(parquet_file)
        
    def __len__(self):
        return len(self.data)
    
    def __getitem__(self, idx):
        row = self.data.iloc[idx]
        
        # Features: Hand (32-bit int) -> One-hot (32 floats)
        hand_int = row['hand_south']
        hand_vec = self._bits_to_vec(hand_int)
        
        # Targets: Scores (List of 4 ints) -> Float tensor normalized
        # Max score is 162 (182 with belote?), let's div by 162 for now.
        scores = np.array(row['scores'], dtype=np.float32)
        scores_normalized = scores / 162.0
        
        return {
            'features': torch.from_numpy(hand_vec),
            'targets': torch.from_numpy(scores_normalized)
        }

    def _bits_to_vec(self, bits):
        vec = np.zeros(32, dtype=np.float32)
        for i in range(32):
            if (bits & (1 << i)) != 0:
                vec[i] = 1.0
        return vec
