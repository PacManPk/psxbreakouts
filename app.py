import requests
import pandas as pd
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import os
from openpyxl import load_workbook
from openpyxl.utils import get_column_letter
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.chart import PieChart, Reference
from openpyxl.chart.label import DataLabelList
from openpyxl import Workbook
from io import StringIO
from IPython.display import display, HTML
from pytz import timezone

# Configuration
PSX_HISTORICAL_URL = 'https://dps.psx.com.pk/historical'
EXCEL_FILE = 'PSX Scanner/PSX Breakout Scanner by Nisar Ahmed V2.xlsx'
PSX_STOCK_DATA_URL = 'https://docs.google.com/spreadsheets/d/1wGpkG37p2GV4aCckLYdaznQ4FjlQog8E/export?format=csv'
KMI_SYMBOLS_FILE = 'https://drive.google.com/uc?export=download&id=1Lf24EnwxUV3l64Y6i_XO-JoP0CEY-tuB'
MONTH_CODES = ['-JAN', '-FEB', '-MAR', '-APR', '-MAY', '-JUN',
               '-JUL', '-AUG', '-SEP', '-OCT', '-NOV', '-DEC']
MAX_DAYS_BACK = 5


def get_symbols_data():
    """Load symbol data from both PSX stock data and KMI compliance files"""
    try:

        # Load PSX Stock Data
        debug_print("Fetching symbol data...")
        psx_response = requests.get(PSX_STOCK_DATA_URL)
        psx_response.raise_for_status()
        psx_df = pd.read_csv(StringIO(psx_response.text))

        # Verify required columns
        psx_required = ['Symbol', 'Company Name', 'Sector']
        for col in psx_required:
            if col not in psx_df.columns:
                raise ValueError(f"Missing column: {col}")

        # Load KMI compliance data
        debug_print("Fetching KMI compliance data...")
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

def debug_print(message, important=False):
    """Only print important messages unless debugging is needed"""
    if important:
        print(f"🇵🇰 {message}")

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
    debug_print("Calculating breakout statistics...")
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

def create_stats_dashboard(worksheet, df, start_col):
    """Create a stats dashboard with pie charts and summary tables"""
    debug_print("Creating dashboard...")

    def get_counts(status_col):
        counts = {
            "Breakout": len(df[df[status_col].str.contains("▲▲")]),
            "Breakdown": len(df[df[status_col].str.contains("▼▼")]),
            "Within Range": len(df[df[status_col].str.contains("–")])
        }
        return counts

    daily_counts = get_counts('DAILY_STATUS')
    weekly_counts = get_counts('WEEKLY_STATUS')
    monthly_counts = get_counts('MONTHLY_STATUS')

    # Border and Fill styles
    thin_border = Border(
        left=Side(style='thin'),
        right=Side(style='thin'),
        top=Side(style='thin'),
        bottom=Side(style='thin')
    )
    blue_fill = PatternFill(start_color='ADD8E6', end_color='ADD8E6', fill_type='solid')
    header_fill = PatternFill(start_color='4F81BD', end_color='4F81BD', fill_type='solid')
    header_font = Font(bold=True, color="FFFFFF")

    def write_summary_table(title, counts, start_row, start_col):
        # Merge and format title cell
        worksheet.merge_cells(start_row=start_row, start_column=start_col,
                            end_row=start_row, end_column=start_col+1)
        title_cell = worksheet.cell(row=start_row, column=start_col, value=title)
        title_cell.font = header_font
        title_cell.fill = header_fill
        title_cell.alignment = Alignment(horizontal='center')
        title_cell.border = thin_border

        # Headers
        worksheet.cell(row=start_row+1, column=start_col, value="Category").font = Font(bold=True)
        worksheet.cell(row=start_row+1, column=start_col+1, value="Count").font = Font(bold=True)
        worksheet.cell(row=start_row+1, column=start_col).border = thin_border
        worksheet.cell(row=start_row+1, column=start_col+1).border = thin_border

        # Data rows
        for i, (category, count) in enumerate(counts.items(), start=2):
            cat_cell = worksheet.cell(row=start_row+i, column=start_col, value=category)
            count_cell = worksheet.cell(row=start_row+i, column=start_col+1, value=count)
            cat_cell.border = thin_border
            count_cell.border = thin_border

    # DAILY Summary (Z8)
    write_summary_table("DAILY SUMMARY", daily_counts, 8, 26)

    # WEEKLY Summary (Z24)
    write_summary_table("WEEKLY SUMMARY", weekly_counts, 24, 26)

    # MONTHLY Summary (Z38)
    write_summary_table("MONTHLY SUMMARY", monthly_counts, 38, 26)

    # Pie chart function
    def create_pie_chart(title, data_row, anchor_cell):
        pie = PieChart()
        labels = Reference(worksheet, min_col=26, min_row=data_row, max_row=data_row+2)
        data = Reference(worksheet, min_col=27, min_row=data_row-1, max_row=data_row+2)
        pie.add_data(data, titles_from_data=True)
        pie.set_categories(labels)
        pie.title = title
        pie.height = 7
        pie.width = 7
        pie.dataLabels = DataLabelList()
        pie.dataLabels.showPercent = True
        worksheet.add_chart(pie, anchor_cell)

    # Place pie charts
    create_pie_chart("Daily", 10, "U4")
    create_pie_chart("Weekly", 26, "U19")
    create_pie_chart("Monthly", 40, "U36")

def save_to_excel(df, report_date):
    """Save the results to an Excel file with formatting"""
    try:
        os.makedirs(os.path.dirname(EXCEL_FILE), exist_ok=True)

        workbook = load_workbook(EXCEL_FILE) if os.path.exists(EXCEL_FILE) else Workbook()
        if 'Sheet' in workbook.sheetnames:
            worksheet = workbook['Sheet']
        else:
            worksheet = workbook.active
            worksheet.title = 'Breakout Analysis'

        # Clear existing data
        worksheet.delete_rows(1, worksheet.max_row)

        formatted_date = datetime.strptime(report_date, "%Y-%m-%d").strftime("%d %B %Y")

        # Main title (row 1)
        worksheet.merge_cells('A1:S1')
        title_cell = worksheet.cell(row=1, column=1, value=f"📈 PSX Breakout/Breakdown Analysis - {formatted_date}")
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

        # Write headers (starting at row 3)
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

        # Write data (starting at row 4)
        for row_idx, row_data in enumerate(df.values, 4):
            for col_idx, value in enumerate(row_data, 1):
                worksheet.cell(row=row_idx, column=col_idx, value=value)

        # Apply conditional formatting
        status_cols = {
            17: 'DAILY_STATUS',  # Column Q
            18: 'WEEKLY_STATUS', # Column R
            19: 'MONTHLY_STATUS' # Column S
        }

        cond_formatting = {
            "▲▲": PatternFill(start_color="008000", fill_type="solid"),  # Green
            "▲": PatternFill(start_color="92D050", fill_type="solid"),    # Light Green
            "▼▼": PatternFill(start_color="FF0000", fill_type="solid"),   # Red
            "▼": PatternFill(start_color="FFC7CE", fill_type="solid"),    # Light Red
            "–": PatternFill(start_color="D9D9D9", fill_type="solid")      # Gray
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

            # Set fixed width for status columns
            if column_letter in ['Q', 'R', 'S']:
                worksheet.column_dimensions[column_letter].width = 18  # Slightly wider for status
                continue

            for cell in column:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            adjusted_width = (max_length + 2) * 1.1
            worksheet.column_dimensions[column_letter].width = adjusted_width

        # Manual adjustments for specific columns
        worksheet.column_dimensions['A'].width = 12  # SYMBOL
        worksheet.column_dimensions['B'].width = 30  # COMPANY
        worksheet.column_dimensions['C'].width = 20  # SECTOR
        worksheet.column_dimensions['D'].width = 12  # KMI_COMPLIANT
        worksheet.column_dimensions['E'].width = 15  # VOLUME

        # Freeze first 2 columns
        worksheet.freeze_panes = 'C4'

        # Create stats dashboard with pie charts
        create_stats_dashboard(worksheet, df, start_col=21)

        workbook.save(EXCEL_FILE)
        debug_print(f"✅ Report saved: {EXCEL_FILE}", important=True)

        # For Google Colab - display download link
        if 'google.colab' in str(get_ipython()):
            from google.colab import files
            files.download(EXCEL_FILE)
            display(HTML(f'<a href="{EXCEL_FILE}" download>Download Excel File</a>'))

    except Exception as e:
        debug_print(f"❌ Error saving Excel file: {e}", important=True)


def main():
    debug_print("🔍 Scanning PSX for Breakout 📈📉", important=True)

    # Step 1: Get symbols data
    debug_print("Loading market data...", important=True)
    symbols_data = get_symbols_data()
    if not symbols_data:
        return

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
        debug_print("❌ Error: No market data found for past {} days".format(MAX_DAYS_BACK), important=True)
        return

    # Filter for valid symbols only
    today_data = today_data[today_data['SYMBOL'].apply(lambda x: is_valid_symbol(x, symbols_data))].copy()
    if today_data.empty:
        debug_print("⚠️ Warning: No valid symbols found in the data", important=True)
        return

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
                debug_print(f"Sample of previous day data:\n{prev_day_data.head()}", important=True)
        days_back += 1

    # Previous week and month data
    prev_week_data = get_previous_week_data(target_date)
    prev_month_data = get_previous_month_data(target_date)

    # Step 4: Calculate breakout stats
    debug_print("Analyzing breakouts...", important=True)
    result_df = calculate_breakout_stats(today_data, prev_day_data, prev_week_data, prev_month_data, symbols_data)

    # Step 5: Save results
    save_to_excel(result_df, today_date)
    debug_print("Analysis completed", important=True)


if __name__ == "__main__":
    # Check if running in Google Colab
    try:
        from google.colab import drive
        IN_COLAB = True
    except:
        IN_COLAB = False

    if IN_COLAB:
        debug_print("Running in Google Colab", important=True)

    main()