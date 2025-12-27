
import torch
import torch.nn as nn
import torch.nn.functional as F

class BiddingValueNet(nn.Module):
    def __init__(self, input_dim=32, output_dim=4, hidden_dim=128):
        super().__init__()
        
        self.fc1 = nn.Linear(input_dim, hidden_dim)
        self.bn1 = nn.BatchNorm1d(hidden_dim)
        
        self.fc2 = nn.Linear(hidden_dim, hidden_dim)
        self.bn2 = nn.BatchNorm1d(hidden_dim)
        
        self.fc3 = nn.Linear(hidden_dim, hidden_dim)
        self.bn3 = nn.BatchNorm1d(hidden_dim)
        
        self.output = nn.Linear(hidden_dim, output_dim)
        
        self.dropout = nn.Dropout(0.1)

    def forward(self, x):
        x = F.relu(self.bn1(self.fc1(x)))
        x = self.dropout(x)
        x = F.relu(self.bn2(self.fc2(x)))
        x = self.dropout(x)
        x = F.relu(self.bn3(self.fc3(x)))
        
        return self.output(x)
