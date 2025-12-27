import { Component, Input, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { GameService, Card } from '../../services/game.service';
import { CardComponent } from '../card/card.component';

@Component({
  selector: 'app-hand',
  standalone: true,
  imports: [CommonModule, CardComponent],
  template: `
    <div class="hand">
      @for (card of cards; track card.id) {
        <app-card 
          [card]="card" 
          [isLegal]="isCardLegal(card)"
          (cardClick)="playCard(card)">
        </app-card>
      }
    </div>
  `,
  styles: [`
    .hand {
      display: flex;
      flex-direction: row;
      gap: -20px; /* Overlap like a fan */
      justify-content: center;
      padding: 10px;
    }
    app-card {
        margin-right: -20px;
    }
    app-card:last-child {
        margin-right: 0;
    }
  `]
})
export class HandComponent {
  @Input({ required: true }) cards: Card[] = [];
  @Input() canPlay: boolean = false;
  
  private gameService = inject(GameService);

  isCardLegal(card: Card): boolean {
    if (!this.canPlay) return false;
    return this.gameService.isCardLegal(card.id);
  }

  playCard(card: Card) {
      console.log('Trying to play card', card);
    if (this.canPlay && this.gameService.isCardLegal(card.id)) {
      this.gameService.playCard(card.id);
    }
  }
}
