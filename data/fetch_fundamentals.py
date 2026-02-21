from analysis.valuation import AssetFundamentals
from analysis.bank_quality import BankMetrics
from db.connection import get_connection
import pandas as pd
import random
import math

from datetime import datetime

def fetch_fundamentals(symbol: str, as_of_date: datetime = None) -> tuple[AssetFundamentals, BankMetrics]:
    """
    获取资产基本面数据 (DB-First Implementation)
    优先从数据库读取 OCR 或导入的数据，缺失时回退到 Mock。
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    # 0. 获取标准的 Canonical ID (处理输入为 TSLA 或 00700 的情况)
    canonical_id = symbol
    if ":" not in symbol:
        # 启发式补全
        if symbol.isalpha(): canonical_id = f"US:STOCK:{symbol}"
        elif symbol.isdigit(): canonical_id = f"HK:STOCK:{symbol.zfill(5)}"
        elif ".HK" in symbol: canonical_id = f"HK:STOCK:{symbol.replace('.HK','').zfill(5)}"
        elif ".SS" in symbol or ".SH" in symbol:
            code = symbol.split(".")[0]
            canonical_id = f"CN:STOCK:{code}"
    
    # 记录原始 symbol 用于 fallback 兼容，核心逻辑改用 canonical_id
    effective_symbol = canonical_id
    
    # 获取 A 股备选 ID
    alt_symbol = effective_symbol
    if effective_symbol.endswith(".SS"):
        alt_symbol = effective_symbol.replace(".SS", ".SH")
    elif effective_symbol.endswith(".SH"):
        alt_symbol = effective_symbol.replace(".SH", ".SS")
    elif "CN:STOCK:" in effective_symbol:
        # 如果是标准 ID 但 A 股数据可能在不同市场
        pass

    # 1. 获取行业信息与基本设置
    cursor.execute("SELECT industry, name FROM assets WHERE asset_id IN (?, ?, ?)", (effective_symbol, alt_symbol, symbol))
    asset_row = cursor.fetchone()
    industry = asset_row[0] if asset_row and asset_row[0] != 'Unknown' else "Technology"
    
    # 银行股自动识别补充 (修复逻辑：避免誤判包含 STOCK 字符的标的)
    bank_codes = ["BAC", "JPM", "GS", "MS", "C", "WFC"] # 美股大行
    cn_hk_bank_codes = ["600036", "601398", "601998", "00998", "00005"] # 中港大行
    
    parts = symbol.split(":")
    code_only = parts[-1].replace(".HK", "").replace(".SS", "").replace(".SH", "")
    
    if code_only in bank_codes or code_only in cn_hk_bank_codes:
        industry = "Bank"
    
    # 2. 从数据库获取财务指标
    # 获取最接近的财务快照 (支持从 A 股两个常用后缀中查找)
    # 2. 从数据库获取财务指标
    # 获取最接近的财务快照 (支持从 A 股两个常用后缀中查找)
    # 支持历史回测：只获取截止到 as_of_date 的报告
    query = """
        SELECT eps_ttm, bps, revenue_ttm, net_profit_ttm, dividend_amount, buyback_amount,
               npl_ratio, provision_coverage, special_mention_ratio, currency,
               net_interest_income, net_fee_income, provision_expense, total_loans, 
               core_tier1_capital_ratio, overdue_90_loans, npl_balance,
               roe, net_margin
        FROM financial_history 
        WHERE asset_id IN (?, ?, ?)
    """
    params = [effective_symbol, alt_symbol, symbol]
    
    if as_of_date:
        query += " AND report_date <= ?"
        params.append(as_of_date)
        
    query += " ORDER BY report_date DESC LIMIT 1"
    
    cursor.execute(query, params)
    fin_row = cursor.fetchone()
    
    # 3. 获取最新价格以计算 PE/PB
    # 支持历史回测：只获取截止到 as_of_date 的最后价格
    date_constraint = ""
    params = [effective_symbol, alt_symbol, symbol]
    
    if as_of_date:
        date_constraint = "AND trade_date <= ?"
        params.append(as_of_date)
        
    cursor.execute(f"SELECT close, pe, pe_ttm, pb, eps, ps, dividend_yield FROM vera_price_cache WHERE symbol IN (?, ?, ?) {date_constraint} ORDER BY trade_date DESC LIMIT 1", (effective_symbol, alt_symbol, symbol) + ((as_of_date,) if as_of_date else ()))
    price_row = cursor.fetchone()
    
    # 已通过 IN 查询覆盖，删除 redundant retry

    current_price = price_row[0] if price_row else None
    db_pe = price_row[1] if price_row else None
    db_pe_ttm = price_row[2] if price_row else None
    db_pb = price_row[3] if price_row else None
    db_eps = price_row[4] if price_row else None
    db_ps = price_row[5] if price_row else None
    db_dy = price_row[6] if price_row else None
    
    # ... (revenue_history 提取逻辑保持不变) ...
    
    # --- Extract revenue_history from financial_history (Migrated from financial_fundamentals) ---
    # This ensures we can still get quality metric data for multi-year revenue analysis
    revenue_history = None
    cursor.execute("""
        SELECT revenue_ttm
        FROM financial_history
        WHERE asset_id IN (?, ?, ?) AND revenue_ttm IS NOT NULL
        ORDER BY report_date ASC
    """, (effective_symbol, alt_symbol, symbol))
    revenue_rows = cursor.fetchall()
    if revenue_rows and len(revenue_rows) >= 4:
        # Extract as list (oldest to newest)
        revenue_history = [float(row[0]) for row in revenue_rows if row[0] is not None]
    
    if fin_row:
        # Unpack with new columns
        eps, bps, rev, profit, div_amt, buy_amt, npl_r, prov_c, sm_r, report_currency, \
        nii, fees, prov_exp, loans, cet1, overdue90, npl_bal, roe_val, margin_val = fin_row
        
        # --- Generic Currency Adjustment Logic ---
        # Principle: Only convert if Reporting Currency != Trading Currency
        
        # 1. Infer Trading Currency
        trading_currency = "CNY" # Default
        if "HK:STOCK:" in symbol or symbol.endswith(".HK"):
            trading_currency = "HKD"
        elif "US:STOCK:" in symbol or "US:INDEX" in symbol or symbol.isalpha():
            trading_currency = "USD"
        elif "CN:STOCK:" in symbol or symbol.endswith(".SS") or symbol.endswith(".SH"):
            trading_currency = "CNY"
            
        # 2. Normalize Reporting Currency
        if not report_currency:
             # Fallback logic if DB is empty:
             # If HK stock & identified as Mainland -> CNY, else Trading Currency
             is_hk = trading_currency == "HKD"
             # Use the known list heuristic as 'Fallback' only when report_currency is missing
             known_cny_reporters = ["00700", "09988", "03690", "09618", "01024", "01810", "03988", "01398", "00939", "01288", "00883", "00857"]
             raw_code = symbol.split(":")[-1].replace(".HK", "")
             if is_hk and any(c in raw_code for c in known_cny_reporters):
                 report_currency = "CNY"
             else:
                 report_currency = trading_currency

        # 3. Define FX Rates (Reporting -> Trading)
        # TODO: Ideally fetch from DB/API. Using static estimates for MVP.
        FX_RATES = {
            ("CNY", "HKD"): 1.08,
            ("USD", "HKD"): 7.78,
            ("HKD", "CNY"): 0.92,
            ("USD", "CNY"): 7.20,
            ("CNY", "USD"): 0.14,
            ("HKD", "USD"): 0.13
        }
        
        # 4. Apply Conversion (仅在数据库没有直读 PE/PB 时计算)
        adjusted_eps = db_eps or eps
        adjusted_bps = bps # db_pb 包含价格逻辑，此处 adjusted_bps 主要用于 AssetFundamentals 结构
        
        # 如果数据库有直读，且不需要货币转换（或者 db 指标已包含转换），则直接用
        if db_pe_ttm:
            pe = db_pe_ttm
        elif db_pe:
            # Fallback: if TTM not explicitly there, use Static if that's all we have
            # But strictly speaking we should try to calc TTM from EPS TTM.
            if adjusted_eps and adjusted_eps > 0 and current_price:
                 pe = current_price / adjusted_eps
            else:
                 pe = db_pe # Last resort
        else:
            if report_currency != trading_currency and eps:
                rate = FX_RATES.get((report_currency, trading_currency), 1.0)
                adjusted_eps = eps * rate
            pe = current_price / adjusted_eps if adjusted_eps and adjusted_eps > 0 else None
            
        # Static PE (Anchor)
        pe_static = db_pe

        if db_pb:
            pb = db_pb
        else:
            if report_currency != trading_currency and bps:
                rate = FX_RATES.get((report_currency, trading_currency), 1.0)
                adjusted_bps = bps * rate
            pb = current_price / adjusted_bps if adjusted_bps and adjusted_bps > 0 else None
        
        div_yield = db_dy if db_dy else (div_amt / current_price if (div_amt and current_price and current_price > 0) else 0.0)
        # 移除银行默认 5% 股息的 Mock
        
        # --- NEW: Override with Standardized Fundamentals Facts if available ---
        # Strategy: Use EPS/BVPS from fundamentals_facts + current_price to get dynamic PE/PB
        # Try both canonical and naked symbol
        naked_symbol = symbol.split(":")[-1]
        cursor.execute("""
            SELECT eps_ttm, book_value_per_sh, shares_outstanding
            FROM fundamentals_facts
            WHERE asset_id IN (?, ?)
            ORDER BY as_of_date DESC LIMIT 1
        """, (symbol, naked_symbol))
        fact_row = cursor.fetchone()
        
        shares_out = None
        if fact_row:
            f_eps, f_bvps, f_shares = fact_row
            shares_out = f_shares
            
            # Update local variables for AssetFundamentals
            if f_eps is not None and not db_eps: 
                eps = f_eps
                # Re-apply FX logic using the same generic approach
                if report_currency != trading_currency:
                    rate = FX_RATES.get((report_currency, trading_currency), 1.0)
                    adjusted_eps = f_eps * rate
                else:
                    adjusted_eps = f_eps
                
            if f_bvps is not None and not adjusted_bps: 
                bps = f_bvps
                if report_currency != trading_currency:
                    rate = FX_RATES.get((report_currency, trading_currency), 1.0)
                    adjusted_bps = f_bvps * rate
                else:
                    adjusted_bps = f_bvps
            
            # 仅在数据库直读缺失时，使用事实库重新计算指标
            if not pe and adjusted_eps and adjusted_eps > 0 and current_price:
                pe = current_price / adjusted_eps
            
            if not pb and adjusted_bps and adjusted_bps > 0 and current_price:
                pb = current_price / adjusted_bps

        # 计算 no_dividend_history 和 listing_years (用于质量评估)
        no_dividend_history = False
        listing_years = None
        
        # Check dividend history
        cursor.execute("""
            SELECT COUNT(*) FROM financial_history 
            WHERE asset_id IN (?, ?) AND dividend_amount IS NOT NULL AND dividend_amount > 0
        """, (symbol, alt_symbol))
        div_count_row = cursor.fetchone()
        div_count = div_count_row[0] if div_count_row else 0
        
        # Check listing age approximation from price history
        cursor.execute("""
            SELECT MIN(trade_date), MAX(trade_date) FROM vera_price_cache 
            WHERE symbol IN (?, ?)
        """, (symbol, alt_symbol))
        date_row = cursor.fetchone()
        if date_row and date_row[0] and date_row[1]:
            try:
                from datetime import datetime
                min_date = datetime.strptime(str(date_row[0]), '%Y-%m-%d')
                max_date = datetime.strptime(str(date_row[1]), '%Y-%m-%d')
                days_diff = (max_date - min_date).days
                listing_years = days_diff / 365.25
            except Exception:
                pass
        
        # Mark as no_dividend_history if: mature company (5+ years) with zero dividend records
        if div_count == 0 and listing_years is not None and listing_years >= 5:
            no_dividend_history = True

        # 计算估值状态 (Valuation Status)
        # 1. 优先使用 PE/PB 历史分布 (TODO)
        # 2. 目前使用简化逻辑：若 PE > 40 为高估，PE < 15 为低估 (仅针对非银行/金融)
        # 3. 回退逻辑：价格分位
        val_status = "Fair"
        
        # 尝试通过 PE 判断
        if pe is not None and industry not in ["Bank", "RealEstate", "Insurance"]:
            if pe > 40: val_status = "Overvalued"
            elif pe > 25: val_status = "Premium"
            elif pe < 12: val_status = "Undervalued"
            elif pe < 20: val_status = "Discount"
        elif pb is not None and industry in ["Bank", "RealEstate", "Insurance"]:
            if pb > 1.2: val_status = "Overvalued"
            elif pb < 0.5: val_status = "Undervalued"
            elif pb < 0.7: val_status = "Discount"
        else:
            # 最终回退：价格分位 (Last Resort)
            cursor.execute("SELECT MIN(close), MAX(close) FROM vera_price_cache WHERE symbol IN (?, ?)", (symbol, alt_symbol))
            p_row = cursor.fetchone()
            if p_row and p_row[0] is not None:
                min_p, max_p = p_row
                p_range = max_p - min_p
                if p_range > 0:
                    percentile = (current_price - min_p) / p_range
                    if percentile < 0.15: val_status = "Undervalued"
                    elif percentile < 0.35: val_status = "Discount"
                    elif percentile > 0.85: val_status = "Overvalued"
                    elif percentile > 0.65: val_status = "Premium"
        
        fundamentals = AssetFundamentals(
            symbol=symbol,
            industry=industry,
            net_profit_ttm=profit if profit else 0.0,
            revenue_ttm=rev if rev else 0.0,
            revenue_growth_3y=None, 
            profit_growth_3y=None,
            pe_ttm=pe,
            pe_static=pe_static,
            pb_ratio=pb,
            dividend_yield=div_yield,
            buyback_ratio=buy_amt / (current_price * shares_out) if buy_amt and current_price and shares_out else 0.0,
            bps=bps,
            eps_ttm=eps,
            valuation_status=val_status,
            revenue_history=revenue_history,
            roe=roe_val,
            net_margin=margin_val,
            no_dividend_history=no_dividend_history,
            listing_years=listing_years,
            npl_deviation=npl_r * 1.5 if npl_r else (1.0 if industry == "Bank" else None),
            provision_coverage=prov_c if prov_c else (2.5 if industry == "Bank" else None),
            net_interest_income=nii,
            net_fee_income=fees,
            provision_expense=prov_exp,
            total_loans=loans,
            core_tier1_capital_ratio=cet1
        )
        
        # 银行专项指标补充
        bank_metrics = None
        if industry == "Bank":
            bank_metrics = BankMetrics(
                overdue_90_loans=overdue90 if overdue90 else 0.0,
                npl_balance=npl_bal if npl_bal else 0.0,
                provision_coverage=prov_c if prov_c else 0.0,
                special_mention_ratio=sm_r if sm_r else 0.0,
                npl_ratio=npl_r if npl_r else 0.0,
                net_interest_income=nii,
                net_fee_income=fees,
                provision_expense=prov_exp,
                total_loans=loans,
                core_tier1_capital_ratio=cet1
            )
    else:
        # 4. 无数据时的空对象回退 (无 Mock) - BUT USE MARKET DATA IF AVAILABLE
        # Fallback to DB-based PE if financial report is missing
        pe = db_pe_ttm if db_pe_ttm else db_pe
        pe_static = db_pe
        pb = db_pb
        
        # Simple Valuation Status Check if we have PE
        val_status = "Unknown"
        if pe is not None and industry not in ["Bank", "RealEstate", "Insurance"]:
            if pe > 40: val_status = "Overvalued"
            elif pe > 25: val_status = "Premium"
            elif pe < 12: val_status = "Undervalued"
            elif pe < 20: val_status = "Discount"
        elif pe:
             val_status = "Fair"

        fundamentals = AssetFundamentals(
            symbol=symbol,
            industry=industry,
            net_profit_ttm=0.0,
            revenue_ttm=0.0,
            revenue_growth_3y=None,
            profit_growth_3y=None,
            pe_ttm=pe,
            pe_static=pe_static,
            pb_ratio=pb,
            dividend_yield=db_dy if db_dy else 0.0,
            buyback_ratio=0.0,
            revenue_history=revenue_history,
            valuation_status=val_status
        )

    # 5. 银行专项指标补充
    bank_metrics = None
    if industry == "Bank":
        # 如果是银行但没有 fin_row，我们也需要一个基础结构，但所有值应表现为无
        bank_metrics = BankMetrics(
            overdue_90_loans=0.0,
            npl_balance=0.0,
            provision_coverage=0.0,
            special_mention_ratio=0.0,
            npl_ratio=0.0
        )
    
    conn.close()
    return fundamentals, bank_metrics
