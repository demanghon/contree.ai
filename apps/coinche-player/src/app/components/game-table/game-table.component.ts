import { Component, computed, inject, signal, effect } from '@angular/core';
import { CommonModule } from '@angular/common';
import { GameService } from '../../services/game.service';
import { PlayerSpotComponent } from '../player-spot/player-spot.component';
import { CardComponent } from '../card/card.component';
import { BiddingPanelComponent } from '../bidding/bidding.component';

@Component({
  selector: 'app-game-table',
  standalone: true,
  imports: [CommonModule, PlayerSpotComponent, CardComponent, BiddingPanelComponent],
  template: `
    <div class="table-container">
      <div class="toolbar">
        <label>
            <input type="checkbox" 
                [checked]="gameService.isOmniscient()" 
                (change)="toggleOmniscient()">
            Show All Cards
        </label>
        <label>
            <input type="checkbox" 
                [checked]="gameService.playAll()" 
                (change)="togglePlayAll()">
            Play All (Hotseat)
        </label>
        <span class="status">Phase: {{ phase() }} | Trump: {{ trumpSumbol() }}</span>
        @if (contract()) {
            <span class="contract">Contract: {{ contract()?.value }} {{ getSuit(contract()?.trump) }} by P{{ contractOwner() }}</span>
        }
      </div>

      <div class="felt">
        <!-- Player Spots -->
        <app-player-spot [playerIndex]="2" class="spot top"></app-player-spot>
        <app-player-spot [playerIndex]="1" class="spot left"></app-player-spot>
        <app-player-spot [playerIndex]="3" class="spot right"></app-player-spot>
        <app-player-spot [playerIndex]="0" class="spot bottom"></app-player-spot>

        <!-- Center Area (Trick + Bidding UI) -->
        <div class="center-area">
            @if (phase() === 'BIDDING') {
                <app-bidding-panel></app-bidding-panel>
            }
            
            @if (phase() === 'PLAYING') {
                <div class="trick">
                    @for (card of currentTrick(); track card.player) {
                        <div class="trick-card" [class.p0]="card.player===0" [class.p1]="card.player===1" [class.p2]="card.player===2" [class.p3]="card.player===3">
                            <app-card [card]="card.card" [isLegal]="true"></app-card>
                        </div>
                    }
                    @if (viewingLastTrick()) {
                        <div class="next-trick-overlay">
                            <button (click)="nextTrick()" class="next-btn">Next Trick</button>
                        </div>
                    }
                </div>
            }
            
            @if (phase() === 'FINISHED') {
                <div class="result-banner">
                    <h2>Game Over</h2>
                    <p>NS: {{ result()?.points_ns }} | EW: {{ result()?.points_ew }}</p>
                    <p>{{ result()?.contract_made ? 'CONTRACT MADE' : 'CONTRACT FAILED' }}</p>
                    <button (click)="gameService.createGame()">New Game</button>
                </div>
            }
        </div>
      </div>
    </div>
  `,
  styles: [`
    .table-container {
        display: flex;
        flex-direction: column;
        height: 100vh;
        width: 100vw;
        overflow: hidden;
    }
    .toolbar {
        background: #222;
        color: white;
        padding: 10px;
        display: flex;
        gap: 20px;
        align-items: center;
    }
    .felt {
        flex: 1;
        background: radial-gradient(circle, #2a8a4a 0%, #1a5a3a 100%);
        position: relative;
        display: flex;
        justify-content: center;
        align-items: center;
    }
    .spot {
        position: absolute;
    }
    .top { top: 20px; }
    .bottom { bottom: 20px; }
    .left { left: 20px; top: 50%; transform: translateY(-50%); }
    .right { right: 20px; top: 50%; transform: translateY(-50%); }

    .center-area {
        z-index: 10;
        pointer-events: none; /* Let clicks pass through if empty */
        display: flex;
        justify-content: center;
        align-items: center;
    }
    
    .trick {
        position: relative;
        width: 200px;
        height: 200px;
    }
    .trick-card {
        position: absolute;
    }
    /* Positioning trick cards slightly offset to show who played them */
    .p0 { bottom: 0; left: 50%; transform: translateX(-50%); }
    .p1 { left: 0; top: 50%; transform: translateY(-50%); }
    .p2 { top: 0; left: 50%; transform: translateX(-50%); }
    .p3 { right: 0; top: 50%; transform: translateY(-50%); }

    .result-banner {
        background: rgba(0,0,0,0.8);
        color: white;
        padding: 40px;
        border-radius: 10px;
        text-align: center;
        pointer-events: auto;
    }
    .next-trick-overlay {
        position: absolute;
        top: 50%;
        left: 50%;
        transform: translate(-50%, -50%);
        z-index: 20;
        pointer-events: auto;
    }
    .next-btn {
        padding: 10px 20px;
        font-size: 1.2em;
        background: #ffcc00;
        border: none;
        border-radius: 5px;
        cursor: pointer;
        box-shadow: 0 4px 10px rgba(0,0,0,0.5);
    }
  `]
})
export class GameTableComponent {
  gameService = inject(GameService);

  phase = computed(() => this.gameService.gameState()?.phase);
  contract = computed(() => this.gameService.gameState()?.contract);
  contractOwner = computed(() => this.gameService.gameState()?.contract_owner || this.gameService.gameState()?.bidding?.contract_owner);
  result = computed(() => this.gameService.gameState()?.result);

  viewingLastTrick = signal<boolean>(false);
  
  // Track last seen trick winner to detect changes
  private lastSeenWinner = signal<number | undefined>(undefined);

  constructor() {
      effect(() => {
          const state = this.gameService.gameState();
          if (state?.playing?.last_trick_winner !== undefined) {
              const winner = state.playing.last_trick_winner;
              // If winner changed, it means a new trick finished.
              if (winner !== this.lastSeenWinner()) {
                  this.viewingLastTrick.set(true);
                  this.lastSeenWinner.set(winner);
              }
          }
      }, { allowSignalWrites: true });
  }

  currentTrick = computed(() => {
      const state = this.gameService.gameState();
      if (!state || !state.playing) return [];
      
      const showLast = this.viewingLastTrick();
      const trickSource = showLast ? state.playing.last_trick : state.playing.current_trick;
      
      if (!trickSource) return [];

      const cards = [];
      for (let i = 0; i < 4; i++) {
          if (trickSource[i] !== 255) { // 255 or 0xFF is empty
              cards.push({ player: i, card: this.decodeCard(trickSource[i]) });
          }
      }
      return cards;
  });

  nextTrick() {
      this.viewingLastTrick.set(false);
  }

  toggleOmniscient() {
      this.gameService.isOmniscient.update(v => !v);
  }

  togglePlayAll() {
      this.gameService.playAll.update(v => !v);
  }
  
  trumpSumbol() {
     const s = this.gameService.gameState()?.playing?.trump;
     return s !== undefined ? this.getSuit(s) : '-';
  }

  getSuit(s?: number) {
      return ['♦', '♠', '♥', '♣', 'NT', 'AT'][s ?? 0] || '';
  }

  private decodeCard(id: number) {
    return {
      id,
      suit: Math.floor(id / 8),
      rank: id % 8
    };
  }
}
