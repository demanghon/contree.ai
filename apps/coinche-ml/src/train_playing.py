
print("Starting Gameplay Training...")
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, random_split
import argparse
import os

from gameplay_model import GameplayResNet
from gameplay_dataset import GameplayDataset
from trainer import Trainer

def playing_step_fn(model, batch):
    inputs = batch['features']
    target_card = batch['best_card']
    target_score = batch['best_score'].unsqueeze(1)
    
    pred_score, pred_policy = model(inputs)
    
    mse_loss = nn.MSELoss()
    ce_loss = nn.CrossEntropyLoss()
    
    loss_val = mse_loss(pred_score, target_score)
    loss_pol = ce_loss(pred_policy, target_card)
    
    loss = loss_val + loss_pol
    
    return loss, {'val_loss': loss_val.item(), 'pol_loss': loss_pol.item()}

def playing_eval_fn(model, batch):
    inputs = batch['features']
    target_score = batch['best_score'].unsqueeze(1)
    target_card = batch['best_card']
    
    pred_score, pred_policy = model(inputs)
    
    # MAE on score
    output_scores = pred_score * 162.0
    target_scores_denorm = target_score * 162.0
    mae = torch.mean(torch.abs(output_scores - target_scores_denorm))
    
    # Accuracy on policy
    pred_cards = torch.argmax(pred_policy, dim=1)
    correct = (pred_cards == target_card).float().sum()
    accuracy = correct / len(target_card)
    
    return {'MAE': mae.item(), 'Accuracy': accuracy.item()}

def train(parquet_file, output_path, epochs=10, batch_size=64, lr=0.001):
    # Check device
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Using device: {device}")

    # Load Dataset
    if not os.path.exists(parquet_file):
        print(f"Error: Dataset not found at {parquet_file}")
        return

    full_dataset = GameplayDataset(parquet_file)
    print(f"Total Dataset size: {len(full_dataset)}")
    
    # Split Train/Val
    train_size = int(0.8 * len(full_dataset))
    val_size = len(full_dataset) - train_size
    train_dataset, val_dataset = random_split(full_dataset, [train_size, val_size])
    
    train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True)
    val_loader = DataLoader(val_dataset, batch_size=batch_size, shuffle=False)

    # Initialize Model
    model = GameplayResNet(input_dim=102).to(device)
    
    # Optimizer
    optimizer = optim.Adam(model.parameters(), lr=lr)
    
    # Trainer
    trainer = Trainer(model, train_loader, val_loader, optimizer, device, log_dir="runs/playing", run_name=os.path.basename(output_path))
    
    model_config = {
        'Type': 'ResNet (GameplayResNet)',
        'Residual Blocks': 4,
        'Hidden Dim': 256,
        'Dropout': 0.1
    }
    
    history = trainer.train(
        epochs=epochs,
        loss_fn_dict=playing_step_fn,
        eval_fn=playing_eval_fn,
        patience=5,
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
    if 'Accuracy' in history['final_metrics']:
        print(f"Final Accuracy: {history['final_metrics']['Accuracy']:.2%}")
    print("="*30 + "\n")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=str, default="../../../dist/datasets/gameplay_data.parquet", help="Path to parquet/json file")
    parser.add_argument("--output", type=str, default="../../models/playing_model.pth", help="Path to save model")
    parser.add_argument("--epochs", type=int, default=20, help="Number of epochs")
    args = parser.parse_args()
    
    train(args.data, args.output, epochs=args.epochs)
