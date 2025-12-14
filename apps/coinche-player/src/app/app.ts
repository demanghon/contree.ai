import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RouterOutlet } from '@angular/router';
import { GameArenaComponent } from './components/game-arena/game-arena.component';

@Component({
    selector: 'app-root',
    standalone: true,
    imports: [CommonModule, RouterOutlet, FormsModule, GameArenaComponent],
    templateUrl: './app.html',
    styleUrl: './app.css',
})
export class AppComponent {
    title = 'coinche-player';
    dotInput: string = '';
    gameLoaded: boolean = false;

    loadGame() {
        if (this.dotInput && this.dotInput.trim().length > 0) {
            this.gameLoaded = true;
        }
    }

    resetGame() {
        this.gameLoaded = false;
        this.dotInput = '';
    }
}
