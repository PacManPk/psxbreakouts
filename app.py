import os
import gradio as gr
import pandas as pd
from datetime import datetime, timedelta
from openpyxl import Workbook
from openpyxl.utils.dataframe import dataframe_to_rows
from openpyxl.utils import get_column_letter
from openpyxl.styles import Font, Alignment, PatternFill
from concurrent.futures import ThreadPoolExecutor
from io import StringIO
from pytz import timezone
import tempfile

from dotenv import load_dotenv

# ---------- ENVIRONMENT SETUP ----------
# Load from .env.local if present
if os.path.exists('.env.local'):
    load_dotenv('.env.local')
else:
    # On HuggingFace/Cloud, use environment variables as is
    pass

SUPABASE_URL = os.environ.get("NEXT_PUBLIC_SUPABASE_URL")
SUPABASE_KEY = os.environ.get("NEXT_PUBLIC_SUPABASE_ANON_KEY")

from supabase import create_client, Client

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ---------- CONFIGURATION ----------
MONTH_CODES = ['-JAN', '-FEB', '-MAR', '-APR', '-MAY', '-JUN', '-JUL', '-AUG', '-SEP', '-OCT', '-NOV', '-DEC']
MAX_DAYS_BACK = 5
CIRCUIT_BREAKER_PERCENTAGE = 7.5
CIRCUIT_BREAKER_RS_LIMIT = 1

loaded_data = None

# ---------- REPLACING DATA FETCH FUNCTIONS ----------

def get_symbols_data():
    """Load symbol data from companies and KMI compliance tables in supabase"""
    try:
        companies = supabase.table('companies').select("*").execute().data
        kmi = supabase.table('kmi_compliance').select("Symbol").execute().data

        psx_df = pd.DataFrame(companies)
        kmi_df = pd.DataFrame(kmi)

        psx_required = ['Symbol', 'Company Name', 'Sector']
        for col in psx_required:
            if col not in psx_df.columns:
                raise ValueError(f"Missing column: {col}")

        kmi_symbols = set(kmi_df['Symbol'].str.strip().str.upper()) if not kmi_df.empty else set()

        symbols_data = {
            row['Symbol'].strip().upper(): {
                'Company': row['Company Name'],
                'Sector': row['Sector'],
                'KMI': 'Yes' if row['Symbol'].strip().upper() in kmi_symbols else 'No'
            }
            for _, row in psx_df.iterrows()
        }
        return symbols_data
    except Exception as e:
        print(f"Error loading symbols data: {e}")
        return {}

def fetch_market_data(date):
    """Fetch market data from supabase for a specific date (YYYY-MM-DD)"""
    try:
        date_str = date.strftime('%Y-%m-%d')
        # Fetch data for this date
        data = supabase.table('market_data').select('*').eq('date', date_str).execute().data
        if not data:
            return None, None
        df = pd.DataFrame(data)
        # Optional: Ensure data column casing for compatibility with rest of code
        # Columns: SYMBOL, LDCP, OPEN, HIGH, LOW, CLOSE, VOLUME
        for col in ['SYMBOL', 'LDCP', 'OPEN', 'HIGH', 'LOW', 'CLOSE', 'VOLUME']:
            if col not in df.columns:
                # try normalized lower-case fallback
                if col.lower() in df.columns:
                    df.rename(columns={col.lower(): col}, inplace=True)
                else:
                    df[col] = None  # Ensure presence
        # Sort and clean up
        df = df[['SYMBOL', 'LDCP', 'OPEN', 'HIGH', 'LOW', 'CLOSE', 'VOLUME']]
        return df, date_str
    except Exception as e:
        print(f"Error fetching market data from supabase: {e}")
        return None, None

# All other downstream logic (calculate_breakout_stats, save_to_excel, filter_data, etc) remains UNCHANGED

# ... (insert unchanged code for everything below; e.g., calculate_breakout_stats, save_to_excel, load_data, etc.)

# Copy unchanged code from your supplied script for:
# - calculate_breakout_stats
# - save_to_excel
# - get_counts
# - create_pie_chart
# - highlight_status
# - filter_data
# - is_valid_symbol
# - is_weekend

# ---------- Gradio Interface (UNCHANGED) ----------

with gr.Blocks(title="PSX Breakout Scanner", theme=gr.themes.Soft()) as app:
    gr.Markdown("# 📈 PSX Breakout Scanner")
    gr.Markdown("Identifies breakout/breakdown signals in Pakistan Stock Exchange")

    with gr.Row():
        run_btn = gr.Button("Run Analysis", variant="primary")
        download = gr.File(label="Download Excel Report")

    with gr.Row():
        filter_breakout = gr.Checkbox(label="Show only stocks with Daily, Weekly, and Monthly Breakouts")
        filter_sector = gr.Dropdown(label="Filter by Sector", choices=["All"], value="All")
        filter_kmi = gr.Dropdown(label="Filter by Shariah Compliance", choices=["All", "Yes", "No"], value="All")
        filter_circuit_breaker = gr.Dropdown(label="Filter by Circuit Breaker", choices=["All", "Upper Circuit Breaker", "Lower Circuit Breaker"], value="All")
        filter_symbols = gr.Textbox(label="Filter by Symbols (comma-separated)", placeholder="e.g., SYM1, SYM2")

    with gr.Row():
        dataframe = gr.DataFrame(interactive=False, wrap=True)

    with gr.Row():
        with gr.Column():
            gr.Markdown("### Daily Analysis")
            daily_plot = gr.Plot()
            daily_table = gr.Dataframe(headers=["Status", "Count"])

        with gr.Column():
            gr.Markdown("### Weekly Analysis")
            weekly_plot = gr.Plot()
            weekly_table = gr.Dataframe(headers=["Status", "Count"])

        with gr.Column():
            gr.Markdown("### Monthly Analysis")
            monthly_plot = gr.Plot()
            monthly_table = gr.Dataframe(headers=["Status", "Count"])

    run_btn.click(
        fn=load_data,
        outputs=[
            download,
            dataframe,
            daily_plot,
            weekly_plot,
            monthly_plot,
            daily_table,
            weekly_table,
            monthly_table,
            filter_sector
        ]
    )

    filter_breakout.change(
        fn=filter_data,
        inputs=[filter_breakout, filter_sector, filter_kmi, filter_circuit_breaker, filter_symbols],
        outputs=dataframe
    )

    filter_sector.change(
        fn=filter_data,
        inputs=[filter_breakout, filter_sector, filter_kmi, filter_circuit_breaker, filter_symbols],
        outputs=dataframe
    )

    filter_kmi.change(
        fn=filter_data,
        inputs=[filter_breakout, filter_sector, filter_kmi, filter_circuit_breaker, filter_symbols],
        outputs=dataframe
    )

    filter_circuit_breaker.change(
        fn=filter_data,
        inputs=[filter_breakout, filter_sector, filter_kmi, filter_circuit_breaker, filter_symbols],
        outputs=dataframe
    )

    filter_symbols.change(
        fn=filter_data,
        inputs=[filter_breakout, filter_sector, filter_kmi, filter_circuit_breaker, filter_symbols],
        outputs=dataframe
    )

if __name__ == "__main__":
    app.launch()
