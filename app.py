import gradio as gr
import requests
import pandas as pd
from datetime import datetime, timedelta
from io import StringIO

# Hardcoded URLs from notebook
PSX_STOCK_DATA_URL = 'https://docs.google.com/spreadsheets/d/1wGpkG37p2GV4aCckLYdaznQ4FjlQog8E/export?format=csv'
KMI_SYMBOLS_FILE = 'https://drive.google.com/uc?export=download&id=1Lf24EnwxUV3l64Y6i_XO-JoP0CEY-tuB'

def debug_print(msg):
    print(msg)

def get_symbols_data():
    try:
        psx_response = requests.get(PSX_STOCK_DATA_URL)
        psx_response.raise_for_status()
        psx_df = pd.read_csv(StringIO(psx_response.text))

        kmi_response = requests.get(KMI_SYMBOLS_FILE)
        kmi_response.raise_for_status()
        kmi_df = pd.read_csv(StringIO(kmi_response.text))

        kmi_symbols = []
        if 'Symbol' in kmi_df.columns:
            kmi_symbols = kmi_df['Symbol'].str.strip().str.upper().tolist()

        symbols_data = {}
        for _, row in psx_df.iterrows():
            symbol = row['Symbol'].strip().upper()
            symbols_data[symbol] = {
                'Company': row['Company Name'],
                'Sector': row['Sector'],
                'KMI': 'Yes' if symbol in kmi_symbols else 'No'
            }

        return symbols_data
    except Exception as e:
        return {"error": str(e)}

def display_sector_data():
    data = get_symbols_data()
    if "error" in data:
        return f"❌ Error fetching data: {data['error']}"
    
    df = pd.DataFrame.from_dict(data, orient='index').reset_index()
    df.rename(columns={'index': 'Symbol'}, inplace=True)
    return df

with gr.Blocks(title="PSX KMI Compliance & Sector Lookup") as demo:
    gr.Markdown("# 📈 PSX Sector + KMI Compliance Scanner")
    gr.Markdown("Click below to fetch and display the latest PSX symbol data.")

    with gr.Row():
        display_btn = gr.Button("Fetch PSX Data")
        output_df = gr.Dataframe(headers=["Symbol", "Company", "Sector", "KMI"])

    display_btn.click(fn=display_sector_data, outputs=output_df)

demo.launch(share=True)
