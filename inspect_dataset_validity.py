
import pandas as pd

def count_bits(n):
    return bin(n).count('1')

try:
    print("Reading dataset/simple_bidding_dataset.parquet...")
    df = pd.read_parquet("dataset/simple_bidding_dataset.parquet")
    
    total_samples = len(df)
    print(f"Total samples: {total_samples}")
    
    invalid_count = 0
    hands = df['hand_south']
    
    for i, hand in enumerate(hands):
        c = count_bits(hand)
        if c != 8:
            invalid_count += 1
            if invalid_count <= 5: # Print first few errors
                print(f"Sample {i}: Hand has {c} cards (Expected 8)")
                
    print(f"\nFound {invalid_count} invalid hands out of {total_samples}")
    print(f"Corruption rate: {invalid_count/total_samples*100:.2f}%")

except Exception as e:
    print(f"Error: {e}")
