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
              Current Highest: {{ getDisplayValue(currentContract()?.value) }} {{ getSuit(currentContract()?.trump) }} by Player {{ contractOwner() }}
          </p>
      } @else {
          <p>No bids yet</p>
      }

      <div class="controls">
        <input type="number" [(ngModel)]="bidValue" step="10" [min]="minBid()" max="160">
        <button (click)="bidValue = 252" *ngIf="minBid() <= 252" class="mini-btn">Capot</button>
        <select [(ngModel)]="bidSuit">
            <option [ngValue]="0">Diamonds ♦</option>
            <option [ngValue]="1">Spades ♠</option>
            <option [ngValue]="2">Hearts ♥</option>
            <option [ngValue]="3">Clubs ♣</option>
        </select>
        <button (click)="placeBid()" [disabled]="!canBid()">Bid</button>
        <button (click)="pass()" class="pass">Pass</button>
        
        @if (canCoinche()) {
            <button (click)="coinche()" class="coinche">Coinche!</button>
        }
        @if (canSurcoinche()) {
            <button (click)="surcoinche()" class="coinche">Surcoinche!</button>
        }
      </div>
      
      @if (coincheLevel() > 0) {
          <div class="coinche-status">
              {{ coincheLevel() === 1 ? 'COINCHÉ!' : 'SURCOINCHÉ!' }}
          </div>
      }
      
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
    .coinche {
        background: #d32f2f;
        color: white;
        font-weight: bold;
    }
    .coinche-status {
        color: #d32f2f;
        font-weight: bold;
        font-size: 1.2em;
        margin-top: 10px;
        animation: pulse 1s infinite;
    }
    @keyframes pulse {
        0% { transform: scale(1); }
        50% { transform: scale(1.1); }
        100% { transform: scale(1); }
    }
    .error {
        color: red;
        font-size: 0.9em;
    }
    input { width: 60px; }
    .mini-btn {
        padding: 2px 5px;
        font-size: 0.8em;
        margin-left: 5px;
        background: #eee;
        border: 1px solid #ccc;
        cursor: pointer;
    }
  `]
})
export class BiddingPanelComponent {
  private gameService = inject(GameService);
  
  currentPlayer = this.gameService.currentPlayer;
  currentContract = computed(() => this.gameService.gameState()?.bidding?.contract);
  coincheLevel = computed(() => this.gameService.gameState()?.coinche_level ?? 0);
  contractOwner = computed(() => this.gameService.gameState()?.bidding?.contract_owner ?? -1);
  
  bidValue: number = 80;
  bidSuit: number = 0;
  
  errorMsg: string = '';

  minBid = computed(() => {
     const c = this.currentContract();
     // If coinched, you can't bid values, you can only Pass or Surcoinche.
     if (this.coincheLevel() > 0) return 999;
     if (!c) return 80;

     if (c.value >= 160 && c.value < 252) return 252;
     if (c.value >= 252) return 999; // Cannot bid higher than Capot
     
     return c.value + 10;
  });

  canCoinche = computed(() => {
      // Must have contract, level 0
      if (!this.currentContract() || this.coincheLevel() > 0) return false;
      // Must be opponent's contract
      // Check turn is mine (handled by parent usually, but good to check)
      // Check Teams: (contractOwner % 2) != (currentPlayer % 2)
      return (this.contractOwner() % 2) !== (this.currentPlayer() % 2);
  });

  canSurcoinche = computed(() => {
      // Must be level 1
      if (this.coincheLevel() !== 1) return false;
      // Must be MY team's contract
      return (this.contractOwner() % 2) === (this.currentPlayer() % 2);
  });

  constructor() {
      // Auto-update bid value when contract changes
      effect(() => {
          this.bidValue = this.minBid();
          this.errorMsg = '';
      });
  }

  canBid() {
      return this.bidValue >= this.minBid() && this.bidValue <= 252 && this.coincheLevel() === 0;
  }

  placeBid() {
    this.errorMsg = '';
    if (!this.canBid()) {
        this.errorMsg = `Bid must be at least ${this.minBid()}`;
        return;
    }
    
    this.gameService.bid(this.bidValue, this.bidSuit)?.add(() => {
    });
  }

  pass() {
    this.gameService.pass();
  }

  coinche() {
      this.gameService.coinche();
  }

  surcoinche() {
      this.gameService.surcoinche();
  }
  
  getSuit(s?: number) {
      return ['♦', '♠', '♥', '♣', 'NT', 'AT'][s ?? 0] || '';
  }

  getDisplayValue(v?: number) {
      if (v === 252) return 'Capot';
      return v;
  }
}
