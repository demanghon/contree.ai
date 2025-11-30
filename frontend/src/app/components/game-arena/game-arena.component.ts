import { Component, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { toSignal } from '@angular/core/rxjs-interop';
import { GameService } from '../../services/game.service';
import { CardComponent } from '../card/card.component';
import { getCardById } from '../../models/card.model';

@Component({
    selector: 'app-game-arena',
    standalone: true,
    imports: [CommonModule, CardComponent],
    templateUrl: './game-arena.component.html',
    styleUrls: ['./game-arena.component.css']
})
export class GameArenaComponent {
    private gameService = inject(GameService);

    // Convert observable to signal
    gameState = toSignal(this.gameService.state$);

    opponents = [
        { id: 'north', name: 'Laurence', position: 'player-north' },
        { id: 'west', name: 'Benoit', position: 'player-west' },
        { id: 'east', name: 'Ladinde', position: 'player-east' },
    ];

    constructor() {
        this.gameService.startGame();
    }

    handleCardClick(cardId: number): void {
        const state = this.gameState();
        if (state && state.currentPlayer === 'south') {
            this.gameService.playCard('south', cardId);
        }
    }

    getTransform(index: number): string {
        return `translate(-50%, -50%) rotate(${index * 10 - 15}deg)`;
    }

    getCard(id: number) {
        return getCardById(id);
    }
}
