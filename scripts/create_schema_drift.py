from pathlib import Path
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_FILE = PROJECT_ROOT / "data" / "raw" / "customers.csv"

df = pd.read_csv(RAW_FILE)

df["customer_segment"] = ["PREMIUM", "STANDARD", "PREMIUM", "STANDARD", "PREMIUM"]

df.to_csv(RAW_FILE, index=False)

print(f"Updated source: {RAW_FILE}")
print(f"Records: {len(df)}")
print("Columns:")
print(list(df.columns))
print()
print(df.to_string(index=False))
print()
print("SCHEMA DRIFT SCENARIO CREATED")
