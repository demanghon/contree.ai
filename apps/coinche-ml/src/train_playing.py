
print("Starting Gameplay Training...")
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader
from tqdm import tqdm
import argparse
import os

from gameplay_model import GameplayResNet
from gameplay_dataset import GameplayDataset

def train(parquet_file, output_path, epochs=10, batch_size=64, lr=0.001):
    # Check device
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Using device: {device}")

    # Load Dataset
    if not os.path.exists(parquet_file):
        print(f"Error: Dataset not found at {parquet_file}")
        return

    dataset = GameplayDataset(parquet_file)
    dataloader = DataLoader(dataset, batch_size=batch_size, shuffle=True)
    
    print(f"Dataset size: {len(dataset)}")

    # Initialize Model
    model = GameplayResNet(input_dim=102).to(device)
    
    # Loss Functions
    mse_loss = nn.MSELoss()
    ce_loss = nn.CrossEntropyLoss()
    
    # Optimizer
    optimizer = optim.Adam(model.parameters(), lr=lr)
    
    # Training Loop
    min_loss = float('inf')
    
    for epoch in range(epochs):
        model.train()
        total_loss = 0
        total_val_loss = 0
        total_pol_loss = 0
        
        progress_bar = tqdm(dataloader, desc=f"Epoch {epoch+1}/{epochs}")
        
        for batch in progress_bar:
            inputs = batch['features'].to(device)
            target_card = batch['best_card'].to(device)
            target_score = batch['best_score'].to(device).unsqueeze(1)
            
            optimizer.zero_grad()
            
            pred_score, pred_policy = model(inputs)
            
            loss_val = mse_loss(pred_score, target_score)
            loss_pol = ce_loss(pred_policy, target_card)
            
            loss = loss_val + loss_pol
            
            loss.backward()
            optimizer.step()
            
            total_loss += loss.item()
            total_val_loss += loss_val.item()
            total_pol_loss += loss_pol.item()
            
            progress_bar.set_postfix({
                'loss': f"{loss.item():.4f}",
                'val': f"{loss_val.item():.4f}",
                'pol': f"{loss_pol.item():.4f}"
            })
            
        avg_loss = total_loss / len(dataloader)
        print(f"Epoch {epoch+1} - Avg Loss: {avg_loss:.4f} (Val: {total_val_loss/len(dataloader):.4f}, Pol: {total_pol_loss/len(dataloader):.4f})")
        
        if avg_loss < min_loss:
            min_loss = avg_loss
            torch.save(model.state_dict(), output_path)

    print(f"Training Complete. Best Loss: {min_loss:.4f}")
    print(f"Model saved to {output_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=str, default="../../dataset/simple_gameplay_dataset.parquet", help="Path to parquet file")
    parser.add_argument("--output", type=str, default="../../models/playing_model.pth", help="Path to save model")
    parser.add_argument("--epochs", type=int, default=10, help="Number of epochs")
    args = parser.parse_args()
    
    train(args.data, args.output, epochs=args.epochs)
