import pandas as pd
from fastapi import FastAPI
import gradio as gr
from datetime import datetime
from bs4 import BeautifulSoup
import requests
from pytz import timezone
from io import StringIO
import os

# --- CONFIGURATION ---
PSX_HISTORICAL_URL = "https://dps.psx.com.pk/historical"
PSX_STOCK_DATA_URL = "https://docs.google.com/spreadsheets/d/1wGpkG37p2GV4aCckLYdaznQ4FjlQog8E/export?format=csv"
SHARIAH_PATH = "data/shariah_list.txt"
HEADERS = {
    'User-Agent': 'Mozilla/5.0',
    'Content-Type': 'application/x-www-form-urlencoded'
}

# --- FASTAPI APP ---
app = FastAPI()

# --- FUNCTIONS ---
def debug_print(msg, important=False):
    if important:
        print(f"[{datetime.now(timezone('Asia/Karachi')).strftime('%H:%M:%S')}] 🔵 {msg}")

def safe_float_convert(value, default=0.0):
    if pd.isna(value) or value in ('', '-', 'N/A', None):
        return default
    try:
        return float(str(value).replace(',', '').strip())
    except:
        return default

@app.get("/data")
def fetch_market_data():
    date = datetime.now()

    try:
        # Load symbols from Google Sheet
        response = requests.get(PSX_STOCK_DATA_URL, timeout=30)
        psx_symbols_df = pd.read_csv(StringIO(response.text))
        symbol_set = set(psx_symbols_df['Symbol'].dropna().str.strip().str.upper())

        # Fetch PSX HTML table
        date_str = date.strftime('%Y-%m-%d')
        response = requests.post(
            PSX_HISTORICAL_URL,
            data={'date': date_str},
            headers=HEADERS,
            timeout=30
        )
        soup = BeautifulSoup(response.text, 'html.parser')
        table = soup.find('table')
        rows = table.find_all('tr') if table else []

        data = []
        for row in rows[1:]:
            cells = [cell.text.strip() for cell in row.find_all('td')]
            if len(cells) >= 9:
                try:
                    data.append([
                        cells[0].upper(),
                        safe_float_convert(cells[1]),
                        safe_float_convert(cells[2]),
                        safe_float_convert(cells[3]),
                        safe_float_convert(cells[4]),
                        safe_float_convert(cells[5]),
                        int(cells[8].replace(',', '')) if cells[8] != '-' else 0
                    ])
                except:
                    continue

        df = pd.DataFrame(data, columns=['SYMBOL', 'LDCP', 'OPEN', 'HIGH', 'LOW', 'CLOSE', 'VOLUME'])

        # Filter valid symbols
        df = df[df['SYMBOL'].isin(symbol_set)]

        # Shariah compliance
        if os.path.exists(SHARIAH_PATH):
            with open(SHARIAH_PATH, 'r') as f:
                shariah_symbols = set(line.strip().upper() for line in f.readlines())
            df['Shariah'] = df['SYMBOL'].apply(lambda x: x in shariah_symbols)
        else:
            df['Shariah'] = False

        return df.to_dict(orient='records')

    except Exception as e:
        return {"error": str(e)}

# --- GRADIO DEMO UI ---
demo = gr.Interface(fn=lambda: "✅ PSX Scanner backend is running", inputs=[], outputs="text")

# --- MOUNT FASTAPI WITH GRADIO FOR HUGGING FACE ---
from fastapi.middleware.wsgi import WSGIMiddleware
app.mount("/", WSGIMiddleware(demo.app))
