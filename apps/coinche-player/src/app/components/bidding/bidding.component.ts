import { Component, inject, effect, computed } from '@angular/core';
import { CommonModule } from '@angular/common';
import { GameService } from '../../services/game.service';
import { FormsModule } from '@angular/forms';

@Component({
  selector: 'app-bidding-panel',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <div class="bidding-panel">
      <h3>Bidding (Player {{ currentPlayer() }})</h3>
      
      @if (currentContract()) {
          <p class="current-contract">
              Current Highest: {{ currentContract()?.value }} {{ getSuit(currentContract()?.trump) }}
          </p>
      } @else {
          <p>No bids yet</p>
      }

      <div class="controls">
        <input type="number" [(ngModel)]="bidValue" step="10" [min]="minBid()" max="180">
        <select [(ngModel)]="bidSuit">
            <option [ngValue]="0">Diamonds ♦</option>
            <option [ngValue]="1">Spades ♠</option>
            <option [ngValue]="2">Hearts ♥</option>
            <option [ngValue]="3">Clubs ♣</option>
        </select>
        <button (click)="placeBid()" [disabled]="!canBid()">Bid</button>
        <button (click)="pass()" class="pass">Pass</button>
      </div>
      
      @if (errorMsg) {
          <div class="error">{{ errorMsg }}</div>
      }
    </div>
  `,
  styles: [`
    .bidding-panel {
        background: white;
        padding: 20px;
        border-radius: 8px;
        box-shadow: 0 4px 10px rgba(0,0,0,0.3);
        pointer-events: auto;
        min-width: 300px;
        text-align: center;
    }
    .current-contract {
        color: #666;
        margin-bottom: 10px;
    }
    .controls {
        display: flex;
        gap: 10px;
        justify-content: center;
        margin-bottom: 10px;
    }
    .pass {
        background: #ccc;
    }
    .error {
        color: red;
        font-size: 0.9em;
    }
    input { width: 60px; }
  `]
})
export class BiddingPanelComponent {
  private gameService = inject(GameService);
  
  currentPlayer = this.gameService.currentPlayer;
  currentContract = computed(() => this.gameService.gameState()?.contract);
  
  bidValue: number = 80;
  bidSuit: number = 0;
  
  errorMsg: string = '';

  minBid = computed(() => {
     const c = this.currentContract();
     return c ? c.value + 10 : 80;
  });

  constructor() {
      // Auto-update bid value when contract changes
      effect(() => {
          this.bidValue = this.minBid();
          this.errorMsg = '';
      });
  }

  canBid() {
      return this.bidValue >= this.minBid();
  }

  placeBid() {
    this.errorMsg = '';
    if (!this.canBid()) {
        this.errorMsg = `Bid must be at least ${this.minBid()}`;
        return;
    }
    
    this.gameService.bid(this.bidValue, this.bidSuit)?.add(() => {
        // Callback after completion? 
        // RxJS subscription happens in service. 
        // If service throws error, we might catch it?
        // GameService currently swallows errors or logs to console.
    });
  }

  pass() {
    this.gameService.pass();
  }
  
  getSuit(s?: number) {
      return ['♦', '♠', '♥', '♣', 'NT', 'AT'][s ?? 0] || '';
  }
}
