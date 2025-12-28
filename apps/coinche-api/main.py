from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import coinche_engine
from typing import Optional, List
import uuid
import os

from ai_agent import AIAgent

app = FastAPI()

# Config
MODELS_DIR = "../../models" # relative to apps/coinche-api
if not os.path.exists(MODELS_DIR):
    # Try absolute path if relative fails
    MODELS_DIR = "/home/demanghon/.gemini/antigravity/scratch/contree.ai/models"

ai_agent = AIAgent(MODELS_DIR)

origins = [
    "http://localhost:4200",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory storage for games
games = {} 

class CreateGameRequest(BaseModel):
    dealer: int = 0
    # Flattened hands [u32] for 4 players (4 integers)
    hands: Optional[List[int]] = None 

class BidRequest(BaseModel):
    value: int
    trump: int

class PlayCardRequest(BaseModel):
    card_index: int # 0-31


def auto_play_ai(match: coinche_engine.CoincheMatch):
    """
    Automatically plays turns for AI players (1, 2, 3) until it's Human's (0) turn 
    or the phase changes/ends.
    """
    while True:
        phase = match.phase_name()
        
        # Stop if game finished
        if phase == "FINISHED":
            break
            
        current_player = 0
        
        if phase == "BIDDING":
            bs = match.get_bidding_state()
            if not bs: break
            current_player = bs.current_player
            
            # If Human turn, stop
            if current_player == 0:
                break
                
            # AI Logic
            hand = match.hands[current_player]
            contract = bs.contract
            
            bid = ai_agent.get_bid(hand, contract)
            match.bid(bid) # None = Pass
            
        elif phase == "PLAYING":
            ps = match.get_playing_state()
            if not ps: break
            current_player = ps.current_player
            
            # If Human turn, stop
            if current_player == 0:
                break
                
            # AI Logic
            hand = match.hands[current_player]
            legal_moves = ps.get_legal_moves()
            
            # Construct partial game state for AI
            game_state = {
                'current_trick': ps.current_trick,
                'trump': ps.trump
                # 'history': ??? (Missing history mask)
            }
            
            card = ai_agent.get_play(game_state, hand, legal_moves)
            match.play_card(card)
            
        else:
            break


@app.post("/game/new")
def create_game(req: CreateGameRequest):
    game_id = str(uuid.uuid4())
    
    hands = req.hands
    if hands is None:
        # Generate random hands
        # coinche_engine.generate_bidding_hands(1) returns ([u32; 4], [u8; 1])
        generated_hands, _ = coinche_engine.generate_bidding_hands(1)
        hands = generated_hands
        
    try:
        match = coinche_engine.CoincheMatch(req.dealer, hands)
        games[game_id] = match
        
        # Check if AI needs to start (e.g. if Dealer was 0, P1 starts)
        auto_play_ai(match)
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
        
    return get_game(game_id)

@app.get("/game/{game_id}")
def get_game(game_id: str):
    if game_id not in games:
        raise HTTPException(status_code=404, detail="Game not found")
    match = games[game_id]
    
    state = {
        "game_id": game_id,
        "phase": match.phase_name(),
        "dealer": match.dealer,
        "coinche_level": match.coinche_level,
        "contract_owner": match.contract_owner,
        "hands": match.hands 
    }
    
    if match.phase_name() == "BIDDING":
        bs = match.get_bidding_state()
        if bs:
            state["bidding"] = {
                "history": [{"value": b.value, "trump": b.trump} if b else None for b in bs.history],
                "current_player": bs.current_player,
                "contract": {"value": bs.contract.value, "trump": bs.contract.trump} if bs.contract else None,
                "contract_owner": bs.contract_owner
            }
    elif match.phase_name() == "PLAYING":
        ps = match.get_playing_state()
        if ps:
            state["playing"] = {
                "current_trick": ps.current_trick,
                "current_player": ps.current_player,
                "trump": ps.trump,
                "tricks_won": ps.tricks_won,
                "points": ps.points,
                "trick_starter": ps.trick_starter,
                "legal_moves": ps.get_legal_moves(),
                "last_trick": ps.last_trick,
                "last_trick_starter": ps.last_trick_starter,
                "last_trick_winner": ps.last_trick_winner
            }
        
        state["contract"] = {"value": match.contract.value, "trump": match.contract.trump} if match.contract else None
        
    elif match.phase_name() == "FINISHED":
        res = match.get_result()
        if res:
            state["result"] = {
                 "points_ns": res.points_ns,
                 "points_ew": res.points_ew,
                 "contract_made": res.contract_made
            }
        
    return state

@app.post("/game/{game_id}/bid")
def bid(game_id: str, req: BidRequest):
    if game_id not in games:
        raise HTTPException(status_code=404, detail="Game not found")
    
    match = games[game_id]
    try:
        match.bid(coinche_engine.Bid(req.value, req.trump))
        auto_play_ai(match)
        return get_game(game_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/game/{game_id}/pass")
def pass_turn(game_id: str):
    if game_id not in games:
        raise HTTPException(status_code=404, detail="Game not found")
    
    match = games[game_id]
    try:
        match.bid(None)
        auto_play_ai(match)
        return get_game(game_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/game/{game_id}/coinche")
def coinche(game_id: str):
    if game_id not in games:
        raise HTTPException(status_code=404, detail="Game not found")
    
    match = games[game_id]
    try:
        match.coinche()
        auto_play_ai(match)
        return get_game(game_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/game/{game_id}/surcoinche")
def surcoinche(game_id: str):
    if game_id not in games:
        raise HTTPException(status_code=404, detail="Game not found")
    
    match = games[game_id]
    try:
        match.surcoinche()
        auto_play_ai(match)
        return get_game(game_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/game/{game_id}/play")
def play_card(game_id: str, req: PlayCardRequest):
    if game_id not in games:
        raise HTTPException(status_code=404, detail="Game not found")
    match = games[game_id]
    
    try:
        match.play_card(req.card_index)
        auto_play_ai(match)
        return get_game(game_id)
    except Exception as e:
         raise HTTPException(status_code=400, detail=str(e))
