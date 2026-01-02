
import argparse
import torch
from torch.utils.tensorboard import SummaryWriter
import os
from tqdm import tqdm
import time


import agent
from agent import load_agent
from tournament import TournamentEngine, Team

def main():
    parser = argparse.ArgumentParser(description="Coinche Model Comparator (Duplicate Tournament)")
    
    # Team A Models
    parser.add_argument("--team_a_bidding", type=str, required=True, help="Path to Team A Bidding Model (or 'heuristic', 'random')")
    parser.add_argument("--team_a_playing", type=str, required=True, help="Path to Team A Playing Model (or 'heuristic', 'random')")
    parser.add_argument("--team_a_name", type=str, default="Team_A_Baseline", help="Name of Team A")
    
    # Team B Models
    parser.add_argument("--team_b_bidding", type=str, required=True, help="Path to Team B Bidding Model (or 'heuristic', 'random')")
    parser.add_argument("--team_b_playing", type=str, required=True, help="Path to Team B Playing Model (or 'heuristic', 'random')")
    parser.add_argument("--team_b_name", type=str, default="Team_B_Challenger", help="Name of Team B")
    
    # Tournament Settings
    parser.add_argument("--nb_games", type=int, default=1000, help="Number of duplicate hands to play")
    parser.add_argument("--device", type=str, default="cpu", help="Device (cpu/cuda)")
    parser.add_argument("--log_dir", type=str, default="runs/tournament", help="TensorBoard log dir")
    
    args = parser.parse_args()
    
    device = torch.device(args.device)
    log_dir = os.path.join(args.log_dir, f"{args.team_a_name}_vs_{args.team_b_name}_{int(time.time())}")
    writer = SummaryWriter(log_dir=log_dir)
    print(f"Logging tournament to {log_dir}")
    
    # Initialize Agents
    print("Loading Team A Agents...")
    agent_a = load_agent(args.team_a_bidding, args.team_a_playing, device, name=args.team_a_name)
    team_a = Team(args.team_a_name, agent_a)
    
    print("Loading Team B Agents...")
    agent_b = load_agent(args.team_b_bidding, args.team_b_playing, device, name=args.team_b_name)
    team_b = Team(args.team_b_name, agent_b)
    
    # Initialize Engine
    engine = TournamentEngine(team_a, team_b)
    
    # Determine which is 'Baseline' (Heuristic) for Margin Metric
    baseline_team = None
    if isinstance(agent_a, agent.HeuristicAgent):
        baseline_team = 'A'
    elif isinstance(agent_b, agent.HeuristicAgent):
        baseline_team = 'B'
        
    # Note: load_agent returns instance. Check type requires importing classes or checking name?
    # Actually load_agent returns HeuristicAgent instance. 'agent' module needs to be imported fully to check instance, 
    # but we only imported load_agent. Let's assume if name or path contains 'heuristic'.
    
    is_heuristic_a = args.team_a_bidding.lower() == 'heuristic'
    is_heuristic_b = args.team_b_bidding.lower() == 'heuristic'
    
    print(f"Starting Tournament: {args.nb_games} Hands (Duplicate format)...")
    
    for i in tqdm(range(args.nb_games)):
        res = engine.play_duplicate_hand()
        
        # Log basic metrics per hand
        step = i + 1
        
        relative_score = res['relative_score_b'] # (Score B - Score A)
        
        writer.add_scalar('Score/Relative_Diff_Per_Hand', relative_score, step)
        writer.add_scalar('Score/Total_Team_A', engine.metrics.team_a_score, step)
        writer.add_scalar('Score/Total_Team_B', engine.metrics.team_b_score, step)
        
        # Histogram of relative scores (Stability)
        if step % 50 == 0:
            writer.add_histogram('Distribution/Relative_Score_Diff', 
                                 torch.tensor(engine.metrics.relative_points), step)
        
        # Baseline Margin Metric
        # If A is heuristic, Margin = B_Score - A_Score (which is relative_score).
        # If B is heuristic, Margin = A_Score - B_Score (which is -relative_score).
        if is_heuristic_a:
             # A is baseline. How much better is B?
             writer.add_scalar('Tournament/Baseline_Margin', relative_score, step)
        elif is_heuristic_b:
             # B is baseline. How much better is A?
             writer.add_scalar('Tournament/Baseline_Margin', -relative_score, step)
             
        # --- Advanced Metrics (Cumulative) ---
        if engine.metrics.games_played > 0:
            # Win Rate
            wr_a = engine.metrics.team_a_wins / engine.metrics.games_played
            wr_b = engine.metrics.team_b_wins / engine.metrics.games_played
            writer.add_scalar('Performance/WinRate_A', wr_a, step)
            writer.add_scalar('Performance/WinRate_B', wr_b, step)
            
            # Helper for Bidding Stats
            def log_bidding_stats(stats, prefix):
                taken = stats['taken']
                if taken > 0:
                    success_rate = stats['made'] / taken
                    avg_value = stats['total_value'] / taken
                    writer.add_scalar(f'{prefix}/SuccessRate', success_rate, step)
                    writer.add_scalar(f'{prefix}/AvgContractValue', avg_value, step)
            
            log_bidding_stats(engine.metrics.team_a_bidding_stats, 'Bidding/Team_A')
            log_bidding_stats(engine.metrics.team_b_bidding_stats, 'Bidding/Team_B')
            
            # Helper for Defense Stats
            def log_defense_stats(stats, prefix):
                count = stats['count']
                if count > 0:
                    avg_score = stats['score'] / count
                    writer.add_scalar(f'{prefix}/AvgDefenseScore', avg_score, step)
            
            log_defense_stats(engine.metrics.team_a_defense_stats, 'Defense/Team_A')
            log_defense_stats(engine.metrics.team_b_defense_stats, 'Defense/Team_B')

    # Final Review
    total_games = args.nb_games * 2 # 2 games per hand
    
    avg_a = engine.metrics.team_a_score / total_games
    avg_b = engine.metrics.team_b_score / total_games
    
    print("\n" + "="*30)
    print(" TOURNAMENT RESULTS ")
    print("="*30)
    print(f"Team A ({args.team_a_name}): {engine.metrics.team_a_score} pts (Avg: {avg_a:.2f})")
    print(f"Team B ({args.team_b_name}): {engine.metrics.team_b_score} pts (Avg: {avg_b:.2f})")
    print("-" * 30)
    diff = engine.metrics.team_b_score - engine.metrics.team_a_score
    print(f"Net Difference (B - A): {diff} pts")
    if diff > 0:
        print(f"WINNER: {args.team_b_name}")
    elif diff < 0:
        print(f"WINNER: {args.team_a_name}")
    else:
        print("DRAW")
    print("="*30 + "\n")
    
    # Final Stats
    wr_a = engine.metrics.team_a_wins / total_games
    wr_b = engine.metrics.team_b_wins / total_games
    
    def get_bid_stats(stats):
        taken = stats['taken']
        if taken == 0: return "N/A"
        succ = (stats['made'] / taken) * 100
        avg = stats['total_value'] / taken
        return f"{taken} contracts (Succ: {succ:.1f}%, AvgVal: {avg:.1f})"
        
    def get_def_stats(stats):
        count = stats['count']
        if count == 0: return "N/A"
        avg = stats['score'] / count
        return f"{avg:.1f} pts/game ({count} games)"

    # Log Final Text Summary
    summary_text = f"### Tournament Results\n\n" \
                   f"**{args.team_a_name}** vs **{args.team_b_name}**\n\n" \
                   f"- **Hands Played**: {args.nb_games} (Duplicate, {total_games} games total)\n" \
                   f"- **Net Diff (B-A)**: {diff} pts\n\n" \
                   f"#### Team A Stats:\n" \
                   f"- Score: {engine.metrics.team_a_score} (Avg: {avg_a:.2f})\n" \
                   f"- Win Rate: {wr_a:.1%}\n" \
                   f"- Bidding: {get_bid_stats(engine.metrics.team_a_bidding_stats)}\n" \
                   f"- Defense: {get_def_stats(engine.metrics.team_a_defense_stats)}\n\n" \
                   f"#### Team B Stats:\n" \
                   f"- Score: {engine.metrics.team_b_score} (Avg: {avg_b:.2f})\n" \
                   f"- Win Rate: {wr_b:.1%}\n" \
                   f"- Bidding: {get_bid_stats(engine.metrics.team_b_bidding_stats)}\n" \
                   f"- Defense: {get_def_stats(engine.metrics.team_b_defense_stats)}\n"
    writer.add_text("Final_Results", summary_text, 0)
    print(summary_text)
    
    writer.flush()
    writer.close()

if __name__ == "__main__":
    main()
