import gradio as gr
import requests
import pandas as pd
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import tempfile
import plotly.express as px
from pytz import timezone
from openpyxl import Workbook
from openpyxl.utils.dataframe import dataframe_to_rows
from openpyxl.utils import get_column_letter
from openpyxl.styles import Font, Alignment, PatternFill
from concurrent.futures import ThreadPoolExecutor
from io import StringIO

# Configuration
PSX_HISTORICAL_URL = 'https://dps.psx.com.pk/historical'
PSX_STOCK_DATA_URL = 'https://docs.google.com/spreadsheets/d/1wGpkG37p2GV4aCckLYdaznQ4FjlQog8E/export?format=csv'
KMI_SYMBOLS_FILE = 'https://drive.google.com/uc?export=download&id=1Lf24EnwxUV3l64Y6i_XO-JoP0CEY-tuB'
MONTH_CODES = ['-JAN', '-FEB', '-MAR', '-APR', '-MAY', '-JUN', '-JUL', '-AUG', '-SEP', '-OCT', '-NOV', '-DEC']
MAX_DAYS_BACK = 5
CIRCUIT_BREAKER_PERCENTAGE = 7.5
CIRCUIT_BREAKER_RS_LIMIT = 1

# Global variable to store the loaded data
loaded_data = None

def fetch_url(url):
    """Fetch data from a URL."""
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.text
    except Exception as e:
        print(f"Error fetching data from {url}: {e}")
        return None

def get_symbols_data():
    """Load symbol data from both PSX stock data and KMI compliance files"""
    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            psx_response_future = executor.submit(fetch_url, PSX_STOCK_DATA_URL)
            kmi_response_future = executor.submit(fetch_url, KMI_SYMBOLS_FILE)

            psx_response_text = psx_response_future.result()
            kmi_response_text = kmi_response_future.result()

        if not psx_response_text or not kmi_response_text:
            return {}

        psx_df = pd.read_csv(StringIO(psx_response_text))
        kmi_df = pd.read_csv(StringIO(kmi_response_text))

        psx_required = ['Symbol', 'Company Name', 'Sector']
        for col in psx_required:
            if col not in psx_df.columns:
                raise ValueError(f"Missing column: {col}")

        kmi_symbols = set()
        if 'Symbol' in kmi_df.columns:
            kmi_symbols = set(kmi_df['Symbol'].str.strip().str.upper())

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
    """Fetch market data from PSX historical page for a specific date"""
    try:
        date_str = date.strftime('%Y-%m-%d')
        response = requests.post(PSX_HISTORICAL_URL, data={'date': date_str}, timeout=30)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, 'html.parser')
        rows = soup.find_all('tr')

        if len(rows) <= 1:
            return None, None

        data = []
        for row in rows[1:]:
            cells = [cell.text.strip() for cell in row.find_all('td')]
            if len(cells) >= 9:
                raw_volume = cells[8]
                try:
                    volume = int(raw_volume.replace(',', '')) if raw_volume and raw_volume != '-' else 0
                except ValueError:
                    volume = 0

                data.append([
                    cells[0], cells[1], cells[2], cells[3], cells[4], cells[5], str(volume)
                ])

        if data:
            df = pd.DataFrame(data, columns=['SYMBOL', 'LDCP', 'OPEN', 'HIGH', 'LOW', 'CLOSE', 'VOLUME'])
            return df, date_str

        return None, None
    except Exception as e:
        print(f"Error fetching data: {str(e)}")
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

        try:
            today_close = float(today_row['CLOSE'].replace(',', '')) if today_row['CLOSE'] else 0
            today_high = float(today_row['HIGH'].replace(',', '')) if today_row['HIGH'] else 0
            today_low = float(today_row['LOW'].replace(',', '')) if today_row['LOW'] else 0
            today_ldcp = float(today_row['LDCP'].replace(',', '')) if today_row['LDCP'] else 0
            volume = float(str(today_row['VOLUME']).replace(',', '')) if today_row['VOLUME'] and str(today_row['VOLUME']).strip() else 0
            volume_str = f"{volume:,.0f}"
        except Exception as e:
            print(f"Error processing numerical values for {symbol}: {str(e)}")
            continue

        daily_status = weekly_status = monthly_status = circuit_breaker_status = "N/A"
        prev_day_high = prev_day_low = weekly_high = weekly_low = monthly_high = monthly_low = "N/A"

        if prev_day_data is not None:
            prev_day_row = prev_day_data[prev_day_data['SYMBOL'].str.upper() == symbol.upper()]
            if not prev_day_row.empty:
                try:
                    prev_day_close = float(prev_day_row['CLOSE'].iloc[0].replace(',', '')) if prev_day_row['CLOSE'].iloc[0] else 0
                    prev_day_high = float(prev_day_row['HIGH'].iloc[0].replace(',', '')) if prev_day_row['HIGH'].iloc[0] else "N/A"
                    prev_day_low = float(prev_day_row['LOW'].iloc[0].replace(',', '')) if prev_day_row['LOW'].iloc[0] else "N/A"

                    if isinstance(prev_day_high, float) and isinstance(prev_day_low, float):
                        if today_close > prev_day_high:
                            daily_status = "▲▲ Daily Breakout"
                        elif today_close < prev_day_low:
                            daily_status = "▼▼ Daily Breakdown"
                        else:
                            daily_status = "– Daily Within Range"

                    if prev_day_close > 0:
                        price_change = today_close - prev_day_close
                        circuit_breaker_limit = max(CIRCUIT_BREAKER_RS_LIMIT, prev_day_close * CIRCUIT_BREAKER_PERCENTAGE / 100)
                        if price_change > circuit_breaker_limit:
                            circuit_breaker_status = "Upper Circuit Breaker"
                        elif price_change < -circuit_breaker_limit:
                            circuit_breaker_status = "Lower Circuit Breaker"
                except Exception as e:
                    daily_status = "– Daily Data Error"

        if prev_week_data is not None:
            symbol_week_data = prev_week_data[prev_week_data['SYMBOL'].str.upper() == symbol.upper()]
            if not symbol_week_data.empty:
                try:
                    weekly_high = symbol_week_data['HIGH'].apply(lambda x: float(x.replace(',', '')) if str(x) != 'nan' else 0).max()
                    weekly_low = symbol_week_data['LOW'].apply(lambda x: float(x.replace(',', '')) if str(x) != 'nan' else 0).min()

                    if today_close > weekly_high:
                        weekly_status = "▲▲ Weekly Breakout"
                    elif today_close < weekly_low:
                        weekly_status = "▼▼ Weekly Breakdown"
                    else:
                        weekly_status = "– Weekly Within Range"
                except Exception as e:
                    weekly_status = "– Weekly Data Error"

        if prev_month_data is not None:
            symbol_month_data = prev_month_data[prev_month_data['SYMBOL'].str.upper() == symbol.upper()]
            if not symbol_month_data.empty:
                try:
                    monthly_high = symbol_month_data['HIGH'].apply(lambda x: float(x.replace(',', '')) if str(x) != 'nan' else 0).max()
                    monthly_low = symbol_month_data['LOW'].apply(lambda x: float(x.replace(',', '')) if str(x) != 'nan' else 0).min()

                    if today_close > monthly_high:
                        monthly_status = "▲▲ Monthly Breakout"
                    elif today_close < monthly_low:
                        monthly_status = "▼▼ Monthly Breakdown"
                    else:
                        monthly_status = "– Monthly Within Range"
                except Exception as e:
                    monthly_status = "– Monthly Data Error"

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
            'MONTHLY_STATUS': monthly_status,
            'CIRCUIT_BREAKER_STATUS': circuit_breaker_status
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

            formatted_date = datetime.strptime(report_date, "%Y-%m-%d").strftime("%d %B %Y")

            worksheet.merge_cells('A1:T1')
            title_cell = worksheet['A1']
            title_cell.value = f"📈 PSX Breakout Analysis - {formatted_date}"
            title_cell.font = Font(bold=True, size=14, color="1F4E78")
            title_cell.alignment = Alignment(horizontal='center')

            worksheet.merge_cells('A2:T2')
            timestamp_cell = worksheet['A2']
            timestamp_cell.value = f"⏰ Generated: {datetime.now(timezone('Asia/Karachi')).strftime('%d %B %Y %H:%M:%S')} (PKT)"
            timestamp_cell.font = Font(size=12, italic=True, color="404040")
            timestamp_cell.alignment = Alignment(horizontal='center')

            headers = [
                'SYMBOL', 'COMPANY', 'SECTOR', 'KMI_COMPLIANT', 'VOLUME',
                'LDCP', 'OPEN', 'CLOSE', 'HIGH', 'LOW',
                'PREV_DAY_HIGH', 'PREV_DAY_LOW', 'WEEKLY_HIGH', 'WEEKLY_LOW',
                'MONTHLY_HIGH', 'MONTHLY_LOW', 'DAILY_STATUS', 'WEEKLY_STATUS', 'MONTHLY_STATUS', 'CIRCUIT_BREAKER_STATUS'
            ]

            for col_num, header in enumerate(headers, 1):
                cell = worksheet.cell(row=3, column=col_num, value=header)
                cell.font = Font(bold=True, color="FFFFFF")
                cell.fill = PatternFill(start_color="4F81BD", fill_type="solid")
                cell.alignment = Alignment(horizontal='center')

            for row in dataframe_to_rows(df, index=False, header=False):
                worksheet.append(row)

            status_cols = {17: 'DAILY_STATUS', 18: 'WEEKLY_STATUS', 19: 'MONTHLY_STATUS', 20: 'CIRCUIT_BREAKER_STATUS'}

            cond_formatting = {
                "▲▲": PatternFill(start_color="008000", fill_type="solid"),
                "▲": PatternFill(start_color="92D050", fill_type="solid"),
                "▼▼": PatternFill(start_color="FF0000", fill_type="solid"),
                "▼": PatternFill(start_color="FFC7CE", fill_type="solid"),
                "–": PatternFill(start_color="D9D9D9", fill_type="solid"),
                "Upper Circuit Breaker": PatternFill(start_color="FFD700", fill_type="solid"),
                "Lower Circuit Breaker": PatternFill(start_color="A52A2A", fill_type="solid")
            }

            for col_num, col_name in status_cols.items():
                for row in range(4, len(df) + 4):
                    cell = worksheet.cell(row=row, column=col_num)
                    for prefix, fill in cond_formatting.items():
                        if prefix in str(cell.value):
                            cell.fill = fill
                            break

            for column in worksheet.columns:
                max_length = 0
                column_letter = get_column_letter(column[0].column)
                if column_letter in ['Q', 'R', 'S', 'T']:
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

            worksheet.column_dimensions['A'].width = 12
            worksheet.column_dimensions['B'].width = 30
            worksheet.column_dimensions['C'].width = 20
            worksheet.column_dimensions['D'].width = 12
            worksheet.column_dimensions['E'].width = 15

            worksheet.freeze_panes = 'C4'

            workbook.save(EXCEL_FILE)
            return EXCEL_FILE
    except Exception as e:
        print(f"Error saving Excel file: {e}")
        return None

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

def highlight_status(val):
    """Highlight status cells based on their value"""
    if "▲▲" in str(val):
        return 'background-color: #008000; color: white'
    elif "▼▼" in str(val):
        return 'background-color: #FF0000; color: white'
    elif "–" in str(val):
        return 'background-color: #D9D9D9; color: black'
    elif "Upper Circuit Breaker" in str(val):
        return 'background-color: #FFD700; color: black'
    elif "Lower Circuit Breaker" in str(val):
        return 'background-color: #A52A2A; color: white'
    return ''

def load_data():
    """Load and return the data"""
    global loaded_data

    symbols_data = get_symbols_data()
    if not symbols_data:
        return None, None, None, None, None, None, None, None, gr.update(choices=["All"])

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
        print("❌ No market data found")
        return None, None, None, None, None, None, None, None, gr.update(choices=["All"])

    today_data = today_data[today_data['SYMBOL'].apply(lambda x: is_valid_symbol(x, symbols_data))].copy()
    if today_data.empty:
        print("⚠️ No valid symbols found")
        return None, None, None, None, None, None, None, None, gr.update(choices=["All"])

    target_date = datetime.strptime(today_date, "%Y-%m-%d")

    prev_day_data = None
    days_back = 1
    while days_back <= MAX_DAYS_BACK and prev_day_data is None:
        prev_day_date = target_date - timedelta(days=days_back)
        if not is_weekend(prev_day_date):
            prev_day_data, _ = fetch_market_data(prev_day_date)
            if prev_day_data is not None:
                break
        days_back += 1

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
    prev_week_data = pd.concat(all_week_data) if all_week_data else None

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
    prev_month_data = pd.concat(all_month_data) if all_month_data else None

    result_df = calculate_breakout_stats(today_data, prev_day_data, prev_week_data, prev_month_data, symbols_data)
    loaded_data = result_df
    excel_file = save_to_excel(result_df, today_date)

    daily_counts = get_counts(result_df, 'DAILY_STATUS')
    weekly_counts = get_counts(result_df, 'WEEKLY_STATUS')
    monthly_counts = get_counts(result_df, 'MONTHLY_STATUS')

    fig_daily = create_pie_chart(daily_counts, "Daily Breakout Distribution")
    fig_weekly = create_pie_chart(weekly_counts, "Weekly Breakout Distribution")
    fig_monthly = create_pie_chart(monthly_counts, "Monthly Breakout Distribution")

    daily_table = pd.DataFrame.from_dict(daily_counts, orient='index').reset_index()
    weekly_table = pd.DataFrame.from_dict(weekly_counts, orient='index').reset_index()
    monthly_table = pd.DataFrame.from_dict(monthly_counts, orient='index').reset_index()

    styled_df = result_df.style.map(highlight_status, subset=['DAILY_STATUS', 'WEEKLY_STATUS', 'MONTHLY_STATUS', 'CIRCUIT_BREAKER_STATUS'])

    sectors = ["All"] + sorted(result_df['SECTOR'].unique().tolist())

    return (
        excel_file,
        styled_df,
        fig_daily,
        fig_weekly,
        fig_monthly,
        daily_table,
        weekly_table,
        monthly_table,
        gr.update(choices=sectors, value="All")
    )

def filter_data(filter_breakout, filter_sector, filter_kmi, filter_circuit_breaker, filter_symbols):
    """Filter data based on user selections"""
    global loaded_data

    if loaded_data is None:
        return gr.DataFrame()

    df = loaded_data.copy()

    if filter_breakout:
        df = df[(df['DAILY_STATUS'].str.contains("▲▲")) &
                (df['WEEKLY_STATUS'].str.contains("▲▲")) &
                (df['MONTHLY_STATUS'].str.contains("▲▲"))]

    if filter_sector != "All":
        df = df[df['SECTOR'] == filter_sector]

    if filter_kmi != "All":
        df = df[df['KMI_COMPLIANT'] == filter_kmi]

    if filter_circuit_breaker != "All":
        if filter_circuit_breaker == "Upper Circuit Breaker":
            df = df[df['CIRCUIT_BREAKER_STATUS'] == "Upper Circuit Breaker"]
        elif filter_circuit_breaker == "Lower Circuit Breaker":
            df = df[df['CIRCUIT_BREAKER_STATUS'] == "Lower Circuit Breaker"]

    if filter_symbols:
        symbols = [symbol.strip().upper() for symbol in filter_symbols.split(',')]
        df = df[df['SYMBOL'].isin(symbols)]

    styled_df = df.style.map(highlight_status, subset=['DAILY_STATUS', 'WEEKLY_STATUS', 'MONTHLY_STATUS', 'CIRCUIT_BREAKER_STATUS'])
    return styled_df

def is_valid_symbol(symbol, symbols_data):
    """Check if symbol is valid and not a futures contract"""
    try:
        symbol = symbol.strip().upper()
        return (symbol in symbols_data) and not any(month in symbol for month in MONTH_CODES)
    except:
        return False

def is_weekend(date):
    """Check if date is weekend (Saturday/Sunday)"""
    return date.weekday() >= 5

# Gradio Interface
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

    dataframe = gr.DataFrame(interactive=False, wrap=True)

    with gr.Row():
        with gr.Column():
            gr.Markdown("### Daily Analysis")
            daily_plot = gr.Plot()
            daily_table = gr.DataFrame(headers=["Status", "Count"])

        with gr.Column():
            gr.Markdown("### Weekly Analysis")
            weekly_plot = gr.Plot()
            weekly_table = gr.DataFrame(headers=["Status", "Count"])

        with gr.Column():
            gr.Markdown("### Monthly Analysis")
            monthly_plot = gr.Plot()
            monthly_table = gr.DataFrame(headers=["Status", "Count"])

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
