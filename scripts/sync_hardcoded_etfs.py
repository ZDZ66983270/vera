import sqlite3
import sys
import os

# Ensure we can import from project root
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.connection import get_connection
from engine.universe_manager import add_to_universe

def sync_etfs():
    etfs = [
        ("XLK", "科技行业 (XLK)", "Information Technology"),
        ("XLF", "金融行业 (XLF)", "Financials"),
        ("XLE", "能源行业 (XLE)", "Energy"),
        ("XLY", "可选消费 (XLY)", "Consumer Discretionary"),
        ("XLP", "必需消费 (XLP)", "Consumer Staples"),
        ("XLV", "医疗保健 (XLV)", "Health Care"),
        ("XLI", "工业行业 (XLI)", "Industrials"),
        ("XLB", "原材料行业 (XLB)", "Materials"),
        ("XLU", "公用事业 (XLU)", "Utilities"),
        ("XLC", "通信服务 (XLC)", "Communication Services"),
        ("XLRE", "房地产行业 (XLRE)", "Real Estate"),
        ("IWM", "罗素2000 (IWM)", "Broad Market"),
        ("QQQ", "纳斯达克100 (QQQ)", "Broad Market"),
        ("SPY", "标普500 (SPY)", "Broad Market"),
        ("DIA", "道琼斯 (DIA)", "Broad Market"),
    ]
    
    print(f"Syncing {len(etfs)} US ETFs to universe...")
    for sym, name, ind in etfs:
        print(f"  Registering {sym}...")
        add_to_universe(
            raw_symbol=sym,
            name=name,
            market="US",
            asset_type="ETF",
            industry_name=ind
        )
    print("✅ US ETFs sync complete.")

if __name__ == "__main__":
    sync_etfs()
