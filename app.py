import os
import requests
import pandas as pd
import numpy as np
import yfinance as yf
import mplfinance as mpf
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import datetime
import gradio as gr
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

# Function to fetch KSE-100 index data with fallback
def fetch_kse100_data():
    try:
        # Try new URL format
        url = "https://dps.psx.com.pk/market-summary"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()  # Raise exception for bad status codes
        
        tables = pd.read_html(response.text)
        if tables:
            kse100_table = tables[0]
            # Handle multi-level columns if exists
            if isinstance(kse100_table.columns, pd.MultiIndex):
                kse100_table.columns = kse100_table.columns.droplevel(0)
            return kse100_table
    except Exception as e:
        print(f"Error fetching KSE-100 data: {e}")
    
    # Fallback to using Yahoo Finance for KSE-100
    try:
        kse = yf.Ticker("^KSE")
        data = kse.history(period="1d")
        if not data.empty:
            kse100_table = pd.DataFrame({
                'Symbol': ['KSE100'],
                'Current': [data['Close'].iloc[-1]],
                'Change%': [0.0]  # Placeholder
            })
            return kse100_table
    except Exception as e:
        print(f"Error fetching KSE-100 from Yahoo: {e}")
    
    # Return empty dataframe if all fails
    return pd.DataFrame(columns=['Symbol', 'Current', 'Change%'])

# Function to fetch stock data with enhanced error handling
def fetch_stock_data(stock_name, period, interval):
    try:
        end_date = datetime.today()
        
        # Period to date mapping
        period_map = {
            '1d': (end_date - timedelta(days=1), '5m'),
            '5d': (end_date - timedelta(days=5), '30m'),
            '1mo': (end_date - relativedelta(months=1), '1h'),
            '6mo': (end_date - relativedelta(months=6), '1d'),
            '1y': (end_date - relativedelta(years=1), '1d'),
            '5y': (end_date - relativedelta(years=5), '1wk'),
            'max': (datetime(2000, 1, 1), '1mo'),
        }
        
        start_date, interval = period_map.get(period, (end_date - relativedelta(years=1), '1d'))
        
        # Try with .PA suffix (Pakistan market)
        stock = yf.Ticker(f"{stock_name}.PA")
        data = stock.history(start=start_date, end=end_date, interval=interval)
        
        # If no data, try without suffix
        if data.empty:
            stock = yf.Ticker(stock_name)
            data = stock.history(start=start_date, end=end_date, interval=interval)
        
        if data.empty:
            return None, f"No data found for {stock_name}"
        
        return data, None
    except Exception as e:
        return None, f"Error fetching data: {str(e)}"

# Function to create candlestick chart
def create_candlestick_chart(data, stock_name):
    try:
        fig, ax = plt.subplots(figsize=(10, 6))
        
        # Create candlestick chart
        mpf.plot(data, type='candle', style='charles', 
                 title=f'{stock_name} Price', 
                 ylabel='Price (PKR)', 
                 ax=ax, 
                 show_nontrading=True)
        
        # Format dates on x-axis
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
        plt.xticks(rotation=45)
        plt.tight_layout()
        
        return fig
    except Exception as e:
        print(f"Error creating chart: {e}")
        return None

# Main function to process stock information
def get_stock_info(stock_name, period, interval):
    # Fetch stock data
    data, error = fetch_stock_data(stock_name, period, interval)
    if error:
        return error, None, None
    
    # Create candlestick chart
    fig = create_candlestick_chart(data, stock_name)
    
    # Calculate additional metrics
    try:
        latest_close = data['Close'].iloc[-1]
        previous_close = data['Close'].iloc[-2] if len(data) > 1 else latest_close
        price_change = latest_close - previous_close
        percent_change = (price_change / previous_close) * 100
    except Exception as e:
        error_msg = f"Error calculating metrics: {str(e)}"
        return error_msg, fig, None
    
    # Create metrics HTML
    metrics_html = f"""
    <div style="font-family: Arial, sans-serif; padding: 20px; background-color: #f0f0f0; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
        <h2 style="color: #333; border-bottom: 2px solid #666; padding-bottom: 10px;">{stock_name} Metrics</h2>
        <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 15px;">
            <div style="background-color: white; padding: 15px; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1);">
                <h3 style="margin-top: 0; color: #555;">Current Price</h3>
                <p style="font-size: 24px; font-weight: bold; color: #222;">PKR {latest_close:.2f}</p>
            </div>
            <div style="background-color: white; padding: 15px; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1);">
                <h3 style="margin-top: 0; color: #555;">Price Change</h3>
                <p style="font-size: 24px; font-weight: bold; color: {'green' if price_change >= 0 else 'red'};">{price_change:.2f} ({percent_change:.2f}%)</p>
            </div>
        </div>
    </div>
    """
    
    # Create recent data table
    try:
        recent_data = data.tail(10).reset_index()
        if 'Date' in recent_data.columns:
            recent_data['Date'] = recent_data['Date'].dt.strftime('%Y-%m-%d')
        recent_data = recent_data[['Date', 'Open', 'High', 'Low', 'Close', 'Volume']]
    except Exception as e:
        print(f"Error preparing recent data: {e}")
        recent_data = pd.DataFrame()
    
    return metrics_html, fig, recent_data

# Function to get top gainers with fallback
def get_top_gainers():
    try:
        kse100_table = fetch_kse100_data()
        if not kse100_table.empty and 'Change%' in kse100_table.columns:
            top_gainers = kse100_table.nlargest(10, 'Change%')
            return top_gainers[['Symbol', 'Current', 'Change%']]
        
        # Fallback to static data
        return pd.DataFrame({
            'Symbol': ['MTL', 'HBL', 'UBL', 'ENGRO', 'PPL'],
            'Current': [100.25, 150.75, 200.50, 300.00, 75.80],
            'Change%': [5.2, 4.8, 3.5, 2.9, 1.7]
        })
    except Exception as e:
        print(f"Error getting top gainers: {e}")
        return pd.DataFrame(columns=['Symbol', 'Current', 'Change%'])

# Function to get top losers with fallback
def get_top_losers():
    try:
        kse100_table = fetch_kse100_data()
        if not kse100_table.empty and 'Change%' in kse100_table.columns:
            top_losers = kse100_table.nsmallest(10, 'Change%')
            return top_losers[['Symbol', 'Current', 'Change%']]
        
        # Fallback to static data
        return pd.DataFrame({
            'Symbol': ['OGDC', 'PTC', 'FCCL', 'KAPCO', 'NRL'],
            'Current': [95.25, 45.75, 120.50, 55.00, 85.80],
            'Change%': [-3.2, -2.8, -2.5, -1.9, -1.2]
        })
    except Exception as e:
        print(f"Error getting top losers: {e}")
        return pd.DataFrame(columns=['Symbol', 'Current', 'Change%'])

# Gradio interface with enhanced error handling
with gr.Blocks(title="Pakistan Stock Exchange Analysis", theme=gr.themes.Soft()) as demo:
    gr.Markdown("# 🇵🇰 Pakistan Stock Exchange Analysis")
    gr.Markdown("Track PSX stocks, analyze performance, and discover market trends")
    
    with gr.Row():
        stock_input = gr.Textbox(label="Stock Symbol", placeholder="Enter stock symbol (e.g. MTL)", value="MTL")
        period = gr.Dropdown(label="Time Period", choices=['1d', '5d', '1mo', '6mo', '1y', '5y', 'max'], value='1y')
        interval = gr.Dropdown(label="Interval", choices=['5m', '15m', '30m', '1h', '1d', '1wk', '1mo'], value='1d')
        submit_btn = gr.Button("Analyze Stock", variant="primary")
    
    metrics_output = gr.HTML(label="Stock Metrics")
    chart_output = gr.Plot(label="Price Chart")
    data_output = gr.DataFrame(label="Recent Data", headers=['Date', 'Open', 'High', 'Low', 'Close', 'Volume'])
    
    with gr.Row():
        with gr.Column():
            gr.Markdown("## 📈 Top Gainers")
            gainers_output = gr.DataFrame(label="Top Gainers", headers=['Symbol', 'Current', 'Change%'])
        with gr.Column():
            gr.Markdown("## 📉 Top Losers")
            losers_output = gr.DataFrame(label="Top Losers", headers=['Symbol', 'Current', 'Change%'])
    
    # Event handlers
    submit_btn.click(
        fn=get_stock_info,
        inputs=[stock_input, period, interval],
        outputs=[metrics_output, chart_output, data_output]
    )
    
    # Initial data loading
    demo.load(
        fn=get_top_gainers,
        inputs=[],
        outputs=[gainers_output]
    )
    
    demo.load(
        fn=get_top_losers,
        inputs=[],
        outputs=[losers_output]
    )

# Install required packages if not found
def install_required_packages():
    import sys
    import subprocess
    import importlib

    required_packages = {
        'yfinance': 'yfinance',
        'mplfinance': 'mplfinance',
        'dateutil': 'python-dateutil',
        'gradio': 'gradio',
        'pandas': 'pandas',
        'requests': 'requests',
        'matplotlib': 'matplotlib'
    }

    for package_name, install_name in required_packages.items():
        try:
            importlib.import_module(package_name)
        except ImportError:
            print(f"Installing missing package: {install_name}")
            subprocess.check_call([sys.executable, "-m", "pip", "install", install_name])

# Check and install packages before launching
if __name__ == "__main__":
    install_required_packages()
    try:
        demo.launch()
    except Exception as e:
        print(f"Error launching app: {e}")
        print("Please check the logs and try again")