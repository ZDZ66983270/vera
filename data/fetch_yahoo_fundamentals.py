
import datetime as dt
import yfinance as yf
from db.connection import get_connection
from utils.canonical_resolver import resolve_symbol_for_provider

def _safe_get(d, *keys, default=None):
    cur = d
    for k in keys:
        if cur is None:
            return default
        if isinstance(cur, dict):
             cur = cur.get(k)
        else:
             return default
    return cur if cur not in ("None", "") else default

def fetch_and_save_fundamentals_yahoo(asset_id: str):
    """
    使用 canonical symbol -> yahoo ticker 的映射，拉取基础财务 + PE/PB
    并写入 fundamentals_facts 表。
    """
    # Use existing resolver logic or fallback
    yahoo_symbol = asset_id
    try:
        # Assuming resolve_symbol_for_provider is available, otherwise use direct map logic
        yahoo_symbol = resolve_symbol_for_provider(asset_id, provider="yahoo") 
    except ImportError:
        pass # Fallback to asset_id as is (usually OK for US/HK if formatted right)

    print(f"[{asset_id}] Fetching standardized fundamentals via Yahoo ({yahoo_symbol})...")
    ticker = yf.Ticker(yahoo_symbol)

    try:
        info = ticker.info
    except Exception as e:
        print(f"Error fetching Yahoo info for {yahoo_symbol}: {e}")
        return

    price = _safe_get(info, "currentPrice") or _safe_get(info, "regularMarketPrice")
    
    # Raw metrics from Yahoo
    pe_ttm_raw = _safe_get(info, "trailingPE")
    pb_raw = _safe_get(info, "priceToBook")
    eps_ttm = _safe_get(info, "trailingEps")
    bvps = _safe_get(info, "bookValue")
    shares_out = _safe_get(info, "sharesOutstanding")
    currency = _safe_get(info, "currency")
    
    # As of Date: Try to find most recent quarter
    mrq = _safe_get(info, "mostRecentQuarter") # integer timestamp or string?
    as_of = dt.date.today().isoformat()
    
    if mrq:
        # specific yahoo behavior check: sometimes it's an int timestamp
        if isinstance(mrq, int):
             as_of = dt.date.fromtimestamp(mrq).isoformat()
        else:
             as_of = str(mrq)

    # 规范化计算: PE/PB
    pe_ttm = None
    if price is not None and eps_ttm and eps_ttm > 0:
        pe_ttm = price / eps_ttm

    pb = None
    if price is not None and bvps and bvps > 0:
        pb = price / bvps

    print(f"[{asset_id}] Metrics: Price={price}, EPS_TTM={eps_ttm}, BVPS={bvps} -> PE={pe_ttm}, PB={pb}")

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        INSERT OR REPLACE INTO fundamentals_facts (
            asset_id, as_of_date, currency,
            net_income_ttm, shares_outstanding, book_value_per_sh,
            pe_ttm_raw, pb_raw,
            eps_ttm, pe_ttm, pb,
            source
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        asset_id, as_of,
        currency,
        None,              # net_income can be added via separate fetch if needed
        shares_out,
        bvps,
        pe_ttm_raw,
        pb_raw,
        eps_ttm,
        pe_ttm,
        pb,
        "yahoo",
    ))

    conn.commit()
    conn.close()
    print(f"[{asset_id}] Saved to fundamentals_facts.")

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        fetch_and_save_fundamentals_yahoo(sys.argv[1])
