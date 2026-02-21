from db.connection import get_connection
from metrics.drawdown import max_drawdown
from analysis.price_series import PriceSeries
import pandas as pd

def verify_drawdown(symbol):
    conn = get_connection()
    # Fetch all data for the symbol
    query = """
        SELECT trade_date, close 
        FROM vera_price_cache 
        WHERE symbol = ? 
        ORDER BY trade_date ASC
    """
    df = pd.read_sql_query(query, conn, params=(symbol,))
    conn.close()
    
    if df.empty:
        print(f"No data found for {symbol}")
        return

    # Ensure close is float and date is datetime (though Series logic mainly needs values)
    closes = df['close'].values
    
    # Calculate
    dd = max_drawdown(closes)
    
    print(f"Symbol: {symbol}")
    print(f"Data Points: {len(closes)}")
    print(f"Date Range: {df['trade_date'].min()} to {df['trade_date'].max()}")
    print(f"Max Drawdown: {dd:.4%}")

if __name__ == "__main__":
    verify_drawdown("600309.SH")
