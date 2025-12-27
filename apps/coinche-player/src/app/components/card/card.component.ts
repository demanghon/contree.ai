import { Component, Input, Output, EventEmitter } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Card } from '../../services/game.service';

@Component({
  selector: 'app-card',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div class="card" 
         [class.red]="card.suit === 0 || card.suit === 2"
         [class.black]="card.suit === 1 || card.suit === 3"
         [class.illegal]="!isLegal"
         (click)="onClick()">
      <div class="rank">{{ getRankSymbol(card.rank) }}</div>
      <div class="suit">{{ getSuitSymbol(card.suit) }}</div>
    </div>
  `,
  styles: [`
    .card {
      width: 60px;
      height: 90px;
      background: white;
      border-radius: 8px;
      border: 1px solid #ccc;
      box-shadow: 2px 2px 5px rgba(0,0,0,0.2);
      display: flex;
      flex-direction: column;
      justify-content: center;
      align-items: center;
      font-weight: bold;
      font-size: 1.2rem;
      cursor: pointer;
      user-select: none;
      transition: transform 0.2s, opacity 0.2s;
    }
    .card:hover {
        transform: translateY(-10px);
    }
    .card.illegal {
        opacity: 0.4;
        cursor: not-allowed;
    }
    .card.illegal:hover {
        transform: none;
    }
    .red { color: #d00; }
    .black { color: #000; }
    .suit { font-size: 1.5rem; }
  `]
})
export class CardComponent {
  @Input({ required: true }) card!: Card;
  @Input() isLegal: boolean = true;
  @Output() cardClick = new EventEmitter<void>();

  onClick() {
    if (this.isLegal) {
      this.cardClick.emit();
    }
  }

  getSuitSymbol(suit: number): string {
    return ['♦', '♠', '♥', '♣'][suit] || '?';
  }

  getRankSymbol(rank: number): string {
    // 7, 8, 9, 10, J, Q, K, A
    return ['7', '8', '9', '10', 'J', 'Q', 'K', 'A'][rank] || '?';
  }
}
