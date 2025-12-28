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
        @if (points()) {
            <div class="score-board">
                <span>NS: {{ points()![0] }}</span>
                <span>EW: {{ points()![1] }}</span>
            </div>
        }
      </div>

      <div class="main-content">
          <div class="felt">
            <!-- Player Spots -->
            <app-player-spot [playerIndex]="2" class="spot top"></app-player-spot>
            <app-player-spot [playerIndex]="1" class="spot left"></app-player-spot>
            <app-player-spot [playerIndex]="3" class="spot right"></app-player-spot>
            <app-player-spot [playerIndex]="0" class="spot bottom"></app-player-spot>

            <!-- Last Trick Display (Top Right Corner) -->
            @if (lastTrick().length > 0) {
                <div class="last-trick-container">
                    <div class="last-trick-label">Last Trick</div>
                    <div class="last-trick-cards">
                        @for (card of lastTrick(); track card.player) {
                            <div class="mini-card-wrapper">
                                <span class="player-label">P{{card.player}}</span>
                                <div class="mini-card">
                                    <app-card [card]="card.card" [isLegal]="false" style="transform: scale(0.6); transform-origin: top left; display: block;"></app-card>
                                </div>
                            </div>
                        }
                        @if (lastTrickWinner() !== undefined) {
                            <div class="trick-winner">Winner: P{{ lastTrickWinner() }}</div>
                        }
                    </div>
                </div>
            }

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

          <!-- History Sidebar -->
          <div class="history-sidebar">
              <h3>History</h3>
              <div class="history-list">
                  @for (trick of trickHistory(); track $index) {
                      <div class="history-item">
                          <span class="trick-num">#{{ $index + 1 }}</span>
                          <span class="trick-winner-badge">P{{ trick.winner }}</span>
                          <div class="history-cards">
                              @for (c of trick.cards; track c.player) {
                                  <span class="history-card-text" [class.red]="c.card.suit === 0 || c.card.suit === 2">
                                      {{ getRankSymbol(c.card.rank) }}{{ getSuit(c.card.suit) }}
                                  </span>
                              }
                          </div>
                      </div>
                  }
              </div>
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
        width: 100%;
        box-sizing: border-box;
        height: 50px;
    }
    .score-board {
        margin-left: auto;
        display: flex;
        gap: 15px;
        font-weight: bold;
        font-size: 1.1em;
        background: #333;
        padding: 5px 15px;
        border-radius: 4px;
    }
    
    .main-content {
        display: flex;
        flex: 1;
        overflow: hidden;
    }

    .felt {
        flex: 1;
        background: radial-gradient(circle, #2a8a4a 0%, #1a5a3a 100%);
        position: relative;
        display: flex;
        justify-content: center;
        align-items: center;
    }
    
    .history-sidebar {
        width: 200px;
        background: #1e1e1e;
        color: #ddd;
        border-left: 1px solid #444;
        display: flex;
        flex-direction: column;
        padding: 10px;
        overflow-y: auto;
    }
    .history-sidebar h3 {
        margin-top: 0;
        border-bottom: 1px solid #444;
        padding-bottom: 5px;
        font-size: 1.1em;
    }
    .history-item {
        background: #333;
        margin-bottom: 5px;
        padding: 5px;
        border-radius: 4px;
        font-size: 0.9em;
    }
    .trick-num {
        color: #888;
        margin-right: 5px;
    }
    .trick-winner-badge {
        background: #555;
        padding: 1px 4px;
        border-radius: 3px;
        font-size: 0.8em;
    }
    .history-cards {
        display: flex;
        gap: 5px;
        margin-top: 2px;
    }
    .history-card-text {
        font-weight: bold;
    }
    .red { color: #ff6666; }

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
    
    .last-trick-container {
        position: absolute;
        top: 20px;
        left: 20px;
        background: rgba(0,0,0,0.4);
        padding: 10px;
        border-radius: 8px;
        display: flex;
        flex-direction: column;
        gap: 5px;
        pointer-events: none;
    }
    .last-trick-label {
        color: rgba(255,255,255,0.8);
        font-size: 0.8em;
        text-transform: uppercase;
    }
    .last-trick-cards {
        display: flex;
        gap: 5px;
        flex-direction: column;
    }
    .trick-winner {
        color: gold;
        font-weight: bold;
        font-size: 0.8em;
    }
    .mini-card-wrapper {
        display: flex;
        align-items: center;
        gap: 5px;
    }
    .player-label {
        color: white;
        font-size: 0.7em;
        width: 20px;
    }
    .mini-card {
        width: 40px; 
        height: 60px;
        overflow: hidden; 
    }
  `]
})
export class GameTableComponent {
  gameService = inject(GameService);

  phase = computed(() => this.gameService.gameState()?.phase);
  contract = computed(() => this.gameService.gameState()?.contract);
  contractOwner = computed(() => this.gameService.gameState()?.contract_owner || this.gameService.gameState()?.bidding?.contract_owner);
  result = computed(() => this.gameService.gameState()?.result);
  
  points = computed(() => this.gameService.gameState()?.playing?.points);
  lastTrickWinner = computed(() => this.gameService.gameState()?.playing?.last_trick_winner);

  // Local History
  trickHistory = signal<{winner: number, cards: {player:number, card:any}[]}[]>([]);

  lastTrick = computed(() => {
     const state = this.gameService.gameState();
     if (!state || !state.playing || !state.playing.last_trick) return [];
     const trickSource = state.playing.last_trick;
     const cards = [];
      for (let i = 0; i < 4; i++) {
          if (trickSource[i] !== 255) {
              cards.push({ player: i, card: this.decodeCard(trickSource[i]) });
          }
      }
      return cards;
  });

  // Track last seen trick winner to detect changes (NEW TRICK COMPLETED)
  private lastSeenWinner = signal<number | undefined>(undefined);
  // Track last phase to detect Game Start (reset history)
  private lastPhase = signal<string | undefined>(undefined);

  constructor() {
      effect(() => {
          const state = this.gameService.gameState();
          
          // 1. Detect Game Restart (Phase changed to BIDDING from something else, or just BIDDING initially)
          if (state?.phase === 'BIDDING' && this.lastPhase() !== 'BIDDING') {
              this.trickHistory.set([]); // Reset History
              this.lastSeenWinner.set(undefined);
          }
          this.lastPhase.set(state?.phase);

          // 2. Detect New Trick
          if (state?.playing?.last_trick_winner !== undefined) {
              const winner = state.playing.last_trick_winner;
              if (winner !== this.lastSeenWinner()) {
                  // New trick completed!
                  const trickCards = this.lastTrick(); // This is the trick that just finished
                  this.trickHistory.update(h => [...h, { winner, cards: trickCards }]);
                  this.lastSeenWinner.set(winner);
                  
                  // Pause 2s to show result
                  this.scheduleNextStep(2000);
                  return;
              }
          }

          // 3. Regular AI Move Scheduling (1s delay)
          this.scheduleNextStep(1000);

      }, { allowSignalWrites: true });
  }

  private stepTimeout: any;

  scheduleNextStep(delay: number) {
      if (this.stepTimeout) clearTimeout(this.stepTimeout);

      this.stepTimeout = setTimeout(() => {
          const state = this.gameService.gameState();
          if (!state) return;

          // Check if AI Turn
          // Helper: is AI turn?
          const currentPlayer = this.gameService.currentPlayer();
          
          // Conditions to auto-step:
          // 1. Phase is BIDDING or PLAYING
          // 2. Current player is NOT 0 (Human) (unless playAll is true)
          // 3. Not finished
          
          if (state.phase === 'FINISHED') return;

          const isAiTurn = (currentPlayer !== 0) || this.gameService.playAll();
          
          if (isAiTurn) {
              this.gameService.step();
          }
      }, delay);
  }

  currentTrick = computed(() => {
      const state = this.gameService.gameState();
      if (!state || !state.playing) return [];
      
      const trickSource = state.playing.current_trick;
      if (!trickSource) return [];

      const cards = [];
      for (let i = 0; i < 4; i++) {
          if (trickSource[i] !== 255) { // 255 or 0xFF is empty
              cards.push({ player: i, card: this.decodeCard(trickSource[i]) });
          }
      }
      return cards;
  });

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
  
  getRankSymbol(rank: number): string {
    return ['7', '8', '9', '10', 'J', 'Q', 'K', 'A'][rank] || '?';
  }

  private decodeCard(id: number) {
    return {
      id,
      suit: Math.floor(id / 8),
      rank: id % 8
    };
  }
}
