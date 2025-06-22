import requests
import pandas as pd
from io import StringIO

def fetch_psx(symbol: str) -> pd.DataFrame:
    url = "https://dps.psx.com.pk/historical/download"
    payload = {"symbol": symbol}
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Content-Type": "application/x-www-form-urlencoded",
    }

    r = requests.post(url, data=payload, headers=headers)
    
    if r.status_code != 200 or "Date" not in r.text:
        raise ValueError(f"No data received for symbol {symbol}")

    df = pd.read_csv(StringIO(r.text))
    df['Date'] = pd.to_datetime(df['Date'], dayfirst=True, errors='coerce')
    df.dropna(subset=["Date"], inplace=True)
    return df
