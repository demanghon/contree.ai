
import pandas as pd

try:
    df = pd.read_parquet("dataset/simple_bidding_dataset.parquet")
    print("Columns:", df.columns.tolist())
    print("\nFirst row:")
    print(df.iloc[0])
    print("\nInput Shapes:")
    for col in df.columns:
        val = df.iloc[0][col]
        if hasattr(val, '__len__') and not isinstance(val, str):
             print(f"{col}: len={len(val)}")
        else:
             print(f"{col}: scalar")
             
except Exception as e:
    print(e)
