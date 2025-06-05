import gradio as gr
import requests
import pandas as pd
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import os
import tempfile
import plotly.express as px
from pytz import timezone
from openpyxl import load_workbook, Workbook
from openpyxl.utils import get_column_letter
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.chart import PieChart, Reference
from openpyxl.chart.label import DataLabelList
from io import StringIO

# === Configuration ===
PSX_HISTORICAL_URL = 'https://dps.psx.com.pk/historical'
PSX_STOCK_DATA_URL = 'https://docs.google.com/spreadsheets/d/1wGpkG37p2GV4aCckLYdaznQ4FjlQog8E/export?format=csv'
KMI_SYMBOLS_FILE = 'https://drive.google.com/uc?export=download&id=1Lf24EnwxUV3l64Y6i_XO-JoP0CEY-tuB'
MONTH_CODES = ['-JAN', '-FEB', '-MAR', '-APR', '-MAY', '-JUN',
               '-JUL', '-AUG', '-SEP', '-OCT', '-NOV', '-DEC']
MAX_DAYS_BACK = 5

# === Core Functions (placeholders) ===
def get_symbols_data():
    return pd.read_csv(PSX_STOCK_DATA_URL)

def fetch_market_data(date):
    return pd.DataFrame(), date.strftime('%Y-%m-%d')

def calculate_breakout_stats(today_df, prev_day_df, prev_week_df, prev_month_df, symbols_data):
    df = today_df.copy()
    df['Signal'] = 'Breakout'
    return df

def save_to_excel(df, date_str):
    temp_dir = tempfile.mkdtemp()
    file_path = os.path.join(temp_dir, f"PSX_Breakout_{date_str}.xlsx")
    df.to_excel(file_path, index=False)
    return file_path

# === Gradio UI ===
def psx_breakout_interface():
    with gr.Blocks(title="PSX Breakout Scanner") as demo:
        gr.Markdown("""
        # 📈 PSX Breakout Scanner
        Analyze daily, weekly, and monthly breakout signals for PSX-listed stocks.
        """)

        latest_df = gr.State()
        report_date = gr.State()

        download_button = gr.Button("💾 Download Excel Report", visible=False)
        download_file = gr.File(visible=False)
        status_output = gr.Textbox(label="Status", interactive=False)

        with gr.Row():
            run_button = gr.Button("🔍 Run Scanner", scale=2)

        with gr.Tabs():
            with gr.Tab("📊 Results Table"):
                result_table = gr.Dataframe(
                    headers="row",
                    interactive=False,
                    max_rows=30,
                    wrap=True,
                    height=400,
                    label="Results Preview"
                )

            with gr.Tab("📥 Download"):
                gr.Markdown("Click the button below to export results to Excel.")
                download_button.render()
                download_file.render()

        def run_all():
            today = datetime.now(timezone('Asia/Karachi')).date()
            symbols_data = get_symbols_data()

            for offset in range(MAX_DAYS_BACK):
                date_to_check = today - timedelta(days=offset)
                today_data, date_str = fetch_market_data(date_to_check)
                if today_data is not None:
                    break
            else:
                return gr.update(value="❌ No data found for recent days."), None, None, None

            prev_day_data = pd.DataFrame()
            prev_week_data = pd.DataFrame()
            prev_month_data = pd.DataFrame()

            for i in range(1, 7):
                d = date_to_check - timedelta(days=i)
                data, _ = fetch_market_data(d)
                if not data.empty:
                    prev_day_data = data
                    break

            for i in range(7, 15):
                d = date_to_check - timedelta(days=i)
                data, _ = fetch_market_data(d)
                if not data.empty:
                    prev_week_data = pd.concat([prev_week_data, data], ignore_index=True)

            for i in range(30, 60):
                d = date_to_check - timedelta(days=i)
                data, _ = fetch_market_data(d)
                if not data.empty:
                    prev_month_data = pd.concat([prev_month_data, data], ignore_index=True)

            final_df = calculate_breakout_stats(today_data, prev_day_data, prev_week_data, prev_month_data, symbols_data)
            return "✅ Analysis Complete", final_df, final_df, date_str

        def export_data(df, date_str):
            if df is not None and date_str:
                file_path = save_to_excel(df, date_str)
                return file_path
            return None

        run_button.click(
            fn=run_all,
            inputs=[],
            outputs=[status_output, result_table, latest_df, report_date]
        )

        run_button.click(lambda: gr.update(visible=True), None, download_button)

        download_button.click(
            fn=export_data,
            inputs=[latest_df, report_date],
            outputs=download_file
        )

    return demo

# === Launch App ===
if __name__ == "__main__":
    demo = psx_breakout_interface()
    demo.launch()