import argparse
import os
import sys
import pyarrow.parquet as pq
import pyarrow as pa

def merge_parquet_files(filename):
    # Define paths
    # Assuming script is run from root or we find the path relative to script
    # User instruction implies running from root or similar, but let's make it robust
    # Script is in scripts/, so up one level is root
    script_dir = os.path.dirname(os.path.abspath(__file__))
    root_dir = os.path.dirname(script_dir)
    
    source_dir = os.path.join(root_dir, "dist", "datasets", "bidding_data")
    dest_dir = os.path.join(root_dir, "dataset")
    
    # Ensure filename ends with .parquet
    if not filename.endswith('.parquet'):
        filename += '.parquet'
        
    output_path = os.path.join(dest_dir, filename)

    # Check source
    if not os.path.exists(source_dir):
        print(f"Error: Source directory '{source_dir}' does not exist.")
        sys.exit(1)

    # Check overwrite
    if os.path.exists(output_path):
        print(f"Error: Output file '{output_path}' already exists. Overwriting is not allowed.")
        sys.exit(1)

    # Ensure destination directory exists
    os.makedirs(dest_dir, exist_ok=True)

    print(f"Reading parquet dataset from {source_dir}...")
    try:
        # Manually find all .parquet files to avoid reading .npy or .json files
        parquet_files = []
        for root, dirs, files in os.walk(source_dir):
            for file in files:
                if file.endswith(".parquet"):
                    parquet_files.append(os.path.join(root, file))
        
        if not parquet_files:
            print("No .parquet files found in the source directory.")
            sys.exit(1)

        # Read the dataset using the list of files
        dataset = pq.ParquetDataset(parquet_files)
        table = dataset.read()
        
        print(f"Read {table.num_rows} rows.")
        
        print(f"Writing merged data to {output_path}...")
        pq.write_table(table, output_path)
        
        print("Success!")
        
    except Exception as e:
        print(f"Error processing parquet files: {e}")
        sys.exit(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Merge bidding data parquet files into a single file.")
    parser.add_argument("filename", help="The name of the output file (e.g., merged_bidding.parquet)")
    
    args = parser.parse_args()
    
    merge_parquet_files(args.filename)
