import sqlite3
import pandas as pd

DB_PATH = "vera.db"

def check_historical_data_coverage():
    """检查所有资产的历史数据覆盖情况"""
    conn = sqlite3.connect(DB_PATH)
    
    print("=" * 80)
    print("资产历史数据覆盖情况检查")
    print("=" * 80)
    
    # Query historical data coverage
    query = """
        SELECT 
            a.asset_id,
            a.symbol_name,
            a.market,
            a.asset_type,
            COUNT(p.trade_date) as record_count,
            MIN(p.trade_date) as earliest_date,
            MAX(p.trade_date) as latest_date
        FROM assets a
        LEFT JOIN vera_price_cache p ON a.asset_id = p.symbol
        GROUP BY a.asset_id, a.symbol_name, a.market, a.asset_type
        ORDER BY 
            CASE a.market WHEN 'HK' THEN 1 WHEN 'US' THEN 2 WHEN 'CN' THEN 3 ELSE 4 END,
            CASE a.asset_type WHEN 'stock' THEN 1 WHEN 'etf' THEN 2 WHEN 'index' THEN 3 ELSE 4 END,
            a.asset_id
    """
    
    df = pd.read_sql_query(query, conn)
    
    # Summary by market and type
    print("\n按市场和类型统计：\n")
    summary = df.groupby(['market', 'asset_type']).agg({
        'record_count': ['count', 'mean', 'min', 'max']
    }).round(0)
    print(summary)
    
    # Assets with insufficient data (< 10 records)
    print("\n" + "=" * 80)
    print("数据不足的资产 (< 10条记录):")
    print("=" * 80)
    
    insufficient = df[df['record_count'] < 10].copy()
    insufficient = insufficient.sort_values(['market', 'asset_type', 'asset_id'])
    
    if len(insufficient) > 0:
        print(f"\n发现 {len(insufficient)} 个资产数据不足:\n")
        print(f"{'市场':<6} {'类型':<8} {'Asset ID':<20} {'名称':<25} {'记录数':>8} {'最早日期':<12} {'最新日期':<12}")
        print("-" * 110)
        
        for _, row in insufficient.iterrows():
            market = row['market'] or 'N/A'
            asset_type = row['asset_type'] or 'N/A'
            asset_id = row['asset_id']
            name = (row['symbol_name'] or '')[:24]
            count = int(row['record_count']) if pd.notna(row['record_count']) else 0
            earliest = row['earliest_date'] or 'N/A'
            latest = row['latest_date'] or 'N/A'
            
            print(f"{market:<6} {asset_type:<8} {asset_id:<20} {name:<25} {count:>8} {earliest:<12} {latest:<12}")
    else:
        print("\n✅ 所有资产都有充足的历史数据")
    
    # Top assets by data coverage
    print("\n" + "=" * 80)
    print("数据最丰富的资产 (Top 10):")
    print("=" * 80)
    
    top_assets = df.nlargest(10, 'record_count')[['asset_id', 'symbol_name', 'market', 'asset_type', 'record_count', 'earliest_date', 'latest_date']]
    print(f"\n{'Asset ID':<20} {'名称':<25} {'市场':<6} {'类型':<8} {'记录数':>8} {'时间跨度'}")
    print("-" * 100)
    for _, row in top_assets.iterrows():
        span = f"{row['earliest_date']} - {row['latest_date']}" if pd.notna(row['earliest_date']) else 'N/A'
        print(f"{row['asset_id']:<20} {(row['symbol_name'] or '')[:24]:<25} {row['market'] or 'N/A':<6} {row['asset_type'] or 'N/A':<8} {int(row['record_count']):>8} {span}")
    
    conn.close()

if __name__ == "__main__":
    check_historical_data_coverage()
