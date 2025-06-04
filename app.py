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

# Function to fetch KSE-100 index data
def fetch_kse100_data():
    url = "https://www.psx.com.pk/market-summary/"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'
    }
    response = requests.get(url, headers=headers)
    tables = pd.read_html(response.text)
    kse100_table = tables[0]
    kse100_table.columns = kse100_table.columns.droplevel(0)
    return kse100_table

# Function to fetch stock data
def fetch_stock_data(stock_name, period, interval):
    end_date = datetime.today()
    
    if period == '1d':
        start_date = end_date - timedelta(days=1)
        interval = '5m'
    elif period == '5d':
        start_date = end_date - timedelta(days=5)
        interval = '30m'
    elif period == '1mo':
        start_date = end_date - relativedelta(months=1)
        interval = '1h'
    elif period == '6mo':
        start_date = end_date - relativedelta(months=6)
        interval = '1d'
    elif period == '1y':
        start_date = end_date - relativedelta(years=1)
        interval = '1d'
    elif period == '5y':
        start_date = end_date - relativedelta(years=5)
        interval = '1wk'
    elif period == 'max':
        start_date = datetime(2000, 1, 1)
        interval = '1mo'
    else:
        start_date = end_date - relativedelta(years=1)
        interval = '1d'
    
    stock = yf.Ticker(stock_name + ".PA")
    data = stock.history(start=start_date, end=end_date, interval=interval)
    
    if data.empty:
        return None, f"No data found for {stock_name}"
    
    return data, None

# Function to create candlestick chart
def create_candlestick_chart(data, stock_name):
    fig, ax = plt.subplots(figsize=(10, 6))
    
    # Create candlestick chart
    mpf.plot(data, type='candle', style='charles', 
             title=f'{stock_name} Price', 
             ylabel='Price (PKR)', 
             ax=ax, 
             show_nontrading=False)
    
    # Format dates on x-axis
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
    plt.xticks(rotation=45)
    plt.tight_layout()
    
    return fig

# Main function to process stock information
def get_stock_info(stock_name, period, interval):
    # Fetch stock data
    data, error = fetch_stock_data(stock_name, period, interval)
    if error:
        return error, None, None
    
    # Create candlestick chart
    fig = create_candlestick_chart(data, stock_name)
    
    # Calculate additional metrics
    latest_close = data['Close'].iloc[-1]
    previous_close = data['Close'].iloc[-2] if len(data) > 1 else latest_close
    price_change = latest_close - previous_close
    percent_change = (price_change / previous_close) * 100
    
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
    recent_data = data.tail(10).reset_index()
    recent_data['Date'] = recent_data['Date'].dt.strftime('%Y-%m-%d')
    recent_data = recent_data[['Date', 'Open', 'High', 'Low', 'Close', 'Volume']]
    
    return metrics_html, fig, recent_data

# Function to get top gainers
def get_top_gainers():
    kse100_table = fetch_kse100_data()
    top_gainers = kse100_table.nlargest(10, 'Change%')
    return top_gainers[['Symbol', 'Current', 'Change%']]

# Function to get top losers
def get_top_losers():
    kse100_table = fetch_kse100_data()
    top_losers = kse100_table.nsmallest(10, 'Change%')
    return top_losers[['Symbol', 'Current', 'Change%']]

# Gradio interface
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

# Launch the app
if __name__ == "__main__":
    demo.launch()