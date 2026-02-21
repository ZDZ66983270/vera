import sqlite3
import pandas as pd

DB_PATH = "vera.db"

def list_all_assets_attributes():
    conn = sqlite3.connect(DB_PATH)
    
    # Comprehensive query to join assets with their classifications and sector benchmarks
    # Note: Using OUTER JOINs to ensure we see assets even if they lack classification
    query = """
    SELECT 
        a.market as "市场",
        a.asset_id as "资产 ID",
        a.symbol_name as "展示名称",
        a.asset_type as "类型",
        ac.sector_name as "所属行业",
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
    
    # 1:1 Mapping refinement: Only keep the most specific sector mapping if duplicates exist
    # (Usually caused by multiple classification records for the same asset)
    df = df.drop_duplicates(subset=["资产 ID", "市场"], keep="first")
    
    # Clean up the 'Type' labels for readability
    type_map = {
        'stock': '个股',
        'EQUITY': '个股',
        'Etf': 'ETF',
        'ETF': 'ETF',
        'INDEX': '指数'
    }
    df['类型'] = df['类型'].map(type_map).fillna(df['类型'])
    df['所属行业'] = df['所属行业'].fillna("-")
    df['对标 ETF'] = df['对标 ETF'].fillna("-")
    df['市场指数'] = df['市场指数'].fillna("-")

    # Print by Market
    for market, group in df.groupby("市场"):
        print(f"\n🌍 {market} 市场资产分布及对标一览")
        print(group.drop(columns=["市场"]).to_markdown(index=False))

if __name__ == "__main__":
    list_all_assets_attributes()
