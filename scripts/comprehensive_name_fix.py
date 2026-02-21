import sqlite3

DB_PATH = "vera.db"

def comprehensive_name_fix():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 1. Update Names for ALL known assets to ensure they aren't showing IDs
    name_map = {
        # HK Stocks
        "HK:STOCK:00700": "腾讯控股",
        "HK:STOCK:00005": "汇丰控股",
        "HK:STOCK:00998": "中信银行 (HK)",
        "HK:STOCK:01919": "中远海控 (HK)",
        "HK:STOCK:09988": "阿里巴巴",
        "HK:STOCK:02800": "盈富基金",
        "HK:STOCK:03033": "南方恒生科技",
        
        # CN Stocks
        "CN:STOCK:600030": "中信证券",
        "CN:STOCK:600309": "万华化学",
        "CN:STOCK:600536": "中国软件",
        "CN:STOCK:601519": "大智慧",
        "CN:STOCK:601919": "中远海控",
        "CN:STOCK:601998": "中信银行",
        "CN:STOCK:159662": "航运ETF",
        "CN:STOCK:512880": "证券ETF",
        "CN:STOCK:159851": "金融科技ETF",
        "CN:STOCK:512800": "银行ETF",
        "CN:STOCK:159852": "软件ETF",
        "CN:STOCK:516020": "化工ETF",
        "CN:STOCK:513190": "港股通金融ETF",
        "CN:STOCK:159751": "港股通科技ETF",
        
        # Indices
        "CN:INDEX:000016": "上证50",
        "CN:INDEX:000300": "沪深300",
        "CN:INDEX:000905": "中证500",
        "CN:INDEX:000001": "上证指数",
        "CN:INDEX:399006": "创业板指",
        "SPX": "标普500",
        "NDX": "纳斯达克100",
        "DJI": "道琼斯工业",
        "HSI": "恒生指数",
        "HSTECH": "恒生科技指数",
        "HSCE": "恒生中国企业指数"
    }
    
    for aid, name in name_map.items():
        cursor.execute("UPDATE assets SET symbol_name = ? WHERE asset_id = ?", (name, aid))
        
    # 2. Fix Market Attribution in assets table for HK assets
    cursor.execute("UPDATE assets SET market = 'HK' WHERE asset_id LIKE 'HK:%'")
    cursor.execute("UPDATE assets SET market = 'HK' WHERE asset_id IN ('HSI', 'HSTECH', 'HSCE')")
    
    conn.commit()
    conn.close()
    print("Database Names and Markets Standardized.")

if __name__ == "__main__":
    comprehensive_name_fix()
