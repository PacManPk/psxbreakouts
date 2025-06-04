import requests
import pandas as pd
from datetime import datetime
import os
from openpyxl import load_workbook
from openpyxl.styles import Font, Alignment
from openpyxl import Workbook
from io import StringIO
from pytz import timezone
from openpyxl.utils.dataframe import dataframe_to_rows  # Import this function

# Configuration
PSX_STOCK_DATA_URL = 'https://docs.google.com/spreadsheets/d/1wGpkG37p2GV4aCckLYdaznQ4FjlQog8E/export?format=csv'
EXCEL_FILE = '/tmp/PSX_Breakout_Scanner.xlsx'  # Using /tmp for Hugging Face
MONTH_CODES = ['-JAN', '-FEB', '-MAR', '-APR', '-MAY', '-JUN', '-JUL', '-AUG', '-SEP', '-OCT', '-NOV', '-DEC']

def debug_print(message, important=False):
    """Print messages with timestamp"""
    timestamp = datetime.now(timezone('Asia/Karachi')).strftime('%Y-%m-%d %H:%M:%S')
    if important:
        print(f"[{timestamp}] 🇵🇰 {message}")

def save_to_excel(df, report_date):
    """Modified for Hugging Face compatibility"""
    try:
        # Ensure directory exists
        os.makedirs(os.path.dirname(EXCEL_FILE), exist_ok=True)

        # Create new workbook if file doesn't exist
        if not os.path.exists(EXCEL_FILE):
            workbook = Workbook()
            worksheet = workbook.active
            worksheet.title = 'Breakout Analysis'
        else:
            workbook = load_workbook(EXCEL_FILE)
            if 'Breakout Analysis' in workbook.sheetnames:
                worksheet = workbook['Breakout Analysis']
            else:
                worksheet = workbook.active
                worksheet.title = 'Breakout Analysis'

        # Write data to Excel (simple example for writing data)
        for row in dataframe_to_rows(df, index=False, header=True):
            worksheet.append(row)

        # Apply basic styling to the header row
        for cell in worksheet[1]:
            cell.font = Font(bold=True)
            cell.alignment = Alignment(horizontal='center')

        workbook.save(EXCEL_FILE)
        debug_print(f"✅ Report saved: {EXCEL_FILE}", important=True)

        # Return the file path for Hugging Face to display
        return EXCEL_FILE

    except Exception as e:
        debug_print(f"❌ Error saving Excel file: {e}", important=True)
        return None

def download_stock_data():
    """Download stock data from PSX or Google Sheets"""
    try:
        response = requests.get(PSX_STOCK_DATA_URL)
        if response.status_code == 200:
            df = pd.read_csv(StringIO(response.text))

            # Debug print the first few rows of the DataFrame
            debug_print(f"✅ Stock data downloaded successfully: {df.head()}", important=True)

            # Check if the required column 'Symbol' exists in the DataFrame
            if 'Symbol' not in df.columns:
                debug_print("❌ 'Symbol' column not found in the stock data", important=True)
                return None

            return df
        else:
            debug_print("❌ Failed to download stock data", important=True)
            return None
    except Exception as e:
        debug_print(f"❌ Error downloading stock data: {e}", important=True)
        return None

def process_data(df):
    """Process the stock data for analysis"""
    # Here, you should add your own logic to process the stock data
    if df is None or df.empty:
        debug_print("❌ DataFrame is empty or invalid.", important=True)
        return None
    
    # Sample logic: Adding Date and Analysis columns
    df['Date'] = datetime.now().strftime('%Y-%m-%d')
    df['Analysis'] = df['Symbol'].apply(lambda x: 'Buy' if x.startswith('K') else 'Sell')  # Dummy analysis logic
    return df

def main():
    debug_print("🔍 Starting PSX Breakout Scanner", important=True)
    
    try:
        # Step 1: Download stock data
        stock_df = download_stock_data()
        
        if stock_df is None:
            debug_print("❌ No stock data available", important=True)
            return
        
        # Step 2: Process data
        result_df = process_data(stock_df)
        
        if result_df is None:
            debug_print("❌ Processed data is empty or invalid", important=True)
            return
        
        # Step 3: Save the processed data to Excel
        today_date = datetime.now().strftime('%Y-%m-%d')
        result_file = save_to_excel(result_df, today_date)
        
        if result_file:
            debug_print(f"Analysis complete. File available at: {result_file}", important=True)
        else:
            debug_print("Analysis completed but file could not be saved", important=True)
            
    except Exception as e:
        debug_print(f"❌ Fatal error: {str(e)}", important=True)

if __name__ == "__main__":
    # Simplified entry point for Hugging Face
    main()
