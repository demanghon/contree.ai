import coinche_engine
import os
import pandas as pd

def verify_bidding():
    # Generate enough samples to see the 20% bias significantly
    filename = "../../dist/datasets/bidding_test.parquet"
    num_samples = 20

    print("Generating bidding data verification for {} samples...".format(num_samples))
    
    if os.path.exists(filename):
        os.remove(filename)
    
    coinche_engine.generate_bidding_data(filename, num_samples)
    
    if os.path.exists(filename):
        print(f"File {filename} created. Size: {os.path.getsize(filename)} bytes")
        try:
            df = pd.read_parquet(filename)
            print("Bidding Data Preview:")
            print(df.head())
            
            # Analyze Distribution
            # We need to reconstruct hands to check for biases
            # Hand is u32 bitmap.
            
            capot_count = 0
            belote_count = 0 
            
            # Helper to check if hand has card
            def has_card(hand, suit, rank):
                return (hand & (1 << (suit * 8 + rank))) != 0

            # Iterate through a sample
            for hand in df['hand_south']:
                # Check Belote (K+Q of any suit - strictly we bias for Trump Belote, but here we don't know trump)
                # Actually, the generator forces K+Q of the *target* trump.
                # So we should see a high prevalence of K+Q pairs in *some* suit.
                
                has_any_belote = False
                for s in range(4):
                    if has_card(hand, s, 5) and has_card(hand, s, 6): # Q=5, K=6
                        has_any_belote = True
                        break
                if has_any_belote:
                    belote_count += 1
                    
                # Check Capot (Top 5 trumps: J,9,A,10,K)
                # J=4, 9=2, A=7, 10=3, K=6
                has_any_capot = False
                for s in range(4):
                    if (has_card(hand, s, 4) and has_card(hand, s, 2) and 
                        has_card(hand, s, 7) and has_card(hand, s, 3) and 
                        has_card(hand, s, 6)):
                        has_any_capot = True
                        break
                if has_any_capot:
                    capot_count += 1

            print(f"\nDistribution Analysis (N={num_samples}):")
            print(f"Hands with Belote (K+Q): {belote_count} ({belote_count/num_samples*100:.1f}%) [Expected ~20%+]")
            print(f"Hands with Capot Base (J-9-A-10-K): {capot_count} ({capot_count/num_samples*100:.1f}%) [Expected ~20%]")
            
        except Exception as e:
            print(f"Error reading parquet: {e}")
            import traceback
            traceback.print_exc()
    else:
        print(f"File {filename} NOT created.")

def verify_gameplay():
    print("\nGenerating gameplay data...")
    filename = "../../dist/datasets/gameplay_test.parquet"
    if os.path.exists(filename):
        os.remove(filename)
    
    coinche_engine.generate_gameplay_data(filename, 10)
    
    if os.path.exists(filename):
        print(f"File {filename} created. Size: {os.path.getsize(filename)} bytes")
        try:
            df = pd.read_parquet(filename)
            print("Gameplay Data Preview:")
            print(df.head())
            print("Columns:", df.columns)
            print("Shape:", df.shape)
        except Exception as e:
            print(f"Error reading parquet: {e}")
    else:
        print(f"File {filename} NOT created.")

if __name__ == "__main__":
    verify_bidding()
    # verify_gameplay()
