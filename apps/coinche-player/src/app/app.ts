import { Component, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { GameService } from './services/game.service';
import { GameTableComponent } from './components/game-table/game-table.component';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [CommonModule, GameTableComponent],
  template: `
    <div class="app-root">
      @if (!gameStarted()) {
        <div class="start-screen">
          <h1>Coinche Master</h1>
          <button (click)="startGame()">Start New Game</button>
        </div>
      } @else {
        <app-game-table></app-game-table>
      }
    </div>
  `,
  styles: [`
    .app-root {
        height: 100vh;
        width: 100vw;
        overflow: hidden;
    }
    .start-screen {
        height: 100%;
        display: flex;
        flex-direction: column;
        justify-content: center;
        align-items: center;
        background: #111;
        color: white;
    }
    button {
        font-size: 1.5rem;
        padding: 10px 30px;
        cursor: pointer;
    }
  `]
})
export class AppComponent {
  private gameService = inject(GameService);
  
  gameStarted = computed(() => !!this.gameService.gameState());

  startGame() {
    this.gameService.createGame();
  }
}

import { computed } from '@angular/core';
