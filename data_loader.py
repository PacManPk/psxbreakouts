import pandas as pd
import requests
from io import StringIO
import time

def fetch_psx(symbol: str, retries: int = 3, delay: float = 1.0) -> pd.DataFrame:
    url = "https://dps.psx.com.pk/historical/download"
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    data = {"symbol": symbol.strip().upper()}

    for attempt in range(retries):
        try:
            response = requests.post(url, headers=headers, data=data, timeout=10)
            if response.status_code == 200 and "Date" in response.text:
                df = pd.read_csv(StringIO(response.text))
                df["Date"] = pd.to_datetime(df["Date"], dayfirst=True, errors="coerce")
                df.dropna(subset=["Date"], inplace=True)
                for col in ["Open", "High", "Low", "Close", "Volume"]:
                    if col in df.columns:
                        df[col] = pd.to_numeric(df[col], errors="coerce")
                df.dropna(subset=["Open", "Close", "Volume"], inplace=True)
                return df
        except Exception as e:
            print(f"[RETRY] {symbol} (attempt {attempt + 1}): {e}")
            time.sleep(delay)

    raise RuntimeError(f"Failed to fetch data for symbol: {symbol} after {retries} attempts.")

def list_available_symbols():
    url = "https://docs.google.com/spreadsheets/d/1wGpkG37p2GV4aCckLYdaznQ4FjlQog8E/export?format=csv"
    try:
        df = pd.read_csv(url)
        if "Symbol" in df.columns:
            return df["Symbol"].dropna().unique().tolist()
    except Exception as e:
        print(f"[SYMBOL_LOAD_FAIL] {e}")
    return []
