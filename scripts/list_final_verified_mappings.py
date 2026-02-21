import sqlite3
import pandas as pd

DB_PATH = "vera.db"

def list_final_mappings():
    conn = sqlite3.connect(DB_PATH)
    
    # 1. Main query to get Stocks and their associated Sector Benchmarks
    query = """
    SELECT 
        a.market as "市场",
        a.asset_id as "资产 ID",
        a.symbol_name as "名称",
        a.asset_type as "类型",
        ac.sector_name as "所属行业",
        sp.proxy_etf_id as "对标 ETF",
        sp.market_index_id as "市场指数"
    FROM assets a
    LEFT JOIN asset_classification ac ON a.asset_id = ac.asset_id
    LEFT JOIN sector_proxy_map sp ON ac.sector_code = sp.sector_code AND ac.scheme = sp.scheme
    WHERE a.asset_type IN ('stock', 'EQUITY', 'Etf', 'ETF', 'INDEX')
    ORDER BY a.market, a.asset_type DESC, a.asset_id
    """
    
    df = pd.read_sql_query(query, conn)
    conn.close()
    
    # Simple Deduplication
    df = df.drop_duplicates(subset=["资产 ID", "名称", "对标 ETF", "市场指数"])
    
    if df.empty:
        print("未找到资产数据。")
        return

    # Print Grouped by Market
    for market, group in df.groupby("市场"):
        print(f"\n🌍 {market} 市场对照表")
        # Rename types for readability
        group['类型'] = group['类型'].replace({'EQUITY': '个股', 'stock': '个股', 'Etf': 'ETF', 'INDEX': '指数'})
        print(group.drop(columns=["市场"]).to_markdown(index=False))

if __name__ == "__main__":
    list_final_mappings()
