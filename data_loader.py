import requests
import pandas as pd
from io import StringIO

def fetch_psx(symbol: str) -> pd.DataFrame:
    """
    Fetch PSX historical data for a given symbol by downloading its CSV from the PSX website.
    """
    url = "https://dps.psx.com.pk/historical/download"
    payload = {"symbol": symbol}
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Content-Type": "application/x-www-form-urlencoded",
    }

    response = requests.post(url, data=payload, headers=headers)

    if response.status_code != 200 or "Date" not in response.text:
        raise ValueError(f"Failed to fetch data for symbol: {symbol}")

    df = pd.read_csv(StringIO(response.text))

    # Clean and parse
    df["Date"] = pd.to_datetime(df["Date"], dayfirst=True, errors="coerce")
    df.dropna(subset=["Date"], inplace=True)

    # Ensure correct data types
    for col in ["Open", "High", "Low", "Close", "Volume"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    
    df.dropna(subset=["Open", "Close", "Volume"], inplace=True)

    return df
