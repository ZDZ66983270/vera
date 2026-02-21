
from db.connection import get_connection

if __name__ == "__main__":
    asset_id = "CN:STOCK:600030"
    conn = get_connection()
    cursor = conn.cursor()
    
    print(f"Testing SQL query for {asset_id}...")
    
    cursor.execute("""
        SELECT revenue_ttm
        FROM financial_fundamentals
        WHERE asset_id = ? AND revenue_ttm IS NOT NULL
        ORDER BY as_of_date ASC
    """, (asset_id,))
    
    revenue_rows = cursor.fetchall()
    print(f"\nQuery returned {len(revenue_rows)} rows")
    
    if revenue_rows:
        print("\nRevenue values:")
        for i, row in enumerate(revenue_rows):
            print(f"  {i+1}. {row[0]:,.0f}")
            
        if len(revenue_rows) >= 4:
            revenue_history = [float(row[0]) for row in revenue_rows if row[0] is not None]
            print(f"\n✅ Revenue history list created: {len(revenue_history)} items")
            print(f"   First 3: {revenue_history[:3]}")
        else:
            print(f"\n❌ Only {len(revenue_rows)} rows, need >= 4")
    else:
        print("\n❌ No rows returned")
    
    conn.close()
