import sqlite3
import pandas as pd

DB_PATH = "vera.db"

def list_final_purified_mappings():
    conn = sqlite3.connect(DB_PATH)
    
    # Updated query to show TRUE resolved context per market
    query = """
    SELECT 
        a.market as "市场",
        a.asset_id as "资产 ID",
        a.symbol_name as "名称",
        a.asset_type as "类型",
        ac.sector_name as "行业",
        sp.proxy_etf_id as "对标 ETF",
        sp.market_index_id as "市场指数"
    FROM assets a
    LEFT JOIN asset_classification ac ON a.asset_id = ac.asset_id
    LEFT JOIN sector_proxy_map sp ON ac.sector_code = sp.sector_code 
                                AND ac.scheme = sp.scheme
                                AND sp.market = a.market
    WHERE a.asset_type IN ('stock', 'EQUITY', 'Etf', 'ETF', 'INDEX')
    ORDER BY a.market, a.asset_type DESC, a.asset_id
    """
    
    df = pd.read_sql_query(query, conn)
    conn.close()
    
    # Deduplicate
    df = df.drop_duplicates(subset=["资产 ID", "名称", "对标 ETF", "市场指数"])
    
    # Hide indices from detailed sector mapping display if not relevant
    # (Optional: just filter for stocks to keep it clean)
    df_stocks = df[df['类型'].isin(['stock', 'EQUITY'])]
    
    for market, group in df_stocks.groupby("市场"):
        print(f"\n🌍 {market} 市场对照表 (已净化)")
        print(group.drop(columns=["市场", "类型"]).to_markdown(index=False))

if __name__ == "__main__":
    list_final_purified_mappings()
