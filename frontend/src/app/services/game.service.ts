import { Injectable } from '@angular/core';
import { BehaviorSubject } from 'rxjs';
import { CardModel, DECK } from '../models/card.model';

export interface GameState {
    hands: { [key: string]: number[] };
    currentTrick: { playerId: string; cardId: number }[];
    currentPlayer: string;
    history: any[];
}

@Injectable({
    providedIn: 'root'
})
export class GameService {
    private deck: CardModel[] = [...DECK];
    private players = ['north', 'east', 'south', 'west'];

    private state = new BehaviorSubject<GameState>({
        hands: { north: [], east: [], south: [], west: [] },
        currentTrick: [],
        currentPlayer: 'south',
        history: []
    });

    public state$ = this.state.asObservable();

    constructor() { }

    startGame() {
        // Shuffle deck
        const newDeck = [...DECK];
        for (let i = newDeck.length - 1; i > 0; i--) {
            const j = Math.floor(Math.random() * (i + 1));
            [newDeck[i], newDeck[j]] = [newDeck[j], newDeck[i]];
        }
        this.deck = newDeck;

        // Distribute 8 cards to each player
        const hands = {
            north: newDeck.slice(0, 8).map(c => c.id),
            east: newDeck.slice(8, 16).map(c => c.id),
            south: newDeck.slice(16, 24).map(c => c.id),
            west: newDeck.slice(24, 32).map(c => c.id)
        };

        this.updateState({
            hands,
            currentTrick: [],
            currentPlayer: 'south',
            history: []
        });
    }

    playCard(playerId: string, cardId: number) {
        const currentState = this.state.value;

        if (currentState.currentPlayer !== playerId) {
            console.warn(`Not ${playerId}'s turn!`);
            return;
        }

        const hand = [...currentState.hands[playerId]];
        const cardIndex = hand.indexOf(cardId);

        if (cardIndex === -1) {
            console.warn(`Player ${playerId} does not have card ${cardId}`);
            return;
        }

        // Remove card from hand
        hand.splice(cardIndex, 1);
        const newHands = { ...currentState.hands, [playerId]: hand };

        // Add to trick
        const newTrick = [...currentState.currentTrick, { playerId, cardId }];

        // Add to history
        const newHistory = [...currentState.history, {
            action: 'PLAY_CARD',
            playerId,
            cardId,
            timestamp: new Date().toISOString()
        }];

        // Next player
        const currentPlayerIndex = this.players.indexOf(currentState.currentPlayer);
        const nextPlayerIndex = (currentPlayerIndex + 1) % 4;
        const nextPlayer = this.players[nextPlayerIndex];

        // Update state
        this.updateState({
            hands: newHands,
            currentTrick: newTrick,
            currentPlayer: nextPlayer,
            history: newHistory
        });

        // Check trick end (simplified)
        if (newTrick.length >= 4) {
            setTimeout(() => {
                this.updateState({
                    ...this.state.value,
                    currentTrick: [] // Clear trick
                });
            }, 1000);
        }
    }

    private updateState(newState: GameState) {
        this.state.next(newState);
    }
}
