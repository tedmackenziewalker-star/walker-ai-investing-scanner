import requests
import pandas as pd
from io import StringIO
from datetime import datetime, timezone

BASE = "https://" + "raw.githubusercontent.com"
REPO = "zjplab/US-Trading-Data"
FOLDER = "data/SP500"
# Discover stock files automatically from GitHub.
listing_url = "https://" + "api.github.com/repos/zjplab/US-Trading-Data/contents/data/SP500"
listing = requests.get(listing_url, timeout=30)
listing.raise_for_status()
TICKERS = sorted(
    item["name"][:-4]
    for item in listing.json()
    if item["name"].endswith(".csv")
)
# Verify membership before starting the scan.
wiki_url = "https://" + "en.wikipedia.org/wiki/List_of_S%26P_500_companies"
wiki_response = requests.get(
    wiki_url,
    headers={"User-Agent": "WalkerAIInvestingResearch/1.0"},
    timeout=30
)
wiki_response.raise_for_status()

official_tables = pd.read_html(StringIO(wiki_response.text))
official_table = next(
    t for t in official_tables if "Symbol" in t.columns
)
official = set(
    official_table["Symbol"].astype(str).str.replace(
        ".", "-", regex=False
    )
)
available = set(TICKERS)

missing = sorted(official - available)
extra = sorted(available - official)

if missing or extra:
    print("Missing from price source:", missing)
    print("Not in reference index:", extra)
    raise SystemExit("MEMBERSHIP CHECK FAILED. Scan stopped.")

print(f"Membership verified: {len(official)} tickers.")

# Reuse one connection pool for the entire scan.
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

session = requests.Session()
retry = Retry(
    total=3,
    connect=3,
    read=3,
    backoff_factor=1,
    status_forcelist=[429, 500, 502, 503, 504]
)
session.mount("https://", HTTPAdapter(max_retries=retry))

results = []
failures = []

for ticker in TICKERS:
    try:
        url = f"{BASE}/{REPO}/main/{FOLDER}/{ticker}.csv"
        r = session.get(url, timeout=30)
        r.raise_for_status()

        df = pd.read_csv(StringIO(r.text))
        df["Date"] = pd.to_datetime(df["Date"], utc=True)
        df = df.sort_values("Date").set_index("Date")

        if not df.index.is_unique:
            df = df[~df.index.duplicated(keep="last")]

        df["Close"] = pd.to_numeric(df["Close"], errors="coerce")
        df = df.dropna(subset=["Close"])

        # Convert timestamps to US market calendar dates.
        dates = df.index.tz_convert("America/New_York")
        df.index = pd.DatetimeIndex(dates.date)

        latest_date = df.index[-1]
        latest_price = float(df["Close"].iloc[-1])

        # Only include weeks whose Friday has passed in the data.
        weekly = df["Close"].resample("W-FRI").last().dropna()
        # Include only weeks that have fully ended.
        # The most recent Friday is complete only after Friday's US close.
        from datetime import timedelta
        last_friday = latest_date - timedelta(days=(latest_date.weekday() - 4) % 7)
        weekly = weekly[weekly.index <= pd.Timestamp(last_friday)]

        if len(weekly) < 200:
            failures.append({"Ticker": ticker, "Reason": "Insufficient history"})
            print(f"{ticker}: insufficient weekly history")
            continue

        ma200 = float(weekly.tail(200).mean())
        distance = (latest_price / ma200 - 1) * 100

        age = (datetime.now(timezone.utc).date() - latest_date.date()).days
        freshness = "STALE" if age > 5 else "OK"

        results.append({
            "Ticker": ticker,
            "Price": round(latest_price, 2),
            "200W_MA": round(ma200, 2),
            "Distance_%": round(distance, 2),
            "Signal": "BELOW" if distance < 0 else "ABOVE",
            "Data_Date": str(latest_date),
            "Freshness": freshness
        })
        print(f"{ticker}: completed")

    except Exception as e:
        failures.append({"Ticker": ticker, "Reason": str(e)})
        print(f"{ticker}: ERROR - {e}")

if results:
    output = pd.DataFrame(results)
    output = output.sort_values("Distance_%")
    output.to_csv("scanner_results.csv", index=False)

    print("\n=== WALKER AI INVESTING — ENGINE 01 ===")
    print(output.to_string(index=False))
    print("\nSaved to scanner_results.csv")
    print(f"Stocks successfully scanned: {len(output)}/{len(TICKERS)}")
else:
    print("No stocks processed successfully.")


# Save failures on every run, including when there are none.
pd.DataFrame(failures, columns=["Ticker", "Reason"]).to_csv(
    "scanner_failures.csv", index=False
)
print(f"Stocks excluded or failed: {len(failures)}")
print("Failure log saved to scanner_failures.csv")
