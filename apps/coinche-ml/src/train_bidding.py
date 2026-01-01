
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, random_split
import argparse
import os

from bidding_model import BiddingValueNet
from bidding_dataset import BiddingDataset
from trainer import Trainer

def bidding_step_fn(model, batch):
    inputs = batch['features']
    targets = batch['targets']
    
    outputs = model(inputs)
    
    criterion = nn.MSELoss()
    loss = criterion(outputs, targets)
    
    return loss, {}

def bidding_eval_fn(model, batch):
    inputs = batch['features']
    targets = batch['targets']
    
    outputs = model(inputs)
    
    # MAE on actual scores (denormalized)
    # Norm factor was 162.0 in dataset
    output_scores = outputs * 162.0
    target_scores = targets * 162.0
    
    mae = torch.mean(torch.abs(output_scores - target_scores))
    
    return {'MAE': mae.item()}

def train(parquet_file, output_path, epochs=10, batch_size=64, lr=0.001):
    # Check device
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Using device: {device}")

    # Load Dataset
    if not os.path.exists(parquet_file):
        print(f"Error: Dataset not found at {parquet_file}")
        return

    full_dataset = BiddingDataset(parquet_file)
    print(f"Total Dataset size: {len(full_dataset)}")
    
    # Split Train/Val (80/20)
    train_size = int(0.8 * len(full_dataset))
    val_size = len(full_dataset) - train_size
    train_dataset, val_dataset = random_split(full_dataset, [train_size, val_size])
    
    train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True)
    val_loader = DataLoader(val_dataset, batch_size=batch_size, shuffle=False) # No shuffle for val

    # Initialize Model
    model = BiddingValueNet().to(device)
    
    # Optimizer
    optimizer = optim.Adam(model.parameters(), lr=lr)
    
    # Trainer
    trainer = Trainer(model, train_loader, val_loader, optimizer, device, log_dir="runs/bidding", run_name=os.path.basename(output_path))
    
    model_config = {
        'Type': 'MLP (BiddingValueNet)',
        'Hidden Layers': 3,
        'Hidden Dim': 128,
        'Dropout': 0.1
    }
    
    history = trainer.train(
        epochs=epochs,
        loss_fn_dict=bidding_step_fn,
        eval_fn=bidding_eval_fn,
        patience=5, # Early stopping patience
        checkpoint_path=output_path,
        model_config=model_config
    )
    
    print("\n" + "="*30)
    print("       FINAL RESULTS       ")
    print("="*30)
    print(f"Epochs Trained: {history['epochs_trained']}")
    print(f"Best Validation Loss: {history['min_val_loss']:.4f}")
    print(f"Final Train Loss: {history['final_train_loss']:.4f}")
    if 'MAE' in history['final_metrics']:
        print(f"Final MAE: {history['final_metrics']['MAE']:.2f} points")
    print("="*30 + "\n")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=str, default="../../../dist/datasets/bidding_data", help="Path to parquet/json file")
    parser.add_argument("--output", type=str, default="../../models/bidding_model.pth", help="Path to save model")
    parser.add_argument("--epochs", type=int, default=20, help="Number of epochs")
    args = parser.parse_args()
    
    train(args.data, args.output, epochs=args.epochs)
