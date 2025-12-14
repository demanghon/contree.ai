import coinche_engine
import os
import argparse
import time

def generate_datasets(bidding_samples, gameplay_samples, bidding_file, gameplay_file):
    print(f"Starting data generation...")
    
    # Bidding Data
    if bidding_samples > 0:
        print(f"Generating {bidding_samples} bidding samples to {bidding_file}...")
        start_time = time.time()
        try:
            if os.path.exists(bidding_file):
                os.remove(bidding_file)
            coinche_engine.generate_bidding_data(bidding_file, bidding_samples)
            duration = time.time() - start_time
            print(f"Bidding data generated in {duration:.2f}s. Size: {os.path.getsize(bidding_file)} bytes")
        except Exception as e:
            print(f"Error generating bidding data: {e}")

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
    parser.add_argument("--bidding-output", type=str, default="../../dist/datasets/bidding_data.parquet", help="Output file for bidding data")
    parser.add_argument("--gameplay-output", type=str, default="../../dist/datasets/gameplay_data.parquet", help="Output file for gameplay data")
    args = parser.parse_args()

    bidding_samples = args.bidding_samples
    gameplay_samples = args.gameplay_samples
    bidding_file = args.bidding_output
    gameplay_file = args.gameplay_output
    
    generate_datasets(
        bidding_samples, 
        gameplay_samples, 
        bidding_file, 
        gameplay_file
    )
