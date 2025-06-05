import gradio as gr
import requests
import pandas as pd
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import tempfile
import plotly.express as px
from pytz import timezone
from openpyxl import Workbook
from openpyxl.utils import get_column_letter
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from io import StringIO
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# === Configuration ===
PSX_HISTORICAL_URL = 'https://dps.psx.com.pk/historical'
PSX_STOCK_DATA_URL = 'https://docs.google.com/spreadsheets/d/1wGpkG37p2GV4aCckLYdaznQ4FjlQog8E/export?format=csv'
KMI_SYMBOLS_FILE = 'https://drive.google.com/uc?export=download&id=1Lf24EnwxUV3l64Y6i_XO-JoP0CEY-tuB'
MONTH_CODES = ['-JAN', '-FEB', '-MAR', '-APR', '-MAY', '-JUN',
               '-JUL', '-AUG', '-SEP', '-OCT', '-NOV', '-DEC']
MAX_DAYS_BACK = 5

# === Core Functions ===
def get_symbols_data():
    """Load symbol data from both PSX stock data and KMI compliance files"""
    try:
        # Load PSX Stock Data
        logging.info("Fetching PSX stock data...")
        psx_response = requests.get(PSX_STOCK_DATA_URL, timeout=30)
        psx_response.raise_for_status()
        
        # Handle potential encoding issues
        content = psx_response.content.decode('utf-8-sig')
        psx_df = pd.read_csv(StringIO(content))
        
        # Verify required columns
        psx_required = ['Symbol', 'Company Name', 'Sector']
        for col in psx_required:
            if col not in psx_df.columns:
                raise ValueError(f"Missing column: {col}")
        
        # Load KMI compliance data
        logging.info("Fetching KMI compliance data...")
        kmi_response = requests.get(KMI_SYMBOLS_FILE, timeout=30)
        kmi_response.raise_for_status()
        
        # Handle KMI as text file (one symbol per line)
        kmi_symbols = []
        kmi_content = kmi_response.text.splitlines()
        for line in kmi_content:
            if line.strip() and not line.startswith(('#', '//')):
                kmi_symbols.append(line.strip().upper())
        
        # Merge data into comprehensive dictionary
        symbols_data = {}
        for _, row in psx_df.iterrows():
            symbol = str(row['Symbol']).strip().upper()
            symbols_data[symbol] = {
                'Company': row['Company Name'],
                'Sector': row['Sector'],
                'KMI': 'Yes' if symbol in kmi_symbols else 'No'
            }

        logging.info(f"Loaded data for {len(symbols_data)} symbols")
        return symbols_data

    except Exception as e:
        logging.error(f"Error loading symbols data: {str(e)}")
        return {}

def fetch_market_data(date):
    """Fetch market data from PSX historical page for specific date"""
    try:
        date_str = date.strftime('%Y-%m-%d')
        logging.info(f"Fetching market data for {date_str}")
        response = requests.post(PSX_HISTORICAL_URL, data={'date': date_str}, timeout=30)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, 'html.parser')
        rows = soup.find_all('tr')

        if len(rows) <= 1:
            logging.warning(f"No data found for {date_str}")
            return None, None

        data = []
        for row in rows[1:]:  # Skip header row
            cells = [cell.text.strip() for cell in row.find_all('td')]
            if len(cells) >= 9:  # Now checking for 9 columns
                raw_volume = cells[8]
                try:
                    volume = int(raw_volume.replace(',', '')) if raw_volume and raw_volume != '-' else 0
                except ValueError:
                    volume = 0

                data.append([
                    cells[0],  # SYMBOL
                    cells[1],  # LDCP
                    cells[2],  # OPEN
                    cells[3],  # HIGH
                    cells[4],  # LOW
                    cells[5],  # CLOSE
                    str(volume)  # VOLUME
                ])

        if data:
            df = pd.DataFrame(data, columns=['SYMBOL', 'LDCP', 'OPEN', 'HIGH', 'LOW', 'CLOSE', 'VOLUME'])
            logging.info(f"Found {len(df)} records for {date_str}")
            return df, date_str

        return None, None
    except Exception as e:
        logging.error(f"Error fetching data for {date_str}: {str(e)}")
        return None, None

# ... [Rest of the core functions remain unchanged from your original working version] ...
# ... [Include all other functions: calculate_breakout_stats, save_to_excel, etc.] ...

# === Gradio Interface ===
def get_counts(df, status_col):
    """Count breakout statuses for visualization"""
    return {
        "Breakout": len(df[df[status_col].str.contains("▲▲")]),
        "Breakdown": len(df[df[status_col].str.contains("▼▼")]),
        "Within Range": len(df[df[status_col].str.contains("–")])
    }

def create_pie_chart(counts, title):
    """Create Plotly pie chart"""
    df = pd.DataFrame({
        'Status': list(counts.keys()),
        'Count': list(counts.values())
    })
    fig = px.pie(df, values='Count', names='Status', title=title)
    return fig

def style_dataframe(df):
    """Apply conditional styling to match Excel colors"""
    status_cols = ['DAILY_STATUS', 'WEEKLY_STATUS', 'MONTHLY_STATUS']
    
    # Create a copy to avoid modifying the original
    styled_df = df.copy()
    
    # Define color mapping
    color_map = {
        "▲▲": "#008000",  # Green
        "▼▼": "#FF0000",  # Red
        "–": "#D9D9D9"    # Gray
    }
    
    # Apply styling to status columns
    for col in status_cols:
        if col in styled_df.columns:
            styled_df[col] = styled_df[col].apply(
                lambda x: (x, next((v for k, v in color_map.items() if k in str(x)), 'transparent'))
            )
    
    return styled_df

def run_analysis():
    """Main analysis function for Gradio"""
    logging.info("Starting PSX Breakout Analysis")
    
    # Step 1: Get symbols data
    symbols_data = get_symbols_data()
    if not symbols_data:
        return [None] * 8
    
    # ... [Rest of run_analysis function remains unchanged] ...
    
    return (
        excel_file,
        result_df,
        fig_daily,
        fig_weekly,
        fig_monthly,
        daily_table,
        weekly_table,
        monthly_table
    )

def is_valid_symbol(symbol, symbols_data):
    """Check if symbol is valid and not a futures contract"""
    try:
        symbol = str(symbol).strip().upper()
        return (symbol in symbols_data) and not any(month in symbol for month in MONTH_CODES)
    except:
        return False

def is_weekend(date):
    """Check if date is weekend (Saturday/Sunday)"""
    return date.weekday() >= 5

# Gradio Interface
with gr.Blocks(title="PSX Breakout Scanner", theme=gr.themes.Soft()) as app:
    # Header section
    gr.Markdown("""
    <div style='text-align: center; margin-bottom: 20px'>
        <h1 style='color: #1F4E78'>📈 PSX Breakout Scanner</h1>
        <p>Identifies breakout/breakdown signals in Pakistan Stock Exchange</p>
    </div>
    """)
    
    # Control section
    with gr.Row():
        run_btn = gr.Button("Run Analysis", variant="primary", size="lg")
        download = gr.File(label="Download Excel Report", visible=False)
    
    # Status indicator
    status_text = gr.Textbox(label="Status", visible=True, interactive=False)
    
    # Main preview section
    with gr.Row():
        with gr.Column():
            gr.Markdown("### Data Preview")
            dataframe = gr.Dataframe(
                wrap=True,
                interactive=False,
                elem_id="main-dataframe"
            )
    
    # Analysis sections
    with gr.Row():
        with gr.Column():
            gr.Markdown("### Daily Analysis")
            with gr.Row():
                daily_plot = gr.Plot()
                daily_table = gr.Dataframe(
                    headers=["Status", "Count"],
                    interactive=False,
                    elem_classes="status-table"
                )
    
    with gr.Row():
        with gr.Column():
            gr.Markdown("### Weekly Analysis")
            with gr.Row():
                weekly_plot = gr.Plot()
                weekly_table = gr.Dataframe(
                    headers=["Status", "Count"],
                    interactive=False,
                    elem_classes="status-table"
                )
    
    with gr.Row():
        with gr.Column():
            gr.Markdown("### Monthly Analysis")
            with gr.Row():
                monthly_plot = gr.Plot()
                monthly_table = gr.Dataframe(
                    headers=["Status", "Count"],
                    interactive=False,
                    elem_classes="status-table"
                )
    
    # Custom CSS for better appearance
    app.css = """
    #main-dataframe {
        max-height: 600px;
        overflow-y: auto;
        width: 100%;
    }
    .status-table {
        width: 300px;
        margin-left: 20px;
    }
    .gradio-container {
        max-width: 1200px !important;
    }
    .dataframe table {
        width: 100% !important;
    }
    .dataframe th {
        background-color: #4F81BD !important;
        color: white !important;
        font-weight: bold !important;
        position: sticky;
        top: 0;
    }
    .dataframe td {
        padding: 8px !important;
    }
    .breakout {
        background-color: #008000 !important;
        color: white !important;
    }
    .breakdown {
        background-color: #FF0000 !important;
        color: white !important;
    }
    .within-range {
        background-color: #D9D9D9 !important;
    }
    """

    def run_analysis_wrapper():
        """Wrapper to handle the styled dataframe output"""
        try:
            results = run_analysis()
            if results[1] is not None:
                # Apply styling without changing data
                styled_df = style_dataframe(results[1])
                return (results[0], styled_df) + results[2:] + ("Analysis completed",)
            return [None] * 8 + ("Analysis failed - see logs",)
        except Exception as e:
            logging.exception("Error in analysis wrapper")
            return [None] * 8 + (f"Error: {str(e)}",)
    
    run_btn.click(
        fn=run_analysis_wrapper,
        outputs=[
            download,
            dataframe,
            daily_plot,
            weekly_plot,
            monthly_plot,
            daily_table,
            weekly_table,
            monthly_table,
            status_text
        ]
    )

if __name__ == "__main__":
    app.launch()