from db.connection import get_connection
import pandas as pd

def analyze_drawdown_details(symbol):
    conn = get_connection()
    query = """
        SELECT trade_date, close 
        FROM vera_price_cache 
        WHERE symbol = ? 
        ORDER BY trade_date ASC
    """
    df = pd.read_sql_query(query, conn, params=(symbol,))
    conn.close()
    
    if df.empty:
        print(f"No data for {symbol}")
        return

    # Prepare Series
    df['trade_date'] = pd.to_datetime(df['trade_date'])
    prices = df.set_index('trade_date')['close']
    
    # Calculate Drawdown Series
    cummax = prices.cummax()
    drawdowns = (prices - cummax) / cummax
    
    # 1. Find Max Drawdown Value & Valley Date
    mdd_val = drawdowns.min()
    valley_date = drawdowns.idxmin()
    
    # 2. Find Peak Date (Highest point before valley)
    # Filter data up to valley_date
    pre_valley = prices[:valley_date]
    peak_date = pre_valley.idxmax()
    peak_price = pre_valley.max()
    
    # 3. Find Recovery Time
    post_valley = prices[valley_date:]
    # Check if price recovered to peak_price
    recovery_dates = post_valley[post_valley >= peak_price].index
    
    recovery_date = None
    days_to_recover = "Not Recovered"
    
    if len(recovery_dates) > 0:
        recovery_date = recovery_dates[0]
        days_to_recover = (recovery_date - valley_date).days
        
    print(f"--- Drawdown Analysis for {symbol} ---")
    print(f"Max Drawdown: {mdd_val:.2%}")
    print(f"Peak Date:    {peak_date.strftime('%Y-%m-%d')} (Price: {peak_price:.2f})")
    print(f"Valley Date:  {valley_date.strftime('%Y-%m-%d')} (Price: {prices[valley_date]:.2f})")
    print(f"Duration:     {(valley_date - peak_date).days} days (Peak to Valley)")
    
    if recovery_date:
        print(f"Recovered On: {recovery_date.strftime('%Y-%m-%d')}")
        print(f"Recovery Time: {days_to_recover} days (Valley to Recovery)")
    else:
        print(f"Status:       Still Under Water (Current Price: {prices.iloc[-1]:.2f})")

if __name__ == "__main__":
    analyze_drawdown_details("600309.SH")
