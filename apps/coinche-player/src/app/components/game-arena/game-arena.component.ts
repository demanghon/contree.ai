import { Component, Input, Output, EventEmitter, OnChanges, SimpleChanges } from '@angular/core';
import { CommonModule } from '@angular/common';
import { GameNode, DotParserService, GameEdge } from '../../services/dot-parser.service';

interface HistoryItem {
    node: GameNode;
    edge: GameEdge;
}

interface PastTrick {
    cards: string[];
    trickScore: { ns: number, ew: number };
    cumulativeScore: { ns: number, ew: number };
    endHistoryIndex: number;
}

@Component({
    selector: 'app-game-arena',
    standalone: true,
    imports: [CommonModule],
    templateUrl: './game-arena.component.html',
    styleUrls: ['./game-arena.component.css'],
})
export class GameArenaComponent implements OnChanges {
    @Input() dotContent: string = '';
    @Output() requestNewGame = new EventEmitter<void>();

    rootNode: GameNode | null = null;
    currentNode: GameNode | null = null;
    // history: HistoryItem[] = []; // This line is removed as per instruction

    // Display State
    hands: string[][] = [[], [], [], []];
    currentTrick: string[] = [];
    currentPlayer: number = 0;
    trump: string = '';
    scores: number = 0;
    currentPoints: { ns: number, ew: number } = { ns: 0, ew: 0 };
    history: HistoryItem[] = [];
    pastTricks: PastTrick[] = [];
    // Just PV score for now

    constructor(private dotParser: DotParserService) { }

    ngOnChanges(changes: SimpleChanges): void {
        if (changes['dotContent'] && this.dotContent) {
            this.rootNode = this.dotParser.parse(this.dotContent);
            this.reset();
        }
    }

    reset() {
        if (this.rootNode) {
            this.currentNode = this.rootNode;
            this.history = [];
            this.updateState();
        }
    }

    selectChild(index: number) {
        if (!this.currentNode || !this.currentNode.children[index]) return;
        const edge = this.currentNode.children[index];
        if (edge.node) {
            this.history.push({ node: this.currentNode, edge: edge });
            this.currentNode = edge.node;
            this.updateState();
        }
    }

    undo() {
        if (this.history.length > 0) {
            const last = this.history.pop();
            if (last) {
                this.currentNode = last.node;
                this.updateState();
            }
        }
    }

    jumpToTrick(trick: PastTrick) {
        // Slice history to the point where this trick ended
        // trick.endHistoryIndex is the length of history at that point
        if (trick.endHistoryIndex <= this.history.length) {
            this.history = this.history.slice(0, trick.endHistoryIndex);

            // Update currentNode to the node after the last move in the sliced history
            if (this.history.length > 0) {
                const lastItem = this.history[this.history.length - 1];
                if (lastItem.edge.node) {
                    this.currentNode = lastItem.edge.node;
                }
            } else {
                // Should not happen for a trick, but safe fallback
                this.currentNode = this.rootNode;
            }

            this.updateState();
        }
    }

    updateState() {
        if (!this.rootNode || !this.currentNode) return;

        // 1. Reset Hands to Root
        this.hands = this.rootNode.hands ? this.rootNode.hands.map(h => [...h]) : [[], [], [], []];
        this.trump = this.rootNode.trump || '';

        // 2. Replay moves to remove cards from hands
        for (const item of this.history) {
            const player = item.node.player;
            const card = item.edge.card;
            if (player !== undefined && card) {
                // Remove card from player's hand
                this.hands[player] = this.hands[player].filter(c => c !== card);
            }
        }

        // 3. Update Current Trick and Player from Current Node
        this.currentTrick = this.currentNode.trick || [];
        this.currentPlayer = this.currentNode.player !== undefined ? this.currentNode.player : 0;
        this.scores = this.currentNode.score || 0;
        this.currentPoints = this.currentNode.currentPoints || { ns: 0, ew: 0 };

        // 4. Calculate Past Tricks
        this.pastTricks = [];
        let trickBuilder: string[] = this.rootNode.trick ? [...this.rootNode.trick] : [];
        let lastPoints = { ns: 0, ew: 0 };

        // Handle initial points if root has them (unlikely to be non-zero but good for correctness)
        if (this.rootNode.currentPoints) {
            lastPoints = { ...this.rootNode.currentPoints };
        }

        for (let i = 0; i < this.history.length; i++) {
            const item = this.history[i];
            const player = item.node.player;
            const card = item.edge.card;
            if (player !== undefined && card) {
                trickBuilder.push(`P${player}:${card}`);
                if (trickBuilder.length === 4) {
                    // Trick Complete
                    const currentPoints = item.edge.node?.currentPoints || { ns: 0, ew: 0 };

                    this.pastTricks.push({
                        cards: [...trickBuilder],
                        cumulativeScore: { ...currentPoints },
                        trickScore: {
                            ns: currentPoints.ns - lastPoints.ns,
                            ew: currentPoints.ew - lastPoints.ew
                        },
                        endHistoryIndex: i + 1
                    });

                    lastPoints = { ...currentPoints };
                    trickBuilder = [];
                }
            }
        }
    }
    isMaximizing(playerIndex: number): boolean {
        return playerIndex === 0 || playerIndex === 2;
    }

    formatCard(card: string): string {
        return card.replace('D', '♦')
            .replace('S', '♠')
            .replace('H', '♥')
            .replace('C', '♣');
    }

    formatTrump(trump: string): string {
        // Trump is a number string "0", "1", "2", "3"
        // 0=D, 1=S, 2=H, 3=C
        switch (trump) {
            case '0': return '♦';
            case '1': return '♠';
            case '2': return '♥';
            case '3': return '♣';
            default: return trump;
        }
    }

    isRedSuit(val: string): boolean {
        // Trump codes: 0=D, 2=H
        if (val === '0' || val === '2') return true;
        // Card codes: D, H
        if (val.includes('D') || val.includes('H')) return true;
        return false;
    }

    getPlayerFromCard(cardString: string): string {
        // Format: "P0:8H" -> "0"
        const parts = cardString.split(':');
        if (parts.length > 1) {
            return parts[0].replace('P', '');
        }
        return '';
    }

    getCardValue(cardString: string): string {
        // Format: "P0:8H" -> "8H"
        const parts = cardString.split(':');
        return parts.length > 1 ? parts[1] : cardString;
    }
}
