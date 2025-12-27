
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader
from tqdm import tqdm
import argparse
import os

from bidding_model import BiddingValueNet
from bidding_dataset import BiddingDataset

def train(parquet_file, output_path, epochs=10, batch_size=64, lr=0.001):
    # Check device
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Using device: {device}")

    # Load Dataset
    if not os.path.exists(parquet_file):
        print(f"Error: Dataset not found at {parquet_file}")
        return

    dataset = BiddingDataset(parquet_file)
    dataloader = DataLoader(dataset, batch_size=batch_size, shuffle=True)
    
    print(f"Dataset size: {len(dataset)}")

    # Initialize Model
    model = BiddingValueNet().to(device)
    
    # Loss Function and Optimizer
    criterion = nn.MSELoss()
    optimizer = optim.Adam(model.parameters(), lr=lr)
    
    # Training Loop
    min_loss = float('inf')
    
    for epoch in range(epochs):
        model.train()
        total_loss = 0
        
        progress_bar = tqdm(dataloader, desc=f"Epoch {epoch+1}/{epochs}")
        
        for batch in progress_bar:
            inputs = batch['features'].to(device)
            targets = batch['targets'].to(device)
            
            optimizer.zero_grad()
            outputs = model(inputs)
            loss = criterion(outputs, targets)
            loss.backward()
            optimizer.step()
            
            total_loss += loss.item()
            progress_bar.set_postfix({'loss': f"{loss.item():.4f}"})
            
        avg_loss = total_loss / len(dataloader)
        print(f"Epoch {epoch+1} - Avg Loss: {avg_loss:.4f}")
        
        if avg_loss < min_loss:
            min_loss = avg_loss
            torch.save(model.state_dict(), output_path)
            # print(f"Model saved to {output_path}")

    print(f"Training Complete. Best Loss: {min_loss:.4f}")
    print(f"Model saved to {output_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=str, default="../../dataset/simple_bidding_dataset.parquet", help="Path to parquet file")
    parser.add_argument("--output", type=str, default="../../models/bidding_model.pth", help="Path to save model")
    parser.add_argument("--epochs", type=int, default=10, help="Number of epochs")
    args = parser.parse_args()
    
    train(args.data, args.output, epochs=args.epochs)
