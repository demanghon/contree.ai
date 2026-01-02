import os
import sys
import argparse
import time
import json
import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

def generate_datasets(bidding_samples, gameplay_samples, bidding_output_dir, gameplay_file, batch_size=1000, pimc_iterations=0):
    import coinche_engine
    print(f"Starting data generation (PIMC={pimc_iterations})...")
    
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
                    scores_batch = coinche_engine.solve_bidding_batch(hands_slice_list, pimc_iterations)
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
                # Define Schema explicitly for float scores (User Requirement: Target continue)
                # scores_batch contains floats from Rust engine
                
                # We cast scores_batch to ensure PyArrow respects float32 (not double) to save space/match ML types
                # Using explicit schema is best.
                score_type = pa.list_(pa.float32())
                schema = pa.schema([
                    ('hand_south', pa.uint32()),
                    ('scores', score_type),
                    ('strategy', pa.string())
                ])

                table = pa.Table.from_pydict({
                    'hand_south': south_hands,
                    'scores': scores_batch,
                    'strategy': strat_names
                }, schema=schema)
                
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
            
            # Merge partitions into single file
            base_merged_file = bidding_output_dir.rstrip('/') + ".parquet"
            merged_file = base_merged_file
            counter = 1
            while os.path.exists(merged_file):
                root, ext = os.path.splitext(base_merged_file)
                merged_file = f"{root}_{counter}{ext}"
                counter += 1
                
            print(f"Merging partitions to {merged_file}...")
            try:
                # We need to manually collecting files because ParquetDataset might choke on npy files in the same dir
                # similar to what we did in the merge script
                parquet_files = []
                for root, dirs, files in os.walk(bidding_output_dir):
                    for file in files:
                        if file.endswith(".parquet"):
                            parquet_files.append(os.path.join(root, file))
                            
                if parquet_files:
                    dataset = pq.ParquetDataset(parquet_files)
                    table = dataset.read()
                    pq.write_table(table, merged_file)
                    print(f"Merge complete: {merged_file}")
                else:
                    print("No parquet files found to merge.")
            except Exception as e:
                print(f"Error merging bidding data: {e}")

    # --- GAMEPLAY DATA GENERATION (Crash Resilient) ---
    if gameplay_samples > 0:
        # We need a directory for intermediate and final files if we want resume capability
        gameplay_dir = os.path.dirname(gameplay_file)
        if not gameplay_dir:
            gameplay_dir = "."
        os.makedirs(gameplay_dir, exist_ok=True)
        
        # Intermediate raw files
        raw_hands_file = os.path.join(gameplay_dir, "raw_gameplay_hands.npy")
        raw_boards_file = os.path.join(gameplay_dir, "raw_gameplay_boards.npy") # flattened or pickled?
        # Boards are variable length. Let's use two files: values and offsets, or just pickle.
        # Numpy object array is easy but not mmap-able.
        # Let's use specific npy files for fixed size cols and a separate strategy for boards.
        # Simple approach: Save everything to a temporary Parquet file? 
        # But we want to iterate it efficiently. Parquet IS efficient.
        intermediate_file = os.path.join(gameplay_dir, "raw_gameplay_intermediate.parquet")
        
        gameplay_state_file = os.path.join(gameplay_dir, "gameplay_state.json")

        # 1. GENERATE RAW STATES
        if not os.path.exists(intermediate_file):
            print(f"Phase 1: Generating {gameplay_samples} raw gameplay states...")
            start_time = time.time()
            try:
                # Returns (hands [flat], boards [list], history, trumps, tricks_won, players)
                hands, boards, history, trumps, tricks_won, players = coinche_engine.generate_raw_gameplay_batch(gameplay_samples)
                
                # Convert to PyArrow Table
                # Hands need to be stored as list of 4? No, flat in Rust, but here we can structuralize them.
                # Let's store them as FixedSizeList? Or just keep flattened and reshape on read?
                # PyArrow Table is cleaner.
                
                # Reshape hands to [N, 4]
                hands_np = np.array(hands, dtype=np.uint32).reshape(-1, 4)
                
                # Boards: List[List[uint8]]
                # PyArrow handles list of lists naturally
                
                # Tricks won: [N, 2]
                tricks_won_np = np.array(tricks_won, dtype=np.uint8) # already list of list
                
                table = pa.Table.from_pydict({
                    'hands': list(hands_np), # List of Arrays
                    'board': boards,
                    'history': history,
                    'trump': trumps,
                    'tricks_won': list(tricks_won_np),
                    'player': players
                })
                
                print(f"Saving raw states to {intermediate_file}...")
                pq.write_table(table, intermediate_file)
                
                duration = time.time() - start_time
                print(f"Phase 1 Complete: Generated {gameplay_samples} states in {duration:.2f}s.")
            except Exception as e:
                print(f"Error generating raw gameplay states: {e}")
                import traceback
                traceback.print_exc()
                return
        else:
             print(f"Phase 1: Found existing raw states at {intermediate_file}. Skipping generation.")

        # 2. SOLVE AND SAVE
        print("Phase 2: Solving gameplay states...")
        
        # Read intermediate data
        # We can use ParquetFile to read row groups
        raw_dataset = pq.ParquetFile(intermediate_file)
        total_rows = raw_dataset.metadata.num_rows
        
        # Load State
        processed_count = 0
        if os.path.exists(gameplay_state_file):
            try:
                with open(gameplay_state_file, 'r') as f:
                    state = json.load(f)
                    processed_count = state.get('processed_count', 0)
                    print(f"Resuming from offset: {processed_count}")
            except:
                print("Could not load state file, starting from 0")

        if processed_count >= total_rows:
            print("All samples already processed.")
        else:
            start_time = time.time()
            
            # We iterate by batch_size
            # ParquetFile.iter_batches is good
            # But we need random access to skip 'processed_count'.
            # iter_batches doesn't support skip easily.
            # So we iterate and discard, or read specific row groups if batch_size aligns with row format.
            # Simplest for now: iter_batches and just skip loop counter? 
            # Or just read table slice. Reading slice is okay if dataset fits in memory?
            # 1M rows * 100 bytes = 100MB. It fits in memory easily.
            # So let's read the whole raw table (it's 100x smaller than the generated Bidding trees).
            
            # If dataset is HUGE (10M+), this might be an issue, but for <10M it's fine.
            full_table = raw_dataset.read()
            
            # Calculate total batches
            total_batches = (total_rows + batch_size - 1) // batch_size
            start_batch = processed_count // batch_size
            
            from tqdm import tqdm
            for i in tqdm(range(processed_count, total_rows, batch_size), initial=start_batch, total=total_batches, desc="Phase 2 Solving"):
                batch_end = min(i + batch_size, total_rows)
                
                batch = full_table.slice(i, batch_end - i)
                
                # Prepare inputs for Rust
                # Hands: Needs to be flattened Vec<u32>
                # Batch['hands'] is List<FixedSizeList<u32>[4]>.
                # We need to flatten it.
                hands_col = batch['hands'].to_pylist() # List[List[u32]]
                # flatten
                hands_flat = [h for sub in hands_col for h in sub]
                
                boards_col = batch['board'].to_pylist()
                history_col = batch['history'].to_pylist()
                trumps_col = batch['trump'].to_pylist()
                tricks_won_col = batch['tricks_won'].to_pylist()
                players_col = batch['player'].to_pylist()
                
                try:
                    # Call Rust Solver
                    best_cards, best_scores, valid_mask = coinche_engine.solve_gameplay_batch(
                        hands_flat,
                        boards_col,
                        history_col,
                        trumps_col,
                        tricks_won_col,
                        players_col,
                        pimc_iterations
                    )
                    
                    # Filter invalid results (forced moves etc)
                    # We need to reconstruct the rows that are valid
                    # Python list filtering is slow? 
                    # Use PyArrow filtering or list comprehension.
                    
                    valid_indices = [idx for idx, v in enumerate(valid_mask) if v]
                    
                    if not valid_indices:
                        continue
                        
                    # Filter inputs to save (User wants: Hand, Board, History, Trump + Label)
                    # NOTE: Only save "My Hand" (the current player's hand) for the final dataset?
                    # The `gameplay.rs` original writer saved only `hand` (u32).
                    # Let's extract My Hand from the hands list.
                    # hands_col[idx] is [H0, H1, H2, H3]. Player is players_col[idx].
                    
                    final_hands = []
                    final_boards = []
                    final_history = []
                    final_trumps = []
                    final_cards = []
                    final_scores = []
                    
                    for idx in valid_indices:
                         player = players_col[idx]
                         my_hand = hands_col[idx][player]
                         
                         final_hands.append(my_hand)
                         final_boards.append(boards_col[idx])
                         final_history.append(history_col[idx])
                         final_trumps.append(trumps_col[idx])
                         final_cards.append(best_cards[idx])
                         final_scores.append(best_scores[idx])
                         
                    # Create Batch Table
                    out_table = pa.Table.from_pydict({
                        'hand': final_hands,
                        'board': final_boards,
                        'history': final_history,
                        'trump': final_trumps,
                        'best_card': final_cards,
                        'best_score': final_scores
                    })
                    
                    # Write to Output File (Append mode?)
                    # Parquet doesn't support random append easily to single file without some trickery.
                    # `write_to_dataset` creates folders.
                    # If user wants a SINGLE file `gameplay.parquet`, we have to append row groups.
                    # `pq.ParquetWriter` supports this.
                    
                    # Check if writer exists or needs creation
                    writer_mode = 'a' if i > 0 or processed_count > 0 else 'w' 
                    # Actually ParquetWriter logic is: Open file, write batch, keep open.
                    
                    # Since we are in a loop, we should open the writer ONCE outside loop?
                    # But we might be resuming.
                    # If resuming, we need to append.
                    # Appending to Parquet is tricky. 
                    # Easier solution: Write one parquet file PER BATCH, then merge later?
                    # Or use `write_to_dataset` with a dummy partition?
                    
                    # Let's use the partitioned approach because it is robust, then merge if needed.
                    # Or just write `part-{i}.parquet`.
                    
                    part_file = os.path.join(gameplay_dir, "gameplay_parts", f"part_{i}.parquet")
                    os.makedirs(os.path.dirname(part_file), exist_ok=True)
                    pq.write_table(out_table, part_file)
                    
                except Exception as e:
                    print(f"Error solving batch {i}: {e}")
                    import traceback
                    traceback.print_exc()
                    break

                # Update State
                processed_count = batch_end
                with open(gameplay_state_file, 'w') as f:
                    json.dump({'processed_count': processed_count}, f)

            total_duration = time.time() - start_time
            print(f"Gameplay generation complete. Parts saved in {os.path.join(gameplay_dir, 'gameplay_parts')}")
            
            # Optional: Merge parts into final file?
            # User specified `gameplay_output` (e.g. gameplay.parquet).
            # We can merge them now.
            
            # Secure filename
            base_gameplay_file = gameplay_file
            final_gameplay_file = base_gameplay_file
            counter = 1
            while os.path.exists(final_gameplay_file):
                root, ext = os.path.splitext(base_gameplay_file)
                final_gameplay_file = f"{root}_{counter}{ext}"
                counter += 1

            print(f"Merging parts to {final_gameplay_file}...")
            try:
                parts_dir = os.path.join(gameplay_dir, "gameplay_parts")
                if os.path.exists(parts_dir):
                    dataset = pq.ParquetDataset(parts_dir)
                    merged_table = dataset.read()
                    pq.write_table(merged_table, final_gameplay_file)
                    print(f"Merge complete: {final_gameplay_file}")
                    # Optional: Cleanup parts?
                    # shutil.rmtree(parts_dir)
            except Exception as e:
                print(f"Error merging: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate Coinche datasets.")
    parser.add_argument("--bidding-samples", type=int, default=10000, help="Number of bidding samples")
    parser.add_argument("--gameplay-samples", type=int, default=10000, help="Number of gameplay samples")
    parser.add_argument("--bidding-output", type=str, default="../../dist/datasets/bidding_data", help="Output directory for bidding data")
    parser.add_argument("--gameplay-output", type=str, default="../../dist/datasets/gameplay_data.parquet", help="Output file for gameplay data")
    parser.add_argument("--batch-size", type=int, default=10000, help="Batch size for solving")
    parser.add_argument("--threads", type=int, default=None, help="Number of threads to use (limit CPU usage)")
    parser.add_argument("--pimc", type=int, default=0, help="Number of PIMC iterations per hand (Bidding & Gameplay). 0 = Double Dummy.")
    
    args = parser.parse_args()

    if args.threads is not None and args.threads > 0:
        os.environ["RAYON_NUM_THREADS"] = str(args.threads)
        print(f"Setting RAYON_NUM_THREADS={args.threads}")

    try:
        generate_datasets(
            args.bidding_samples, 
            args.gameplay_samples, 
            args.bidding_output, 
            args.gameplay_output,
            args.batch_size,
            args.pimc
        )
    except KeyboardInterrupt:
        print("\n\n⚠️ Generation interrupted by user.")
        print("✅ Progress has been saved. Run the command again to resume.")
        try:
            sys.exit(0)
        except SystemExit:
            os._exit(0)
