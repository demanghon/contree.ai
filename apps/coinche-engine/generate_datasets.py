import os
import argparse
import time
import json
import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

def generate_datasets(bidding_samples, gameplay_samples, bidding_output_dir, gameplay_file, batch_size=1000):
    import coinche_engine
    print(f"Starting data generation...")
    
    # --- BIDDING DATA GENERATION (Crash Resilient) ---
    if bidding_samples > 0:
        os.makedirs(bidding_output_dir, exist_ok=True)
        # Using separate .npy files allows memory mapping (mmap_mode)
        raw_hands_file = os.path.join(bidding_output_dir, "bidding_hands.npy")
        raw_strats_file = os.path.join(bidding_output_dir, "bidding_strategies.npy")
        state_file = os.path.join(bidding_output_dir, "bidding_state.json")
        
        # 1. GENERATE RAW HANDS (if not exists)
        if not os.path.exists(raw_hands_file):
            print(f"Phase 1: Generating {bidding_samples} raw hands...")
            start_time = time.time()
            try:
                # Returns (flattened_hands, strategies)
                hands, strategies = coinche_engine.generate_bidding_hands(bidding_samples)
                
                print("Saving raw hands to numpy files (uncompressed for mmap)...")
                np.save(raw_hands_file, np.array(hands, dtype=np.uint32))
                np.save(raw_strats_file, np.array(strategies, dtype=np.uint8))
                
                duration = time.time() - start_time
                print(f"Phase 1 Complete: Generated {bidding_samples} hands in {duration:.2f}s.")
            except Exception as e:
                print(f"Error generating raw hands: {e}")
                return
        else:
            print(f"Phase 1: Found existing raw hands. Skipping generation.")

        # 2. SOLVE AND SAVE IN BATCHES
        print("Phase 2: Solving hands and saving to Parquet dataset...")
        
        # Load Raw Data with Memory Mapping (Reader from Disk)
        # This ensures we don't load the massive array into RAM, but read pages as needed.
        all_hands = np.load(raw_hands_file, mmap_mode='r')
        all_strategies = np.load(raw_strats_file, mmap_mode='r')
        total_samples = len(all_strategies)
        
        # Load State (Resume Logic)
        processed_count = 0
        if os.path.exists(state_file):
            try:
                with open(state_file, 'r') as f:
                    state = json.load(f)
                    processed_count = state.get('processed_count', 0)
                    print(f"Resuming from offset: {processed_count}")
            except:
                print("Could not load state file, starting from 0")

        if processed_count >= total_samples:
            print("All samples already processed.")
        else:
            strat_map = {0: "Random", 1: "ForceCapot", 2: "ForceBelote", 3: "ForceShape"}
            
            start_time = time.time()
            
            # Divide hands by 4 because flattened array
            # But generate_bidding_hands returns N samples, so hands array len is N*4.
            # We iterate by SAMPLE index, so we need to slice hands array by i*4.
            
            for i in range(processed_count, total_samples, batch_size):
                batch_end = min(i + batch_size, total_samples)
                current_batch_size = batch_end - i
                
                # Slice raw data
                # Hand array is flattened, so stride is 4
                hands_slice = all_hands[i*4 : batch_end*4]
                strat_slice = all_strategies[i : batch_end] # already u8
                
                # Solve using Rust
                # Rust expects List[int], numpy array to list
                # Converting large numpy array to list can be slow. 
                # Ideally we pass numpy buffer, but PyO3 needs specific setup.
                # fast conversion:
                hands_slice_list = hands_slice.tolist()
                
                try:
                    # Returns List[List[int]] (scores per sample)
                    scores_batch = coinche_engine.solve_bidding_batch(hands_slice_list)
                except Exception as e:
                    print(f"Error solving batch {i}: {e}")
                    break
                
                # Prepare PyArrow Table
                # We need to restructure hands back to lists of 4 for storage if desired,
                # Or just store the south hand? 
                # User asked to "generate all hands that we store in the file bidding_hands".
                # But for the final parquet, usually we want feature (hand) -> label (score).
                # The original `bidding.rs` stored ONLY South hand (u32).
                # But `scores` depends on the full deal.
                # If we are training a model for a player, we usually input "My Hand" + "Bidding History".
                # Here we are just generating Double Dummy limits.
                # So saving just South Hand + Scores is typical for "Hand Evaluation" datasets.
                # I will stick to the original schema: Hand (South) + Scores.
                
                # Extract South hands (every 4th element starting at 0)
                # hands_slice is [S1, W1, N1, E1, S2, ...]
                south_hands = hands_slice[0::4]
                
                # Map strategies to strings for better partition names
                strat_names = [strat_map.get(s, "Unknown") for s in strat_slice]
                
                # Create Table
                table = pa.Table.from_pydict({
                    'hand_south': south_hands,
                    'scores': scores_batch,
                    'strategy': strat_names
                })
                
                # Write to Dataset with Partitioning
                pq.write_to_dataset(
                    table,
                    root_path=bidding_output_dir,
                    partition_cols=['strategy'],
                    existing_data_behavior='overwrite_or_ignore'
                )
                
                # Update State
                processed_count = batch_end
                with open(state_file, 'w') as f:
                    json.dump({'processed_count': processed_count}, f)
                    
                # Progress Log
                if i % (batch_size * 5) == 0:
                    elapsed = time.time() - start_time
                    rate = (processed_count - state.get('processed_count', 0) if 'state' in locals() else processed_count) / (elapsed + 0.001)
                    print(f"Processed {processed_count}/{total_samples} ({processed_count/total_samples*100:.1f}%)")

            total_duration = time.time() - start_time
            print(f"Bidding data generation complete. Processed {total_samples} samples in {total_duration:.2f}s.")

    # Gameplay Data
    if gameplay_samples > 0:
        print(f"Generating {gameplay_samples} gameplay samples to {gameplay_file}...")
        start_time = time.time()
        try:
            if os.path.exists(gameplay_file):
                os.remove(gameplay_file)
            coinche_engine.generate_gameplay_data(gameplay_file, gameplay_samples)
            duration = time.time() - start_time
            print(f"Gameplay data generated in {duration:.2f}s. Size: {os.path.getsize(gameplay_file)} bytes")
        except Exception as e:
            print(f"Error generating gameplay data: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate Coinche datasets.")
    parser.add_argument("--bidding-samples", type=int, default=10000, help="Number of bidding samples")
    parser.add_argument("--gameplay-samples", type=int, default=10000, help="Number of gameplay samples")
    parser.add_argument("--bidding-output", type=str, default="../../dist/datasets/bidding_data", help="Output directory for bidding data")
    parser.add_argument("--gameplay-output", type=str, default="../../dist/datasets/gameplay_data.parquet", help="Output file for gameplay data")
    parser.add_argument("--batch-size", type=int, default=10000, help="Batch size for solving")
    parser.add_argument("--threads", type=int, default=None, help="Number of threads to use (limit CPU usage)")
    
    args = parser.parse_args()

    if args.threads is not None and args.threads > 0:
        os.environ["RAYON_NUM_THREADS"] = str(args.threads)
        print(f"Setting RAYON_NUM_THREADS={args.threads}")

    generate_datasets(
        args.bidding_samples, 
        args.gameplay_samples, 
        args.bidding_output, 
        args.gameplay_output,
        args.batch_size
    )
