import yfinance as yf
from data.price_cache import save_daily_price

def fetch_and_cache(symbol, start_date, end_date):
    """(DEPRECATED) 停止从 yfinance 获取数据"""
    print(f"[DATA] External fetching disabled for {symbol}. Please import data via CSV or OCR.")
    return None
    # ticker = yf.Ticker(query_symbol)
    # ... (code preserved in history if needed)
