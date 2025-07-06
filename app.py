import gradio as gr
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
from pytz import timezone
from openpyxl import Workbook
from openpyxl.utils.dataframe import dataframe_to_rows
from openpyxl.utils import get_column_letter
from openpyxl.styles import Font, Alignment, PatternFill
import tempfile
import os

from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv(".env.local")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

KMI_SYMBOLS_FILE = 'https://drive.google.com/uc?export=download&id=1Lf24EnwxUV3l64Y6i_XO-JoP0CEY-tuB'
MAX_DAYS_BACK = 5
CIRCUIT_BREAKER_PERCENTAGE = 7.5
CIRCUIT_BREAKER_RS_LIMIT = 1
loaded_data = None

def get_symbols_data():
    try:
        kmi_df = pd.read_csv(KMI_SYMBOLS_FILE)
        kmi_symbols = set()
        if 'Symbol' in kmi_df.columns:
            kmi_symbols = set(kmi_df['Symbol'].str.strip().str.upper())
        symbols_query = supabase.table("psx_stocks").select("symbol").execute()
        symbols = set([row['symbol'].strip().upper() for row in symbols_query.data])
        symbols_data = {
            sym: {
                'Company': sym,
                'Sector': 'N/A',
                'KMI': 'Yes' if sym in kmi_symbols else 'No'
            }
            for sym in symbols
        }
        return symbols_data
    except Exception as e:
        print(f"Error loading symbols data: {e}")
        return {}

def fetch_market_data(date):
    try:
        date_str = date.strftime('%Y-%m-%d')
        data = supabase.table("psx_stocks").select(
            "symbol,ldcp,open_price,high,low,close_price,volume"
        ).eq("trade_date", date_str).execute()
        if not data.data:
            return None, None
        df = pd.DataFrame(data.data)
        df.rename(columns={
            "symbol": "SYMBOL",
            "ldcp": "LDCP",
            "open_price": "OPEN",
            "high": "HIGH",
            "low": "LOW",
            "close_price": "CLOSE",
            "volume": "VOLUME"
        }, inplace=True)
        for col in ["LDCP", "OPEN", "HIGH", "LOW", "CLOSE", "VOLUME"]:
            df[col] = df[col].apply(lambda x: f"{x:,}" if pd.notnull(x) else "")
        return df, date_str
    except Exception as e:
        print(f"Error fetching data: {str(e)}")
        return None, None

def calculate_breakout_stats(today_data, prev_day_data, prev_week_data, prev_month_data, symbols_data):
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
    return {
        "Breakout": len(df[df[status_col].str.contains("▲▲")]),
        "Breakdown": len(df[df[status_col].str.contains("▼▼")]),
        "Within Range": len(df[df[status_col].str.contains("–")])
    }

def create_pie_chart(counts, title):
    df = pd.DataFrame({
        'Status': list(counts.keys()),
        'Count': list(counts.values())
    })
    fig = px.pie(df, values='Count', names='Status', title=title)
    return fig

def highlight_status(val):
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

def is_weekend(date):
    return date.weekday() >= 5

def load_data():
    global loaded_data
    symbols_data = get_symbols_data()
    if not symbols_data:
        return None, None, None, None, None
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
        return None, None, None, None, None
    if today_data.empty:
        print("⚠️ No valid symbols found")
        return None, None, None, None, None
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
    styled_df = result_df.style.applymap(highlight_status, subset=['DAILY_STATUS', 'WEEKLY_STATUS', 'MONTHLY_STATUS', 'CIRCUIT_BREAKER_STATUS'])
    return (
        styled_df,
        fig_daily,
        fig_weekly,
        fig_monthly,
        excel_file
    )

with gr.Blocks() as demo:
    gr.Markdown("# PSX Breakout Analysis (Supabase Powered)")
    with gr.Row():
        load_btn = gr.Button("Load Data")
    with gr.Row():
        data_table = gr.DataFrame(label="Breakout Table", interactive=False)
    with gr.Row():
        fig_daily = gr.Plot(label="Daily Breakout Distribution")
        fig_weekly = gr.Plot(label="Weekly Breakout Distribution")
        fig_monthly = gr.Plot(label="Monthly Breakout Distribution")
    with gr.Row():
        download_btn = gr.File(label="Download Excel Report")
    load_btn.click(
        load_data,
        inputs=[],
        outputs=[data_table, fig_daily, fig_weekly, fig_monthly, download_btn]
    )

if __name__ == "__main__":
    demo.launch()
