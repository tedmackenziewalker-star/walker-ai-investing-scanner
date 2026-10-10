import pandas as pd
from pathlib import Path

path = Path("scanner_results.csv")

if not path.exists():
    raise SystemExit("No scanner results found. Run scanner.py first.")

df = pd.read_csv(path)
below = df[df["Signal"] == "BELOW"]
above = df[df["Signal"] == "ABOVE"]
stale = df[df["Freshness"] == "STALE"]

print("\n=== WALKER AI — ENGINE 01 HEALTH REPORT ===")
print("Stocks successfully analysed:", len(df))
print("Below 200-week MA:", len(below))
print("Above 200-week MA:", len(above))
print("Stale price records:", len(stale))
print("Earliest data date:", df["Data_Date"].min())
print("Latest data date:", df["Data_Date"].max())

print("\n=== TOP 15 BELOW THE 200-WEEK MA ===")
print(below.head(15)[
    ["Ticker", "Price", "200W_MA", "Distance_%", "Data_Date"]
].to_string(index=False))

if not stale.empty:
    print("\n=== STALE STOCKS ===")
    print(stale[["Ticker", "Data_Date"]].to_string(index=False))

print("\nNOTE: This report includes successful scans only.")
print("Missing files, timeouts and insufficient history")
print("must be tracked separately before production deployment.")
