
from db.connection import get_connection

if __name__ == "__main__":
    symbol = "CN:STOCK:600030"
    conn = get_connection()
    cursor = conn.cursor()
    
    print(f"Step 1: Testing revenue_history extraction for {symbol}\n")
    
    # Test the exact code from fetch_fundamentals.py
    revenue_history = None
    cursor.execute("""
        SELECT revenue_ttm
        FROM financial_fundamentals
        WHERE asset_id = ? AND revenue_ttm IS NOT NULL
        ORDER BY as_of_date ASC
    """, (symbol,))
    revenue_rows = cursor.fetchall()
    
    print(f"Query returned: {len(revenue_rows) if revenue_rows else 0} rows")
    
    if revenue_rows and len(revenue_rows) >= 4:
        revenue_history = [float(row[0]) for row in revenue_rows if row[0] is not None]
        print(f"✅ revenue_history created: {len(revenue_history)} items")
    else:
        print(f"❌ Condition failed:")
        print(f"   revenue_rows is None: {revenue_rows is None}")
        if revenue_rows:
            print(f"   len(revenue_rows): {len(revenue_rows)}")
            print(f"   len >= 4: {len(revenue_rows) >= 4}")
    
    print(f"\nStep 2: Now testing with fetch_fundamentals")
    from data.fetch_fundamentals import fetch_fundamentals
    fundamentals, bank_metrics = fetch_fundamentals(symbol)
    
    print(f"\nFundamentals object:")
    print(f"  symbol: {fundamentals.symbol}")
    print(f"  revenue_ttm: {fundamentals.revenue_ttm:,.0f}")
    print(f"  revenue_history: {fundamentals.revenue_history}")
    if fundamentals.revenue_history:
        print(f"    Length: {len(fundamentals.revenue_history)}")
        print(f"    Values: {[f'{v:,.0f}' for v in fundamentals.revenue_history[:3]]}")
    
    conn.close()
