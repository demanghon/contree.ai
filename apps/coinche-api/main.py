from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import coinche_engine
from typing import Optional, List
import uuid

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory store for active games
games = {}

class CreateGameRequest(BaseModel):
    dealer: int = 0
    # Flattened hands [u32] for 4 players (4 integers)
    hands: Optional[List[int]] = None 

class BidRequest(BaseModel):
    value: int
    trump: int

class PlayCardRequest(BaseModel):
    card: int # 0-31

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
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
        
    return {
        "game_id": game_id, 
        "dealer": match.dealer, 
        "phase": match.phase_name(),
        "hands": match.hands
    }

@app.get("/game/{game_id}")
def get_game(game_id: str):
    if game_id not in games:
        raise HTTPException(status_code=404, detail="Game not found")
    match = games[game_id]
    
    state = {
        "game_id": game_id,
        "phase": match.phase_name(),
        "dealer": match.dealer,
        "hands": match.hands 
    }
    
    if match.phase_name() == "BIDDING":
        bs = match.get_bidding_state()
        if bs:
            state["bidding"] = {
                "history": [(b.value, b.trump) if b else None for b in bs.history],
                "current_player": bs.current_player,
                "contract": (bs.contract.value, bs.contract.trump) if bs.contract else None,
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
                "legal_moves": ps.get_legal_moves()
            }
        
        state["contract"] = (match.contract.value, match.contract.trump) if match.contract else None
        
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
def bid(game_id: str, req: Optional[BidRequest] = None):
    if game_id not in games:
        raise HTTPException(status_code=404, detail="Game not found")
    match = games[game_id]
    
    try:
        if req is None:
            # Pass
            match.bid(None)
        else:
            b = coinche_engine.Bid(req.value, req.trump)
            match.bid(b)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
        
    return get_game(game_id)

@app.post("/game/{game_id}/play")
def play_card(game_id: str, req: PlayCardRequest):
    if game_id not in games:
        raise HTTPException(status_code=404, detail="Game not found")
    match = games[game_id]
    
    try:
        match.play_card(req.card)
    except Exception as e:
         raise HTTPException(status_code=400, detail=str(e))
         
    return get_game(game_id)
