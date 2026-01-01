
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.tensorboard import SummaryWriter
from tqdm import tqdm
import numpy as np
import os
from datetime import datetime

class Trainer:
    def __init__(self, model, train_loader, val_loader, optimizer, device, log_dir="runs", run_name=None):
        self.model = model
        self.train_loader = train_loader
        self.val_loader = val_loader
        self.optimizer = optimizer
        self.device = device
        
        # Logging
        if run_name:
            # Clean up the name to be safe for directory
            safe_name = os.path.basename(run_name).replace('.pth', '').replace('.pt', '')
            log_dir = os.path.join(log_dir, safe_name)
        else:
            current_time = datetime.now().strftime('%b%d_%H-%M-%S')
            log_dir = os.path.join(log_dir, current_time)
            
        self.writer = SummaryWriter(log_dir=log_dir)
        print(f"TensorBoard logging to {log_dir}")
        
    def train(self, epochs, loss_fn_dict, 
              eval_fn=None, # Function to compute custom metrics (e.g. MAE)
              patience=5, 
              checkpoint_path="best_model.pth",
              model_config=None):
        
        min_val_loss = float('inf')
        no_improve_epochs = 0
        best_epoch = 0
        
        for epoch in range(epochs):
            # --- Training ---
            self.model.train()
            train_loss = 0.0
            
            progress_bar = tqdm(self.train_loader, desc=f"Epoch {epoch+1}/{epochs} [Train]")
            
            for batch in progress_bar:
                # Move batch to device
                for k, v in batch.items():
                    if isinstance(v, torch.Tensor):
                        batch[k] = v.to(self.device)
                
                self.optimizer.zero_grad()
                
                # Forward
                loss, metrics = self._train_step(batch, loss_fn_dict)
                
                loss.backward()
                
                # Gradient Norm
                total_norm = 0
                for p in self.model.parameters():
                    if p.grad is not None:
                        param_norm = p.grad.data.norm(2)
                        total_norm += param_norm.item() ** 2
                total_norm = total_norm ** 0.5
                
                self.optimizer.step()
                
                train_loss += loss.item()
                current_step = epoch * len(self.train_loader) + progress_bar.n
                if current_step % 100 == 0:
                    self.writer.add_scalar('Train/Batch_Loss', loss.item(), current_step)
                    self.writer.add_scalar('Train/Grad_Norm', total_norm, current_step)
                
                # Update progress bar
                desc = {'loss': f"{loss.item():.4f}"}
                desc.update({k: f"{v:.4f}" for k,v in metrics.items()})
                desc['grad_norm'] = f"{total_norm:.2f}"
                progress_bar.set_postfix(desc)
                
            avg_train_loss = train_loss / len(self.train_loader)
            
            # --- Validation ---
            val_loss, val_metrics = self.evaluate(loss_fn_dict, eval_fn)
            
            # --- Logging ---
            self.writer.add_scalars('Loss', {
                'Train': avg_train_loss,
                'Validation': val_loss
            }, epoch)
            
            self.writer.add_scalar('Generalization Gap', abs(avg_train_loss - val_loss), epoch)
            self.writer.add_scalar('Gradient Norm', total_norm, epoch) # Log last batch grad norm
            
            for k, v in val_metrics.items():
                self.writer.add_scalar(f'Validation/{k}', v, epoch)
            
            print(f"Epoch {epoch+1} | Train Loss: {avg_train_loss:.4f} | Val Loss: {val_loss:.4f}")
            
            # --- Early Stopping & Checkpointing ---
            if val_loss < min_val_loss:
                min_val_loss = val_loss
                no_improve_epochs = 0
                best_epoch = epoch + 1
                torch.save(self.model.state_dict(), checkpoint_path)
                print(f"  -> Validation loss improved. Saved model to {checkpoint_path}")
            else:
                no_improve_epochs += 1
                print(f"  -> No improvement under {min_val_loss:.4f} for {no_improve_epochs} epochs.")
                
            if no_improve_epochs >= patience:
                print(f"Early stopping triggered after {patience} epochs without improvement.")
                break
                
        
        # Log Final Results to Text Tab (MarkDown Table)
        final_text = "### Final Results\n\n"
        final_text += "| Metric | Value |\n"
        final_text += "|---|---|\n"
        
        # Model Config
        if model_config:
            for k, v in model_config.items():
                final_text += f"| {k} | {v} |\n"
        
        # Training Stats
        final_text += f"| Epochs Trained | {epoch + 1} |\n"
        final_text += f"| Best Model Epoch (Real) | {best_epoch} |\n"
        final_text += f"| Best Validation Loss | {min_val_loss:.6f} |\n"
        final_text += f"| Final Train Loss | {avg_train_loss:.6f} |\n"
        
        for k, v in val_metrics.items():
             final_text += f"| Final {k} | {v:.4f} |\n"
            
        self.writer.add_text('Final_Summary', final_text, epoch)
        
        self.writer.flush()
        self.writer.close()
        
        return {
            'min_val_loss': min_val_loss,
            'epochs_trained': epoch + 1,
            'best_epoch': best_epoch,
            'final_train_loss': avg_train_loss,
            'final_val_loss': val_loss,
            'final_metrics': val_metrics
        }

    def _train_step(self, batch, step_fn):
        """
        Executes a single training step.
        step_fn(model, batch) -> (loss, metrics_dict)
        """
        return step_fn(self.model, batch)

    def evaluate(self, step_fn, eval_fn=None):
        self.model.eval()
        total_loss = 0.0
        total_metrics = {}
        
        with torch.no_grad():
            for batch in self.val_loader:
                # Move batch
                for k, v in batch.items():
                    if isinstance(v, torch.Tensor):
                        batch[k] = v.to(self.device)
                
                loss, metrics = step_fn(self.model, batch)
                
                total_loss += loss.item()
                
                # Accumulate metrics
                for k, v in metrics.items():
                    total_metrics[k] = total_metrics.get(k, 0.0) + v
                
                # Custom Evaluation (e.g. MAE un-normalized)
                if eval_fn:
                     custom_metrics = eval_fn(self.model, batch)
                     for k, v in custom_metrics.items():
                         total_metrics[k] = total_metrics.get(k, 0.0) + v
                         
        avg_loss = total_loss / len(self.val_loader)
        avg_metrics = {k: v / len(self.val_loader) for k, v in total_metrics.items()}
        
        return avg_loss, avg_metrics
