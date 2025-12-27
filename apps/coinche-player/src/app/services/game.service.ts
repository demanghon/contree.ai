import { Injectable, signal, computed, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { tap } from 'rxjs';

export interface Card {
  id: number;
  suit: number;
  rank: number;
}

export interface BiddingState {
  history: ({ value: number; trump: number } | null)[];
  current_player: number;
  contract: { value: number; trump: number } | null;
  contract_owner: number | null;
}

export interface PlayingState {
  current_trick: number[];
  current_player: number;
  trump: number;
  tricks_won: number[];
  points: number[];
  trick_starter: number;
  legal_moves: number; // bitmask
}

export interface GameState {
  game_id: string;
  phase: 'BIDDING' | 'PLAYING' | 'FINISHED';
  dealer: number;
  hands?: number[]; // [u32] for 4 players if available (we will parse this)
  
  bidding?: BiddingState;
  playing?: PlayingState;
  result?: {
      points_ns: number;
      points_ew: number;
      contract_made: boolean;
  };
  contract?: { value: number; trump: number } | null;
}

@Injectable({
  providedIn: 'root'
})
export class GameService {
  private http = inject(HttpClient);
  private apiUrl = 'http://localhost:8000'; // Assuming verified backend port

  // Signals
  gameState = signal<GameState | null>(null);
  
  // Debug / Hotseat Flags
  isOmniscient = signal<boolean>(false); // Show all cards
  playAll = signal<boolean>(false); // Allow playing for everyone
  
  // Computed
  currentPlayer = computed(() => {
    const state = this.gameState();
    if (!state) return -1;
    if (state.phase === 'BIDDING' && state.bidding) return state.bidding.current_player;
    if (state.phase === 'PLAYING' && state.playing) return state.playing.current_player;
    return -1;
  });

  constructor() {}

  createGame() {
    return this.http.post<GameState>(`${this.apiUrl}/game/new`, {}).pipe(
      tap(state => this.gameState.set(state))
    ).subscribe();
  }

  getGame(gameId: string) {
    return this.http.get<GameState>(`${this.apiUrl}/game/${gameId}`).pipe(
      tap(state => this.gameState.set(state))
    ).subscribe();
  }

  bid(value: number, trump: number) {
    const state = this.gameState();
    if (!state) return;
    return this.http.post<GameState>(`${this.apiUrl}/game/${state.game_id}/bid`, { value, trump }).pipe(
      tap(res => this.gameState.set(res))
    ).subscribe();
  }

  pass() {
    const state = this.gameState();
    if (!state) return;
    return this.http.post<GameState>(`${this.apiUrl}/game/${state.game_id}/bid`, null).pipe(
      tap(res => this.gameState.set(res))
    ).subscribe();
  }

  playCard(cardId: number) {
    const state = this.gameState();
    if (!state) return;
    return this.http.post<GameState>(`${this.apiUrl}/game/${state.game_id}/play`, { card: cardId }).pipe(
      tap(res => this.gameState.set(res))
    ).subscribe();
  }

  // Helper to parse hands from u32 bitmask to Card objects
  getHandCards(playerIndex: number): Card[] {
    const state = this.gameState();
    if (!state || !state.hands) return [];
    
    // In our simplified backend (main.py), "hands" might not be populated in GET /game/{id} unless we modify it.
    // Wait, main.py says: # "hands": match.hands # Consider hiding
    // But for Omniscient mode we NEED it.
    // I should check if main.py sends hands.
    // It does send "hands" in create_game response, but commented out in get_game.
    // I need to UNCOMMENT it in backend if I want fresh state updates to include hands.
    // OR create_game returns hands, but subsequent updates (bid/play) call get_game.
    // So YES, I need to uncomment it in main.py.
    
    const handMask = state.hands[playerIndex];
    const cards: Card[] = [];
    for (let i = 0; i < 32; i++) {
      if ((handMask & (1 << i)) !== 0) {
        cards.push(this.decodeCard(i));
      }
    }
    // Sort by suit/rank? Visuals handle that.
    return cards;
  }
  
  // Bitmask helpers
    isCardLegal(cardId: number): boolean {
        const state = this.gameState();
        if(!state || state.phase !== 'PLAYING' || !state.playing) return false;
        
        // If it's my turn (or playAll is on)
        // AND card is in legal_moves bitmask
        const legalMask = state.playing.legal_moves;
        return (legalMask & (1 << cardId)) !== 0;
    }

  private decodeCard(id: number): Card {
    return {
      id,
      suit: Math.floor(id / 8),
      rank: id % 8
    };
  }
}
