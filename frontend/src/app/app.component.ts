import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { GameArenaComponent } from './components/game-arena/game-arena.component';

@Component({
    selector: 'app-root',
    standalone: true,
    imports: [CommonModule, GameArenaComponent],
    templateUrl: './app.component.html',
    styleUrls: ['./app.component.css']
})
export class AppComponent {
    title = 'frontend';
}
