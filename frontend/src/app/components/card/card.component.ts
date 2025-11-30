import { Component, input, computed } from '@angular/core';
import { CommonModule } from '@angular/common';
import { getCardById, CardModel } from '../../models/card.model';

@Component({
    selector: 'app-card',
    standalone: true,
    imports: [CommonModule],
    templateUrl: './card.component.html',
    styleUrls: ['./card.component.css']
})
export class CardComponent {
    // If card is provided, render face. If null, render back.
    card = input<CardModel | undefined>(undefined);

    suitColorClass = computed(() => {
        const c = this.card();
        return c && c.color === 'red' ? 'suit-red' : 'suit-black';
    });
}
