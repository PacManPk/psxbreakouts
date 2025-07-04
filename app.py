import os
import gradio as gr
import pandas as pd
from datetime import datetime, timedelta
import tempfile
import plotly.express as px
from pytz import timezone
from supabase import create_client, Client
from concurrent.futures import ThreadPoolExecutor
from io import StringIO

# Initialize Supabase client
url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(url, key)

# Configuration
MONTH_CODES = ['-JAN', '-FEB', '-MAR', '-APR', '-MAY', '-JUN', '-JUL', '-AUG', '-SEP', '-OCT', '-NOV', '-DEC']
MAX_DAYS_BACK = 5
CIRCUIT_BREAKER_PERCENTAGE = 7.5
CIRCUIT_BREAKER_RS_LIMIT = 1

# Global variable to store the loaded data
loaded_data = None

def load_data_from_supabase():
    """Load data from Supabase database."""
    try:
        response = supabase.table('psx_stocks').select("*").execute()
        data = pd.DataFrame(response.data)
        return data
    except Exception as e:
        print(f"Error fetching data from Supabase: {e}")
        return None

def load_data():
    global loaded_data
    loaded_data = load_data_from_supabase()
    # Additional processing can be added here

def filter_data(filter_breakout, filter_sector, filter_kmi, filter_circuit_breaker, filter_symbols):
    if loaded_data is None:
        return pd.DataFrame()
    filtered_df = loaded_data.copy()

    # Example filtering logic, adjust according to your actual data and requirements
    if filter_breakout:
        filtered_df = filtered_df[filtered_df['some_breakout_column'] == filter_breakout]

    if filter_sector:
        filtered_df = filtered_df[filtered_df['some_sector_column'] == filter_sector]

    if filter_kmi:
        filtered_df = filtered_df[filtered_df['some_kmi_column'] == filter_kmi]

    if filter_circuit_breaker:
        filtered_df = filtered_df[filtered_df['some_circuit_breaker_column'] == filter_circuit_breaker]

    if filter_symbols:
        symbols = [s.strip() for s in filter_symbols.split(',')]
        filtered_df = filtered_df[filtered_df['symbol'].isin(symbols)]

    return filtered_df

def create_excel_file(df):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
        with pd.ExcelWriter(tmp.name, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Filtered Data')
        return tmp.name

with gr.Blocks() as app:
    gr.Markdown("# Stock Data Analysis")

    with gr.Row():
        run_btn = gr.Button("Load Data")
        download = gr.File(label="Download Filtered Data")

    with gr.Row():
        filter_breakout = gr.Checkbox(label="Filter by Breakout")
        filter_sector = gr.Dropdown(label="Filter by Sector", choices=[])
        filter_kmi = gr.Checkbox(label="Filter by KMI Compliance")
        filter_circuit_breaker = gr.Checkbox(label="Filter by Circuit Breaker")
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
