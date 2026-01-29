import pandas as pd

try:
    df = pd.read_excel("RegAlum.xls", header=None)
    print("Row 4 (Index 3):", df.iloc[3].values)
    print("Row 5 (Index 4):", df.iloc[4].values)
    print("Row 6 (Index 5):", df.iloc[5].values)
except Exception as e:
    print(f"Error reading Excel: {e}")
