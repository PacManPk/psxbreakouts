import requests
import pandas as pd
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import gradio as gr
from pytz import timezone

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

def is_valid_symbol(symbol, symbols_data):
    """Check if symbol is valid and not a futures contract"""
    try:
        symbol = symbol.strip().upper()
        return (symbol in symbols_data) and not any(month in symbol for month in MONTH_CODES)
    except:
        return False

def is_weekend(date):
    """Check if date is weekend (Saturday/Sunday)"""
    return date.weekday() >= 5  # Saturday=5, Sunday=6

def fetch_market_data(date):
    """Fetch market data from PSX historical page for specific date"""
    try:
        date_str = date.strftime('%Y-%m-%d')
        response = requests.post(PSX_HISTORICAL_URL, data={'date': date_str}, timeout=30)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, 'html.parser')
        rows = soup.find_all('tr')

        if len(rows) <= 1:
            return None, None

        data = []
        for row in rows[1:]:  # Skip header row
            cells = [cell.text.strip() for cell in row.find_all('td')]
            if len(cells) >= 9:  # Now checking for 9 columns
                # Process volume - now from 9th column (index 8)
                raw_volume = cells[8]
                try:
                    # Handle cases where volume might be empty, "-", or "0"
                    volume = int(raw_volume.replace(',', '')) if raw_volume and raw_volume != '-' else 0
                except ValueError:
                    volume = 0  # Fallback for any unexpected format

                data.append([
                    cells[0],  # SYMBOL (1st column)
                    cells[1],  # LDCP (2nd column)
                    cells[2],  # OPEN (3rd column)
                    cells[3],  # HIGH (4th column)
                    cells[4],  # LOW (5th column)
                    cells[5],  # CLOSE (6th column)
                    str(volume)  # VOLUME (now from 9th column)
                ])

        if data:
            df = pd.DataFrame(data, columns=['SYMBOL', 'LDCP', 'OPEN', 'HIGH', 'LOW', 'CLOSE', 'VOLUME'])
            return df, date_str

        return None, None
    except Exception as e:
        debug_print(f"❌ Error fetching data: {str(e)}", important=True)
        return None, None

def get_previous_week_data(target_date):
    """Get data for the previous calendar week (Monday to Friday)"""
    # Find the previous Monday (start of previous week)
    prev_monday = target_date - timedelta(days=target_date.weekday() + 7)
    prev_friday = prev_monday + timedelta(days=4)

    debug_print(f"Fetching Previous Week data ({prev_monday.strftime('%d %b %y')} to {prev_friday.strftime('%d %b %y')})", important=True)

    all_data = []
    current_date = prev_monday
    while current_date <= prev_friday:
        if not is_weekend(current_date):
            data, _ = fetch_market_data(current_date)
            if data is not None:
                all_data.append(data)
        current_date += timedelta(days=1)

    if all_data:
        return pd.concat(all_data)
    return None

def get_previous_month_data(target_date):
    """Get data for the previous calendar month"""
    # First day of previous month
    first_day_prev_month = (target_date.replace(day=1) - timedelta(days=1))
    first_day_prev_month = first_day_prev_month.replace(day=1)

    # Last day of previous month
    last_day_prev_month = (target_date.replace(day=1) - timedelta(days=1))

    debug_print(f"Fetching Previous Month data ({first_day_prev_month.strftime('%d %b %y')} to {last_day_prev_month.strftime('%d %b %y')})", important=True)

    all_data = []
    current_date = first_day_prev_month
    while current_date <= last_day_prev_month:
        if not is_weekend(current_date):
            data, _ = fetch_market_data(current_date)
            if data is not None:
                all_data.append(data)
        current_date += timedelta(days=1)

    if all_data:
        return pd.concat(all_data)
    return None

def calculate_breakout_stats(today_data, prev_day_data, prev_week_data, prev_month_data, symbols_data):
    """Calculate breakout statuses using proper weekly/monthly periods"""
    debug_print("Calculating breakout statistics...", important=True)
    results = []

    for _, today_row in today_data.iterrows():
        symbol = today_row['SYMBOL']

        # Get company info from symbols data
        company_info = symbols_data.get(symbol, {})
        company_name = company_info.get('Company', symbol)
        sector = company_info.get('Sector', 'N/A')
        kmi_status = company_info.get('KMI', 'No')

        # Initialize variables with default values
        today_close = today_high = today_low = today_ldcp = volume = 0
        prev_day_high = prev_day_low = weekly_high = weekly_low = monthly_high = monthly_low = "N/A"
        daily_status = "N/A"
        weekly_status = "N/A"
        monthly_status = "N/A"

        # Parse numerical values with error handling
        try:
            today_close = float(today_row['CLOSE'].replace(',', '')) if today_row['CLOSE'] else 0
            today_high = float(today_row['HIGH'].replace(',', '')) if today_row['HIGH'] else 0
            today_low = float(today_row['LOW'].replace(',', '')) if today_row['LOW'] else 0
            today_ldcp = float(today_row['LDCP'].replace(',', '')) if today_row['LDCP'] else 0

            # Process volume data - handle empty/missing values
            if today_row['VOLUME'] and str(today_row['VOLUME']).strip():
                volume = float(str(today_row['VOLUME']).replace(',', ''))
                volume_str = f"{volume:,.0f}"  # Format with commas for display
            else:
                volume_str = "0"
        except Exception as e:
            debug_print(f"⚠️ Error processing numerical values for {symbol}: {str(e)}")
            continue

        # Daily breakout (vs previous day)
        if prev_day_data is not None:
            prev_day_row = prev_day_data[prev_day_data['SYMBOL'].str.upper() == symbol.upper()]
            debug_print(f"Checking {symbol} - Found {len(prev_day_row)} matching rows in previous day data", important=True)

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
                    debug_print(f"⚠️ Error processing previous day data for {symbol}: {str(e)}")
                    daily_status = "– Daily Data Error"

        # Weekly breakout (previous calendar week)
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
                    debug_print(f"⚠️ Error processing weekly data for {symbol}: {str(e)}")
                    weekly_status = "– Weekly Data Error"

        # Monthly breakout (previous calendar month)
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
                    debug_print(f"⚠️ Error processing monthly data for {symbol}: {str(e)}")
                    monthly_status = "– Monthly Data Error"

        # Fallback to LDCP comparison if no history
        if daily_status == "N/A":
            try:
                if today_close > today_ldcp:
                    daily_status = "▲▲ Daily Breakout"  # Any close > LDCP = Breakout
                elif today_close < today_ldcp:
                    daily_status = "▼▼ Daily Breakdown"  # Any close < LDCP = Breakdown
                else:
                    daily_status = "– Daily Within Range"  # Only if close == LDCP
            except:
                daily_status = "– No Data"  # Fallback on error

        # Format numerical values for display
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

def run_analysis():
    """Run the PSX Breakout Scanner analysis and return results"""
    debug_print("🔍 Scanning PSX for Breakout 📈📉", important=True)

    # Step 1: Get symbols data
    debug_print("Loading market data...", important=True)
    symbols_data = get_symbols_data()
    if not symbols_data:
        return None, "Error: Could not load symbols data"

    # Step 2: Find most recent trading day with data
    date_to_try = datetime.now()
    attempts = 0
    today_data, today_date = None, None

    while attempts < MAX_DAYS_BACK and today_data is None:
        if not is_weekend(date_to_try):
            debug_print(f"🔎 Checking market data for {date_to_try.strftime('%d %b %Y (%a)')}", important=True)
            today_data, today_date = fetch_market_data(date_to_try)
            if today_data is not None:
                debug_print(f"✅ Found market data for {date_to_try.strftime('%d %b %Y (%a)')}", important=True)
                break
            else:
                debug_print(f"⚠️ No data available for {date_to_try.strftime('%d %b %Y (%a)')} - Possible holiday", important=True)
        else:
            debug_print(f"⏸️ {date_to_try.strftime('%d %b %Y (%a)')} - Market closed (weekend)", important=True)

        date_to_try -= timedelta(days=1)
        attempts += 1

    if today_data is None:
        return None, f"Error: No market data found for past {MAX_DAYS_BACK} days"

    # Filter for valid symbols only
    today_data = today_data[today_data['SYMBOL'].apply(lambda x: is_valid_symbol(x, symbols_data))].copy()
    if today_data.empty:
        return None, "Warning: No valid symbols found in the data"

    # Step 3: Get historical data
    target_date = datetime.strptime(today_date, "%Y-%m-%d")

    # Previous day data - keep looking back until we find data or hit MAX_DAYS_BACK
    prev_day_data = None
    days_back = 1
    while days_back <= MAX_DAYS_BACK and prev_day_data is None:
        prev_day_date = target_date - timedelta(days=days_back)
        if not is_weekend(prev_day_date):
            debug_print(f"Fetching Previous Day data for {prev_day_date.strftime('%d %b %Y')}", important=True)
            prev_day_data, _ = fetch_market_data(prev_day_date)
            if prev_day_data is not None:
                debug_print(f"Found previous day data for {prev_day_date.strftime('%d %b %Y')}", important=True)
        days_back += 1

    # Previous week and month data
    prev_week_data = get_previous_week_data(target_date)
    prev_month_data = get_previous_month_data(target_date)

    # Step 4: Calculate breakout stats
    debug_print("Analyzing breakouts...", important=True)
    result_df = calculate_breakout_stats(today_data, prev_day_data, prev_week_data, prev_month_data, symbols_data)
    
    # Format the date for display
    formatted_date = datetime.strptime(today_date, "%Y-%m-%d").strftime("%d %B %Y")
    timestamp = datetime.now(timezone('Asia/Karachi')).strftime('%d %B %Y %H:%M:%S') + " (PKT)"
    
    return result_df, f"PSX Breakout Scanner - {formatted_date} (Generated: {timestamp})"

def create_gradio_interface():
    """Create and launch the Gradio interface"""
    with gr.Blocks(title="PSX Breakout Scanner") as demo:
        gr.Markdown("# 🇵🇰 PSX Breakout Scanner")
        gr.Markdown("This app scans the Pakistan Stock Exchange (PSX) for stocks breaking out of their recent ranges.")
        
        with gr.Row():
            run_btn = gr.Button("Run Analysis", variant="primary")
            clear_btn = gr.Button("Clear")
        
        status_output = gr.Textbox(label="Status")
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
                     "number", "number", "str", "str", "str"]
        )
        
        def run_analysis_and_display():
            status_output.value = "Running analysis... Please wait"
            df, title = run_analysis()
            if df is not None:
                return {
                    status_output: "Analysis completed successfully!",
                    title_output: title,
                    results_output: df
                }
            else:
                return {
                    status_output: title,
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
            outputs=[status_output, title_output, results_output]
        )
        
        clear_btn.click(
            fn=clear_outputs,
            outputs=[status_output, title_output, results_output]
        )
    
    return demo

if __name__ == "__main__":
    demo = create_gradio_interface()
    demo.launch()