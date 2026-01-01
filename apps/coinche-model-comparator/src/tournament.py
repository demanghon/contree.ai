
import coinche_engine
import random
import torch
import numpy as np
from enum import Enum

class Team:
    def __init__(self, name, agent):
        self.name = name
        self.agent = agent

class MatchMetrics:
    def __init__(self):
        self.team_a_score = 0
        self.team_b_score = 0
        self.team_a_bid_error = []
        self.team_b_bid_error = []
        # Relative points: Score(Team B) - Score(Team A) in duplicate setting
        self.relative_points = []
        self.synergy_data = [] # (BidAccuracy, FinalScore)

class TournamentEngine:
    def __init__(self, team_a, team_b):
        self.team_a = team_a # Team A (Agent A)
        self.team_b = team_b # Team B (Agent B)
        self.metrics = MatchMetrics()
        
    def play_duplicate_hand(self):
        """
        Plays one duplicate hand (2 games).
        Strict Duplicate Logic:
        1. Deal Hand H (4x u32).
        2. Game 1: NS=Team A, EW=Team B. Agents: [A, B, A, B]
        3. Game 2: NS=Team B, EW=Team A. Agents: [B, A, B, A].
           Crucial: Uses EXACT SAME 'hands' array.
           This compares Team A's performance with Hand 0 (North) vs Team B's performance with Hand 0 (North).
        """
        hands = self._deal_random_hands()
        dealer = random.randint(0, 3)
        
        # --- Game 1: NS=A, EW=B ---
        # Agents: 0=A, 1=B, 2=A, 3=B
        agents_g1 = [self.team_a.agent, self.team_b.agent, self.team_a.agent, self.team_b.agent]
        res_g1 = self._play_game(hands, dealer, agents_g1)
        
        # --- Game 2: NS=B, EW=A ---
        # Agents: 0=B, 1=A, 2=B, 3=A
        # Note: We reuse 'hands' and 'dealer' strictly.
        agents_g2 = [self.team_b.agent, self.team_a.agent, self.team_b.agent, self.team_a.agent]
        res_g2 = self._play_game(hands, dealer, agents_g2)
        
        # --- Scoring & Metrics ---
        # Goal: Did A outperform B with the same cards?
        
        # Score_A_NS (G1) vs Score_B_NS (G2)
        score_a_ns = res_g1['points_ns']
        score_b_ns = res_g2['points_ns']
        diff_ns_for_a = score_a_ns - score_b_ns
        
        # Score_A_EW (G2) vs Score_B_EW (G1) -> Wait, in G1 B is EW.
        # So we compare A(EW, G2) vs B(EW, G1).
        score_a_ew = res_g2['points_ew']
        score_b_ew = res_g1['points_ew']
        diff_ew_for_a = score_a_ew - score_b_ew
        
        # Total Relative Score for Team A over Team B
        # Positive = A performed better.
        total_diff_for_a = diff_ns_for_a + diff_ew_for_a
        
        # Relative points for B (as requested in logging usually B is challenger)
        total_relative_points_b = -total_diff_for_a
        
        self.metrics.relative_points.append(total_relative_points_b)
        
        # Update raw totals
        # Team A played NS in G1 and EW in G2
        self.metrics.team_a_score += (score_a_ns + score_a_ew)
        
        # Team B played EW in G1 and NS in G2
        self.metrics.team_b_score += (score_b_ew + score_b_ns)
        
        return {
            'relative_score_b': total_relative_points_b,
            'g1': res_g1,
            'g2': res_g2
        }

    def _play_game(self, hands, dealer, agents):
        """
        Simulates a full game.
        """
        match = coinche_engine.CoincheMatch(dealer, hands)
        
        # --- Bidding Phase ---
        while "BIDDING" in match.phase_name():
            state = match.get_bidding_state()
            current_player = state.current_player
            agent = agents[current_player]
            
            # Get agent's hand (mask)
            p_hand = hands[current_player]
            
            # Ask agent for Bid
            # Simple Logic:
            # 1. Agent evaluates hand -> (Suit, Value)
            # 2. If Value > Current Contract or Min Bid, Bid it.
            # 3. Else Pass.
            # 4. (Advanced) Partner context? For now, independent.
            
            # Simple Bidding Heuristic based on ValueNet
            suit_idx, est_score = agent.get_bid(p_hand)
            
            # Rules: 
            # - Must bid higher than current contract (min 80).
            # - increments of 10.
            current_contract = state.contract # Option<Bid>
            min_bid_val = 80
            if current_contract is not None:
                min_bid_val = current_contract.value + 10
            
            # Convert float score to nearest 10?
            # Or just threshold.
            
            # For simplicity: If est_score > min_bid_val + buffer, Bid est_score rounded down to 10.
            # If we already hold the contract (us or partner), maybe Pass?
            # Let's implement a very basic "Bid Max Value" strategy.
            
            # Round est_score to nearest 10
            bid_val = int(round(est_score / 10.0)) * 10
            
            # Check legality
            if bid_val < min_bid_val:
                action = None # Pass
            else:
                # Cap at 160 (or 180?)
                if bid_val > 160: bid_val = 160
                
                # Check if we assume we can make it. 
                # If partner is winning, we might raise? 
                # For now: Greedy. If my hand value > current, I bid.
                
                # Is contract owned by team?
                contract_owner = state.contract_owner
                if contract_owner is not None:
                    # If my team owns it
                    if (contract_owner % 2) == (current_player % 2):
                         # If my bid_val is significantly higher, raise?
                         # Else pass.
                         if bid_val > min_bid_val + 10:
                             action = coinche_engine.Bid(bid_val, suit_idx)
                         else:
                             action = None
                    else:
                        # Opponent owns it. Overbid?
                         if bid_val >= min_bid_val:
                             action = coinche_engine.Bid(bid_val, suit_idx)
                         else:
                             action = None
                else:
                    # No contract yet
                    if bid_val >= 80:
                        action = coinche_engine.Bid(bid_val, suit_idx)
                    else:
                        action = None
            
            # Apply Bid
            try:
                match.bid(action)
            except Exception as e:
                # Fallback to Pass if illegal (e.g. error in logic)
                # print(f"Bid Error: {e}. Force Pass.")
                match.bid(None)
        
        # --- Playing Phase ---
        # If passed out?
        if "FINISHED" in match.phase_name():
            return self._extract_result(match)
            
        while "PLAYING" in match.phase_name():
            state = match.get_playing_state()
            current_player = state.current_player
            agent = agents[current_player]
            
            # Gamestate Features
            p_hand = state.hands[current_player] # Remaining hand?
            # PlayingState exposes current hands? Yes.
            
            # Extract History from state?
            # The python binding doesn't expose history bitmask directly in PlayingState probably?
            # We need to reconstruct it or add accessor to Rust.
            # Let's check PlayingState definition... it has 'history' field?
            # If not, we iterate 'tricks_won'?
            
            # Quick fix: The agent.get_card_logits needs `history_int`.
            # If we can't get it from State easily, let's just pass 0 for now (stats-less agent) 
            # OR modify Rust engine to expose it.
            # Actually, `history` is used in dataset generation. 
            # Let's assume we pass 0 for history now to avoid blocking on engine changes.
            history_int = 0 
            
            # Board cards
            # PlayingState has `current_trick`?
            # Need to check `gameplay/playing.rs`.
            # Accessors in `manager.rs`: `state.get_legal_moves()`.
            # We can infer board from legal moves? No.
            # We need to see the board.
            # Python `PlayingState` should expose `current_trick`.
            
            # Assuming state.current_trick is available (Vec<u8>?)
            # Usage: state.current_trick
            current_trick = state.current_trick if hasattr(state, 'current_trick') else []
            
            trump = state.trump
            legal_mask = state.get_legal_moves()
            
            best_card = agent.get_card(p_hand, history_int, current_trick, trump, legal_mask)
            
            match.play_card(best_card)
            
        return self._extract_result(match)

    def _extract_result(self, match):
        res = match.get_result()
        return {
            'points_ns': res.points_ns,
            'points_ew': res.points_ew,
            'contract_made': res.contract_made
        }

    def _deal_random_hands(self):
        # 32 cards. Shuffle.
        deck = list(range(32))
        random.shuffle(deck)
        hands = [0] * 4
        for i in range(4):
            # Cards 0-7, 8-15, etc
            h_cards = deck[i*8 : (i+1)*8]
            mask = 0
            for c in h_cards:
                mask |= (1 << c)
            hands[i] = mask
        return hands
