import pandas as pd
import requests
from io import StringIO

def fetch_psx(symbol: str) -> pd.DataFrame:
    """
    Fetch stock data from PSX historical page using logic inspired by psx-data-reader.
    """
    url = "https://dps.psx.com.pk/historical/download"
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    data = {"symbol": symbol.strip().upper()}

    try:
        response = requests.post(url, headers=headers, data=data, timeout=10)
        if response.status_code != 200 or "Date" not in response.text:
            raise ValueError(f"No data found for symbol: {symbol}")

        df = pd.read_csv(StringIO(response.text))
        df["Date"] = pd.to_datetime(df["Date"], dayfirst=True, errors="coerce")
        df.dropna(subset=["Date"], inplace=True)

        for col in ["Open", "High", "Low", "Close", "Volume"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        df.dropna(subset=["Open", "Close", "Volume"], inplace=True)
        return df

    except Exception as e:
        raise RuntimeError(f"Error fetching {symbol}: {e}")
