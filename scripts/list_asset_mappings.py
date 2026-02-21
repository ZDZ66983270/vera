import sqlite3
import pandas as pd

DB_PATH = "vera.db"

def list_mappings():
    conn = sqlite3.connect(DB_PATH)
    
    query = """
    SELECT 
        a.market as "市场",
        a.asset_id as "个股 ID",
        a.symbol_name as "名称",
        ac.sector_name as "行业",
        sp.proxy_etf_id as "对标 ETF",
        sp.market_index_id as "市场指数"
    FROM assets a
    JOIN asset_classification ac ON a.asset_id = ac.asset_id
    LEFT JOIN sector_proxy_map sp ON ac.sector_code = sp.sector_code AND ac.scheme = sp.scheme
    WHERE a.asset_type IN ('stock', 'EQUITY')
    ORDER BY a.market, a.asset_id
    """
    
    df = pd.read_sql_query(query, conn)
    conn.close()
    
    if df.empty:
        print("未找到任何对应关系。请确认 asset_classification 和 sector_proxy_map 表是否有数据。")
        return

    # Group by market for better display
    for market, group in df.groupby("市场"):
        print(f"\n===== {market} 市场 =====")
        # Drop the market column for the display table
        display_df = group.drop(columns=["市场"])
        print(display_df.to_markdown(index=False))

if __name__ == "__main__":
    list_mappings()
