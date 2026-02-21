
from data.fetch_fundamentals import fetch_fundamentals

if __name__ == "__main__":
    asset_id = "CN:STOCK:600030"  # Has 5 years of financials
    print(f"Testing revenue_history for {asset_id}...")
    
    fundamentals, bank_metrics = fetch_fundamentals(asset_id)
    
    print(f"\nAsset: {fundamentals.symbol}")
    print(f"Industry: {fundamentals.industry}")
    print(f"Revenue TTM: {fundamentals.revenue_ttm:,.0f}")
    print(f"\nRevenue History (oldest to newest):")
    if fundamentals.revenue_history:
        for i, rev in enumerate(fundamentals.revenue_history):
            print(f"  Year {i+1}: {rev:,.0f}")
        print(f"\n✅ Revenue history populated with {len(fundamentals.revenue_history)} years of data")
    else:
        print("  ❌ No revenue history found")
