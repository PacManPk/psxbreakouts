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

def calculate_breakout_stats(today_data, prev_day_data, prev_week_data, prev_month_data, symbols_data):
    """Calculate breakout statuses using proper weekly/monthly periods"""
    results = []

    for _, today_row in today_data.iterrows():
        symbol = today_row['SYMBOL']
        company_info = symbols_data.get(symbol, {})
        company_name = company_info.get('Company', symbol)
        sector = company_info.get('Sector', 'N/A')
        kmi_status = company_info.get('KMI', 'No')

        # Initialize variables
        today_close = today_high = today_low = today_ldcp = volume = 0
        prev_day_high = prev_day_low = weekly_high = weekly_low = monthly_high = monthly_low = "N/A"
        daily_status = "N/A"
        weekly_status = "N/A"
        monthly_status = "N/A"

        try:
            today_close = float(today_row['CLOSE'].replace(',', '')) if today_row['CLOSE'] else 0
            today_high = float(today_row['HIGH'].replace(',', '')) if today_row['HIGH'] else 0
            today_low = float(today_row['LOW'].replace(',', '')) if today_row['LOW'] else 0
            today_ldcp = float(today_row['LDCP'].replace(',', '')) if today_row['LDCP'] else 0

            if today_row['VOLUME'] and str(today_row['VOLUME']).strip():
                volume = float(str(today_row['VOLUME']).replace(',', ''))
                volume_str = f"{volume:,.0f}"
            else:
                volume_str = "0"
        except Exception as e:
            logging.error(f"Error processing numerical values for {symbol}: {str(e)}")
            continue

        # Daily breakout logic
        if prev_day_data is not None:
            prev_day_row = prev_day_data[prev_day_data['SYMBOL'].str.upper() == symbol.upper()]
            if not prev_day_row.empty:
                try:
                    prev_day_high = float(prev_day_row['HIGH'].iloc[0].replace(',', '')) if prev_day_row['HIGH'].iloc[0] else "N/A"
                    prev_day_low = float(prev_day_row['LOW'].iloc[0].replace(',', '')) if prev_day_row['LOW'].iloc[0] else "N/A"

                    if isinstance(prev_day_high, float) and isinstance(prev_day_low, float):
                        if today_close > prev_day_high:
                            daily_status = "▲▲ Daily Breakout"
                        elif today_close < prev_day_low:
                            daily_status = "▼▼ Daily Breakdown"
                        else:
                            daily_status = "– Daily Within Range"
                except Exception as e:
                    daily_status = "– Daily Data Error"

        # Weekly breakout logic
        if prev_week_data is not None:
            symbol_week_data = prev_week_data[prev_week_data['SYMBOL'].str.upper() == symbol.upper()]
            if not symbol_week_data.empty:
                try:
                    weekly_high = symbol_week_data['HIGH'].apply(
                        lambda x: float(x.replace(',', '')) if str(x) != 'nan' else 0).max()
                    weekly_low = symbol_week_data['LOW'].apply(
                        lambda x: float(x.replace(',', '')) if str(x) != 'nan' else 0).min()

                    if today_close > weekly_high:
                        weekly_status = "▲▲ Weekly Breakout"
                    elif today_close < weekly_low:
                        weekly_status = "▼▼ Weekly Breakdown"
                    else:
                        weekly_status = "– Weekly Within Range"
                except Exception as e:
                    weekly_status = "– Weekly Data Error"

        # Monthly breakout logic
        if prev_month_data is not None:
            symbol_month_data = prev_month_data[prev_month_data['SYMBOL'].str.upper() == symbol.upper()]
            if not symbol_month_data.empty:
                try:
                    monthly_high = symbol_month_data['HIGH'].apply(
                        lambda x: float(x.replace(',', '')) if str(x) != 'nan' else 0).max()
                    monthly_low = symbol_month_data['LOW'].apply(
                        lambda x: float(x.replace(',', '')) if str(x) != 'nan' else 0).min()

                    if today_close > monthly_high:
                        monthly_status = "▲▲ Monthly Breakout"
                    elif today_close < monthly_low:
                        monthly_status = "▼▼ Monthly Breakdown"
                    else:
                        monthly_status = "– Monthly Within Range"
                except Exception as e:
                    monthly_status = "– Monthly Data Error"

        # Fallback to LDCP comparison
        if daily_status == "N/A":
            try:
                if today_close > today_ldcp:
                    daily_status = "▲▲ Daily Breakout"
                elif today_close < today_ldcp:
                    daily_status = "▼▼ Daily Breakdown"
                else:
                    daily_status = "– Daily Within Range"
            except:
                daily_status = "– No Data"

        def format_value(val):
            if isinstance(val, (int, float)):
                return f"{val:,.2f}"
            return str(val)

        results.append({
            'SYMBOL': symbol,
            'COMPANY': company_name,
            'SECTOR': sector,
            'KMI_COMPLIANT': kmi_status,
            'VOLUME': volume_str,
            'LDCP': format_value(today_ldcp),
            'OPEN': format_value(float(today_row['OPEN'].replace(',', '')) if today_row['OPEN'] else 0),
            'CLOSE': format_value(today_close),
            'HIGH': format_value(today_high),
            'LOW': format_value(today_low),
            'PREV_DAY_HIGH': format_value(prev_day_high) if isinstance(prev_day_high, (int, float)) else prev_day_high,
            'PREV_DAY_LOW': format_value(prev_day_low) if isinstance(prev_day_low, (int, float)) else prev_day_low,
            'WEEKLY_HIGH': format_value(weekly_high) if isinstance(weekly_high, (int, float)) else weekly_high,
            'WEEKLY_LOW': format_value(weekly_low) if isinstance(weekly_low, (int, float)) else weekly_low,
            'MONTHLY_HIGH': format_value(monthly_high) if isinstance(monthly_high, (int, float)) else monthly_high,
            'MONTHLY_LOW': format_value(monthly_low) if isinstance(monthly_low, (int, float)) else monthly_low,
            'DAILY_STATUS': daily_status,
            'WEEKLY_STATUS': weekly_status,
            'MONTHLY_STATUS': monthly_status
        })

    return pd.DataFrame(results)

def save_to_excel(df, report_date):
    """Save the results to an Excel file with formatting"""
    try:
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
            EXCEL_FILE = tmp.name
            workbook = Workbook()
            worksheet = workbook.active
            worksheet.title = 'Breakout Analysis'

            # Clear existing data
            worksheet.delete_rows(1, worksheet.max_row)

            formatted_date = datetime.strptime(report_date, "%Y-%m-%d").strftime("%d %B %Y")

            # Main title
            worksheet.merge_cells('A1:S1')
            title_cell = worksheet.cell(row=1, column=1, value=f"📈 PSX Breakout Analysis - {formatted_date}")
            title_cell.font = Font(bold=True, size=14, color="1F4E78")
            title_cell.alignment = Alignment(horizontal='center')

            # Timestamp
            worksheet.merge_cells('A2:S2')
            timestamp_cell = worksheet.cell(
                row=2,
                column=1,
                value=f"⏰ Generated: {datetime.now(timezone('Asia/Karachi')).strftime('%d %B %Y %H:%M:%S')} (PKT)"
            )
            timestamp_cell.font = Font(size=12, italic=True, color="404040")
            timestamp_cell.alignment = Alignment(horizontal='center')

            # Write headers
            headers = [
                'SYMBOL', 'COMPANY', 'SECTOR', 'KMI_COMPLIANT', 'VOLUME',
                'LDCP', 'OPEN', 'CLOSE', 'HIGH', 'LOW',
                'PREV_DAY_HIGH', 'PREV_DAY_LOW', 'WEEKLY_HIGH', 'WEEKLY_LOW',
                'MONTHLY_HIGH', 'MONTHLY_LOW', 'DAILY_STATUS', 'WEEKLY_STATUS', 'MONTHLY_STATUS'
            ]

            header_font = Font(bold=True, color="FFFFFF")
            header_fill = PatternFill(start_color="4F81BD", fill_type="solid")

            for col_num, header in enumerate(headers, 1):
                cell = worksheet.cell(row=3, column=col_num, value=header)
                cell.font = header_font
                cell.fill = header_fill
                cell.alignment = Alignment(horizontal='center')

            # Write data
            for row_idx, row_data in enumerate(df.values, 4):
                for col_idx, value in enumerate(row_data, 1):
                    worksheet.cell(row=row_idx, column=col_idx, value=value)

            # Apply conditional formatting
            status_cols = {
                17: 'DAILY_STATUS',
                18: 'WEEKLY_STATUS',
                19: 'MONTHLY_STATUS'
            }

            cond_formatting = {
                "▲▲": PatternFill(start_color="008000", fill_type="solid"),
                "▲": PatternFill(start_color="92D050", fill_type="solid"),
                "▼▼": PatternFill(start_color="FF0000", fill_type="solid"),
                "▼": PatternFill(start_color="FFC7CE", fill_type="solid"),
                "–": PatternFill(start_color="D9D9D9", fill_type="solid")
            }

            for col_num, col_name in status_cols.items():
                for row in range(4, len(df) + 4):
                    cell = worksheet.cell(row=row, column=col_num)
                    for prefix, fill in cond_formatting.items():
                        if prefix in str(cell.value):
                            cell.fill = fill
                            break

            # Auto-adjust column widths
            for column in worksheet.columns:
                max_length = 0
                column_letter = get_column_letter(column[0].column)

                if column_letter in ['Q', 'R', 'S']:
                    worksheet.column_dimensions[column_letter].width = 18
                    continue

                for cell in column:
                    try:
                        if len(str(cell.value)) > max_length:
                            max_length = len(str(cell.value))
                    except:
                        pass
                adjusted_width = (max_length + 2) * 1.1
                worksheet.column_dimensions[column_letter].width = adjusted_width

            # Manual adjustments
            worksheet.column_dimensions['A'].width = 12
            worksheet.column_dimensions['B'].width = 30
            worksheet.column_dimensions['C'].width = 20
            worksheet.column_dimensions['D'].width = 12
            worksheet.column_dimensions['E'].width = 15

            # Freeze panes
            worksheet.freeze_panes = 'C4'

            workbook.save(EXCEL_FILE)
            return EXCEL_FILE

    except Exception as e:
        logging.error(f"Error saving Excel file: {e}")
        return None

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

def run_analysis():
    """Main analysis function for Gradio"""
    logging.info("Starting PSX Breakout Analysis")
    
    # Step 1: Get symbols data
    symbols_data = get_symbols_data()
    if not symbols_data:
        return [None] * 8
    
    # Step 2: Find most recent trading day
    date_to_try = datetime.now()
    attempts = 0
    today_data, today_date = None, None

    while attempts < MAX_DAYS_BACK and today_data is None:
        if not is_weekend(date_to_try):
            today_data, today_date = fetch_market_data(date_to_try)
            if today_data is not None:
                break
        date_to_try -= timedelta(days=1)
        attempts += 1

    if today_data is None:
        logging.error("No market data found")
        return [None] * 8

    # Filter valid symbols
    today_data = today_data[today_data['SYMBOL'].apply(lambda x: is_valid_symbol(x, symbols_data))].copy()
    if today_data.empty:
        logging.error("No valid symbols found")
        return [None] * 8

    # Step 3: Get historical data
    target_date = datetime.strptime(today_date, "%Y-%m-%d")
    
    # Previous day data
    prev_day_data = None
    days_back = 1
    while days_back <= MAX_DAYS_BACK and prev_day_data is None:
        prev_day_date = target_date - timedelta(days=days_back)
        if not is_weekend(prev_day_date):
            prev_day_data, _ = fetch_market_data(prev_day_date)
            if prev_day_data is not None:
                break
        days_back += 1

    # Previous week data (Mon-Fri)
    prev_week_data = None
    prev_monday = target_date - timedelta(days=target_date.weekday() + 7)
    prev_friday = prev_monday + timedelta(days=4)
    current_date = prev_monday
    all_week_data = []
    while current_date <= prev_friday:
        if not is_weekend(current_date):
            data, _ = fetch_market_data(current_date)
            if data is not None:
                all_week_data.append(data)
        current_date += timedelta(days=1)
    if all_week_data:
        prev_week_data = pd.concat(all_week_data)

    # Previous month data
    prev_month_data = None
    first_day_prev_month = (target_date.replace(day=1) - timedelta(days=1)).replace(day=1)
    last_day_prev_month = target_date.replace(day=1) - timedelta(days=1)
    current_date = first_day_prev_month
    all_month_data = []
    while current_date <= last_day_prev_month:
        if not is_weekend(current_date):
            data, _ = fetch_market_data(current_date)
            if data is not None:
                all_month_data.append(data)
        current_date += timedelta(days=1)
    if all_month_data:
        prev_month_data = pd.concat(all_month_data)

    # Step 4: Calculate breakout stats
    result_df = calculate_breakout_stats(today_data, prev_day_data, prev_week_data, prev_month_data, symbols_data)

    # Step 5: Generate outputs
    excel_file = save_to_excel(result_df, today_date)
    
    # Create visualizations
    daily_counts = get_counts(result_df, 'DAILY_STATUS')
    weekly_counts = get_counts(result_df, 'WEEKLY_STATUS')
    monthly_counts = get_counts(result_df, 'MONTHLY_STATUS')
    
    fig_daily = create_pie_chart(daily_counts, "Daily Breakout Distribution")
    fig_weekly = create_pie_chart(weekly_counts, "Weekly Breakout Distribution")
    fig_monthly = create_pie_chart(monthly_counts, "Monthly Breakout Distribution")
    
    daily_table = pd.DataFrame.from_dict(daily_counts, orient='index').reset_index()
    weekly_table = pd.DataFrame.from_dict(weekly_counts, orient='index').reset_index()
    monthly_table = pd.DataFrame.from_dict(monthly_counts, orient='index').reset_index()

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
            status_msg = "Analysis completed successfully"
            return (*results, status_msg)
        except Exception as e:
            logging.exception("Error in analysis")
            status_msg = f"Error: {str(e)}"
            return (None, None, None, None, None, None, None, None, status_msg)
    
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