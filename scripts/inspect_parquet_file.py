
import pandas as pd
import sys
import os

def inspect_parquet(file_path):
    if not os.path.exists(file_path):
        print(f"Error: File not found at {file_path}")
        return

    try:
        df = pd.read_parquet(file_path)
        print(f"--- Inspecting: {file_path} ---")
        print(f"Shape: {df.shape}")
        print("\nColumns:")
        print(df.columns.tolist())
        print("\nFirst 3 rows:")
        print(df.head(3))
        
        print("\nData Types:")
        print(df.dtypes)
        
    except Exception as e:
        print(f"Failed to read parquet file: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python inspect_parquet_file.py <path_to_parquet_file>")
    else:
        inspect_parquet(sys.argv[1])
