import requests
import pandas as pd
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import gradio as gr
from pytz import timezone
from io import StringIO  # Added missing import

# Configuration
PSX_HISTORICAL_URL = 'https://dps.psx.com.pk/historical'
PSX_STOCK_DATA_URL = 'https://docs.google.com/spreadsheets/d/1wGpkG37p2GV4aCckLYdaznQ4FjlQog8E/export?format=csv'
KMI_SYMBOLS_FILE = 'https://drive.google.com/uc?export=download&id=1Lf24EnwxUV3l64Y6i_Xo-JoP0CEY-tuB'
MONTH_CODES = ['-JAN', '-FEB', '-MAR', '-APR', '-MAY', '-JUN',
               '-JUL', '-AUG', '-SEP', '-OCT', '-NOV', '-DEC']
MAX_DAYS_BACK = 5

def debug_print(message, important=False):
    """Only print important messages unless debugging is needed"""
    if important:
        print(f"🇵🇰 {message}")

def get_symbols_data():
    """Load symbol data from both PSX stock data and KMI compliance files"""
    try:
        # Load PSX Stock Data
        debug_print("Fetching symbol data...", important=True)
        psx_response = requests.get(PSX_STOCK_DATA_URL)
        psx_response.raise_for_status()
        psx_df = pd.read_csv(StringIO(psx_response.text))

        # Verify required columns
        psx_required = ['Symbol', 'Company Name', 'Sector']
        for col in psx_required:
            if col not in psx_df.columns:
                raise ValueError(f"Missing column: {col}")

        # Load KMI compliance data
        debug_print("Fetching KMI compliance data...", important=True)
        kmi_response = requests.get(KMI_SYMBOLS_FILE)
        kmi_response.raise_for_status()
        kmi_df = pd.read_csv(StringIO(kmi_response.text))

        # Create list of KMI compliant symbols
        kmi_symbols = []
        if 'Symbol' in kmi_df.columns:
            kmi_symbols = kmi_df['Symbol'].str.strip().str.upper().tolist()

        # Merge data into comprehensive dictionary
        symbols_data = {}
        for _, row in psx_df.iterrows():
            symbol = row['Symbol'].strip().upper()
            symbols_data[symbol] = {
                'Company': row['Company Name'],
                'Sector': row['Sector'],
                'KMI': 'Yes' if symbol in kmi_symbols else 'No'
            }

        debug_print(f"Loaded data for {len(symbols_data)} symbols", important=True)
        return symbols_data

    except Exception as e:
        debug_print(f"❌ Error loading symbols data: {e}", important=True)
        return {}

# [Rest of your existing functions remain exactly the same...]

def create_gradio_interface():
    """Create and launch the Gradio interface"""
    with gr.Blocks(title="PSX Breakout Scanner") as demo:
        gr.Markdown("# 🇵🇰 PSX Breakout Scanner")
        gr.Markdown("This app scans the Pakistan Stock Exchange (PSX) for stocks breaking out of their recent ranges.")
        
        with gr.Row():
            run_btn = gr.Button("Run Analysis", variant="primary")
            clear_btn = gr.Button("Clear")
        
        status_output = gr.Textbox(label="Status", interactive=False)
        title_output = gr.Markdown()
        results_output = gr.Dataframe(
            label="Breakout Analysis Results",
            headers=[
                'Symbol', 'Company', 'Sector', 'KMI', 'Volume',
                'LDCP', 'Open', 'Close', 'High', 'Low',
                'Prev Day High', 'Prev Day Low', 'Weekly High', 'Weekly Low',
                'Monthly High', 'Monthly Low', 'Daily Status', 'Weekly Status', 'Monthly Status'
            ],
            datatype=["str", "str", "str", "str", "str",
                     "number", "number", "number", "number", "number",
                     "number", "number", "number", "number",
                     "number", "number", "str", "str", "str"],
            wrap=True
        )
        
        def run_analysis_and_display():
            status = "Running analysis... Please wait"
            yield {status_output: status, title_output: "", results_output: None}
            
            df, title = run_analysis()
            if df is not None:
                yield {
                    status_output: "Analysis completed successfully!",
                    title_output: title,
                    results_output: df
                }
            else:
                yield {
                    status_output: "Error: Could not complete analysis (see logs)",
                    title_output: "",
                    results_output: None
                }
        
        def clear_outputs():
            return {
                status_output: "",
                title_output: "",
                results_output: None
            }
        
        run_btn.click(
            fn=run_analysis_and_display,
            outputs=[status_output, title_output, results_output],
            show_progress="minimal"
        )
        
        clear_btn.click(
            fn=clear_outputs,
            outputs=[status_output, title_output, results_output]
        )
    
    return demo

if __name__ == "__main__":
    demo = create_gradio_interface()
    demo.launch(server_name="0.0.0.0", server_port=7860)