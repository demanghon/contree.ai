import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader
from tqdm import tqdm
import argparse

from model import CoincheResNet
from dataset import CoincheDataset

def train(parquet_file, epochs=10, batch_size=32, lr=0.001):
    # Check device
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Using device: {device}")

    # Load Dataset
    dataset = CoincheDataset(parquet_file)
    dataloader = DataLoader(dataset, batch_size=batch_size, shuffle=True)
    
    print(f"Dataset size: {len(dataset)}")

    # Initialize Model
    # Input dim = 32 (Hand) + 32 (History) + 32 (Board) + 4 (Trump) = 100
    model = CoincheResNet(input_dim=100).to(device)
    
    # Loss Functions
    mse_loss = nn.MSELoss()
    ce_loss = nn.CrossEntropyLoss()
    
    # Optimizer
    optimizer = optim.Adam(model.parameters(), lr=lr)
    
    # Training Loop
    for epoch in range(epochs):
        model.train()
        total_loss = 0
        total_value_loss = 0
        total_policy_loss = 0
        
        progress_bar = tqdm(dataloader, desc=f"Epoch {epoch+1}/{epochs}")
        
        for batch in progress_bar:
            features = batch['features'].to(device)
            target_card = batch['best_card'].to(device)
            target_score = batch['score'].to(device).unsqueeze(1) # (batch, 1)
            
            # Forward
            pred_score, pred_policy = model(features)
            
            # Loss
            loss_value = mse_loss(pred_score, target_score)
            loss_policy = ce_loss(pred_policy, target_card)
            
            loss = loss_value + loss_policy
            
            # Backward
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
            
            # Metrics
            total_loss += loss.item()
            total_value_loss += loss_value.item()
            total_policy_loss += loss_policy.item()
            
            progress_bar.set_postfix({
                'loss': f"{loss.item():.4f}", 
                'val': f"{loss_value.item():.4f}", 
                'pol': f"{loss_policy.item():.4f}"
            })
            
        avg_loss = total_loss / len(dataloader)
        print(f"Epoch {epoch+1} - Avg Loss: {avg_loss:.4f}")

    # Save Model
    torch.save(model.state_dict(), "coinche_model.pth")
    print("Model saved to coinche_model.pth")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=str, default="../../dist/datasets/gameplay_data.parquet", help="Path to parquet file")
    parser.add_argument("--epochs", type=int, default=5, help="Number of epochs")
    args = parser.parse_args()
    
    train(args.data, epochs=args.epochs)
