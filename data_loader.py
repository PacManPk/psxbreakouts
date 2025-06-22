import requests, pandas as pd

def fetch_psx(symbol: str, start_date: str=None, end_date: str=None) -> pd.DataFrame:
    """
    Download historical daily CSV for a given PSX symbol.
    """
    url = "https://dps.psx.com.pk/historical"
    params = {"symbol": symbol}
    if start_date: params["start"] = start_date
    if end_date: params["end"] = end_date
    # PSX may require POST or mimic browser headers; here’s a placeholder GET
    r = requests.get(url, params=params, headers={"User-Agent": "Mozilla/5.0"})
    df = pd.read_html(r.text)[0]
    # Ensure columns: Date, Open, High, Low, Close, Volume
    df['Date'] = pd.to_datetime(df['Date'])
    return df
