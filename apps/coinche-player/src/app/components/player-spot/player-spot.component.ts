import { Component, Input, computed, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { GameService } from '../../services/game.service';
import { HandComponent } from '../hand/hand.component';

@Component({
  selector: 'app-player-spot',
  standalone: true,
  imports: [CommonModule, HandComponent],
  template: `
    <div class="player-spot" [class.active]="isActive()">
      <div class="avatar">P{{ playerIndex }}</div>
      
      @if (showHand()) {
        <app-hand 
            [cards]="cards()" 
            [canPlay]="canPlay()">
        </app-hand>
      } @else {
        <div class="card-back-stack">
            {{ cards().length }} cards
        </div>
      }
      
      <div class="info">
        @if (isDealer()) { <span class="dealer-chip">D</span> }
        {{ getName() }}
      </div>
    </div>
  `,
  styles: [`
    .player-spot {
      display: flex;
      flex-direction: column;
      align-items: center;
      padding: 10px;
      border-radius: 8px;
      transition: background 0.3s;
    }
    .player-spot.active {
        background: rgba(255, 255, 0, 0.2);
        box-shadow: 0 0 10px yellow;
    }
    .avatar {
        width: 40px;
        height: 40px;
        border-radius: 50%;
        background: #333;
        color: white;
        display: flex;
        justify-content: center;
        align-items: center;
        font-weight: bold;
        margin-bottom: 5px;
    }
    .card-back-stack {
        width: 60px;
        height: 90px;
        background: navy;
        border-radius: 4px;
        border: 2px solid white;
        color: white;
        display: flex;
        justify-content: center;
        align-items: center;
    }
    .dealer-chip {
        background: orange;
        border-radius: 50%;
        padding: 2px 5px;
        font-size: 0.8rem;
        margin-right: 5px;
    }
  `]
})
export class PlayerSpotComponent {
  @Input({ required: true }) playerIndex!: number;
  
  private gameService = inject(GameService);

  cards = computed(() => this.gameService.getHandCards(this.playerIndex));
  
  isActive = computed(() => this.gameService.currentPlayer() === this.playerIndex);
  
  isDealer = computed(() => {
      const state = this.gameService.gameState();
      return state ? state.dealer === this.playerIndex : false;
  });

  showHand = computed(() => {
      // Show if:
      // 1. Omniscient/Debug Mode is ON
      if (this.gameService.isOmniscient()) return true;
      // 2. Or it's Player 0 (Me) - Assume P0 is the main local user
      if (this.playerIndex === 0) return true;
      // 3. Or Play All is ON AND it's their turn (Hotseat context switching)
      if (this.gameService.playAll() && this.isActive()) return true;
      
      return false;
  });

  canPlay = computed(() => {
      if (!this.isActive()) return false;
      // Can play if:
      // 1. It is Player 0
      if (this.playerIndex === 0) return true;
      // 2. Play All is ON
      if (this.gameService.playAll()) return true;
      
      return false;
  });

  getName() {
    return `Player ${this.playerIndex}`;
  }
}
