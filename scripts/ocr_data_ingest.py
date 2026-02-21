
import sqlite3
from datetime import datetime
from data.price_cache import save_daily_price  # Use canonical-aware import

# ❗ RED LINE: Never write raw symbols directly to vera_price_cache

# 数据库路径
DB_PATH = "vera.db"

# 提取的全字段数据 (校准后的全量数据)
ocr_data = [
    {
        "symbol": "600309.SS", "name": "万华化学", "date": "2025-12-22", "industry": "Chemical",
        "price": {"open": 75.59, "high": 76.19, "low": 75.11, "close": 75.79, "volume": 26473000},
        "fundamentals": {"pe_ttm": 21.38, "pb": 2.26, "div_amt": 0.730}
    },
    {
        "symbol": "600309.SH", "name": "万华化学", "date": "2025-12-22", "industry": "Chemical",
        "price": {"open": 75.59, "high": 76.19, "low": 75.11, "close": 75.79, "volume": 26473000},
        "fundamentals": {"pe_ttm": 21.38, "pb": 2.26, "div_amt": 0.730}
    },
    {
        "symbol": "09988.HK", "name": "阿里巴巴-SW", "date": "2025-12-22", "industry": "Technology",
        "price": {"open": 146.0, "high": 148.5, "low": 145.0, "close": 146.4, "volume": 58880000},
        "fundamentals": {"pe_ttm": 20.34, "pb": 2.47, "div_amt": 1.961}
    },
    {
        "symbol": "00005.HK", "name": "汇丰控股", "date": "2025-12-22", "industry": "Bank",
        "price": {"open": 120.5, "high": 121.6, "low": 120.3, "close": 121.3, "volume": 19350000},
        "fundamentals": {"pe_ttm": 16.15, "pb": 1.40, "div_amt": 5.266},
        "bank_metrics": {"npl_ratio": 0.014, "provision_coverage": 1.80, "sm_ratio": 0.021}
    },
    {
        "symbol": "601919.SS", "name": "中远海控", "date": "2025-12-22", "industry": "Carrier",
        "price": {"open": 15.30, "high": 15.37, "low": 15.24, "close": 15.34, "volume": 50592000},
        "fundamentals": {"pe_ttm": 6.25, "pb": 1.02, "div_amt": 1.590}
    },
    {
        "symbol": "601919.SH", "name": "中远海控", "date": "2025-12-22", "industry": "Carrier",
        "price": {"open": 15.30, "high": 15.37, "low": 15.24, "close": 15.34, "volume": 50592000},
        "fundamentals": {"pe_ttm": 6.25, "pb": 1.02, "div_amt": 1.590}
    },
    {
        "symbol": "01919.HK", "name": "中远海控", "date": "2025-12-22", "industry": "Carrier",
        "price": {"open": 13.60, "high": 13.71, "low": 13.58, "close": 13.70, "volume": 12280000},
        "fundamentals": {"pe_ttm": 5.08, "pb": 0.83, "div_amt": 1.746}
    },
    {
        "symbol": "601998.SS", "name": "中信银行", "date": "2025-12-22", "industry": "Bank",
        "price": {"open": 7.45, "high": 7.45, "low": 7.36, "close": 7.39, "volume": 35964000},
        "fundamentals": {"pe_ttm": 5.86, "pb": 0.58, "div_amt": 0.360},
        "bank_metrics": {"npl_ratio": 0.012, "provision_coverage": 2.10, "sm_ratio": 0.018}
    },
    {
        "symbol": "601998.SH", "name": "中信银行", "date": "2025-12-22", "industry": "Bank",
        "price": {"open": 7.45, "high": 7.45, "low": 7.36, "close": 7.39, "volume": 35964000},
        "fundamentals": {"pe_ttm": 5.86, "pb": 0.58, "div_amt": 0.360},
        "bank_metrics": {"npl_ratio": 0.012, "provision_coverage": 2.10, "sm_ratio": 0.018}
    },
    {
        "symbol": "00998.HK", "name": "中信银行(HK)", "date": "2025-12-22", "industry": "Bank",
        "price": {"open": 6.950, "high": 6.980, "low": 6.870, "close": 6.910, "volume": 23550000},
        "fundamentals": {"pe_ttm": 5.00, "pb": 0.49, "div_amt": 0.394},
        "bank_metrics": {"npl_ratio": 0.012, "provision_coverage": 2.10, "sm_ratio": 0.018}
    }
]

def run_ingestion():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    for item in ocr_data:
        symbol = item["symbol"]
        date = item["date"]
        p = item["price"]
        f = item["fundamentals"]
        
        # 1. 更新资产表
        cursor.execute("""
            INSERT INTO assets (asset_id, symbol_name, industry) VALUES (?, ?, ?)
            ON CONFLICT(asset_id) DO UPDATE SET 
                symbol_name = excluded.symbol_name,
                industry = excluded.industry
        """,(symbol, item["name"], item["industry"]))
        
        # ❗ RED LINE: Use save_daily_price() to ensure canonical mapping
        # 2. 写入行情缓存
        save_daily_price({
            "symbol": symbol,
            "trade_date": date,
            "open": p["open"],
            "high": p["high"],
            "low": p["low"],
            "close": p["close"],
            "volume": p["volume"],
            "source": "OCR"
        })
        
        # 3. 写入基础面数据
        eps_ttm = p["close"] / f["pe_ttm"] if f["pe_ttm"] > 0 else 0
        bps = p["close"] / f["pb"] if f["pb"] > 0 else 0
        
        bm = item.get("bank_metrics", {})
        npl_r = bm.get("npl_ratio")
        prov_c = bm.get("provision_coverage")
        sm_r = bm.get("sm_ratio")
        
        cursor.execute("""
            INSERT INTO financial_history (
                asset_id, report_date, eps_ttm, bps, dividend_amount,
                npl_ratio, provision_coverage, special_mention_ratio
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(asset_id, report_date) DO UPDATE SET
                eps_ttm=excluded.eps_ttm, 
                bps=excluded.bps,
                dividend_amount=excluded.dividend_amount,
                npl_ratio=excluded.npl_ratio,
                provision_coverage=excluded.provision_coverage,
                special_mention_ratio=excluded.special_mention_ratio
        """, (symbol, date, eps_ttm, bps, f["div_amt"], npl_r, prov_c, sm_r))
        
    conn.commit()
    conn.close()
    print("Full OCR Ingestion successfully completed.")

if __name__ == "__main__":
    run_ingestion()
