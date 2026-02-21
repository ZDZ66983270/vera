import uuid
from typing import Dict, List, Any
from datetime import datetime, timedelta
from db.connection import get_connection, init_db
# from data.fetch_marketdata import fetch_and_cache  # Disabled in formal code
from data.fetch_fundamentals import fetch_fundamentals
from data.price_cache import load_price_series, save_daily_price
from analysis.price_series import PriceSeries
from metrics.drawdown import max_drawdown, recovery_time
from metrics.volatility import annual_volatility
from metrics.risk_engine import RiskEngine
from analysis.valuation import AssetFundamentals, choose_valuation_anchor, get_valuation_status, analyze_valuation_path
from analysis.trap_payout import detect_value_trap, calculate_payout_score
from analysis.bank_quality import calc_bank_quality_score
from analysis.conclusion import generate_conclusion, ConclusionInput
from analysis.risk_matrix import build_risk_card
from analysis.dashboard import generate_dashboard_data, DashboardData
from vera.explain.expert_audit_builder import ExpertAuditBuilder  # NEW
from config import DEFAULT_LOOKBACK_YEARS
from utils.stock_name_fetcher import get_stock_name
# --- New Market Context Imports ---
from engine.asset_resolver import resolve_asset, resolve_market_index, resolve_sector_context
from market.index_risk import get_or_compute_index_risk
from market.amplifier import compute_market_amplifier
from market.alpha_headroom import compute_alpha_headroom
from db.market_context_repo import save_market_context
# --- Overlay Imports ---
from analysis.sector_overlay import build_sector_overlay
from analysis.market_regime import build_market_regime
from analysis.overlay_rules import run_overlay_rules, flags_to_json
from db.overlay import save_risk_overlay_snapshot
# --- AI CapEx Risk Imports ---
from core.ai_capex_risk_engine import should_run_ai_capex_risk, run_ai_capex_risk
from core.config_loader import load_ai_capex_rules

def run_snapshot(symbol: str, as_of_date=None, save_to_db: bool = False):
    """
    执行一次完整的分析快照生成流程
    
    Args:
        symbol: 资产代码（典范ID或原始代码）
        as_of_date: 评估基准日期
        save_to_db: 是否保存到数据库（默认False，由用户决定）
    """
    # 初始化数据库
    init_db()
    snapshot_id = str(uuid.uuid4())
    
    # 0. Get Stock Name (New Step)
    # Check if this asset is a known Sector Proxy (e.g. 3033.HK -> HK Tech Leaders)
    stock_name = get_stock_name(symbol)
    
    try:
        conn = get_connection()
        cur = conn.cursor()
        proxy_row = cur.execute("SELECT sector_name FROM sector_proxy_map WHERE proxy_etf_id = ?", (symbol,)).fetchone()
        if proxy_row and proxy_row[0]:
            stock_name = f"{proxy_row[0]} (ETF)"
        conn.close()
    except Exception as e:
        print(f"Proxy name check failed: {e}")

    print(f"[{symbol}] Identified as: {stock_name}")
    
    # --- 0.1 Asset & Market Resolution ---
    asset = resolve_asset(symbol)
    effective_id = asset.asset_id
    
    # Update Asset Table immediately (Enhanced with asset_type/index_role)
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO assets (asset_id, name, market, industry, asset_type, index_role)
        VALUES (?, ?, ?, 'Unknown', ?, ?)
        ON CONFLICT(asset_id) DO UPDATE SET
            name = CASE 
                WHEN assets.name IS NULL OR assets.name = assets.asset_id 
                THEN excluded.name 
                ELSE assets.name 
            END,
            market = COALESCE(assets.market, excluded.market),
            asset_type = COALESCE(assets.asset_type, excluded.asset_type),
            index_role = COALESCE(assets.index_role, excluded.index_role)
    """, (effective_id, stock_name, asset.market, asset.asset_type, asset.index_role))
    conn.commit()
    conn.close()

    # 1. 获取数据 (Price + Fundamentals)
    if as_of_date is None:
        end_date = datetime.now()
    else:
        end_date = as_of_date if isinstance(as_of_date, datetime) else datetime.combine(as_of_date, datetime.min.time())
        
    # FIX: Use 10-year lookback from the EVALUATION DATE
    start_date = end_date - timedelta(days=10 * 365)
    
    print(f"[{effective_id}] Loading local price data...")
    prices = load_price_series(effective_id, start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d"))
    
    # 加载价格序列
    if prices.empty:
        print(f"No price data for {effective_id} (Resolved from original: {symbol})")
        return None
        
    # Ensure correct data types and index
    import pandas as pd
    prices["trade_date"] = pd.to_datetime(prices["trade_date"])
    prices.set_index("trade_date", inplace=True)
    
    # Force numeric conversion to avoid string data issues
    for col in ["open", "high", "low", "close", "volume"]:
        if col in prices.columns:
            prices[col] = pd.to_numeric(prices[col], errors='coerce')
            
    prices.dropna(subset=["close"], inplace=True)
    
    # Calculate Change Percent (vs previous day)
    change_pct = 0.0
    if len(prices) >= 2:
        curr = prices["close"].iloc[-1]
        prev = prices["close"].iloc[-2]
        if prev > 0:
            change_pct = (curr - prev) / prev * 100.0
    
    # ✅ FIX: Handle empty data or data that ends before as_of_date
    # report_date should be the ACTUAL date of the latest price point used for fixed analytics
    data_date = prices.index.max().to_pydatetime()
    
    # If the user requested a specific past date, the engine will naturally look back from there.
    # If the user requested 'today' but market hasn't opened, we analyze up to the latest available.
    print(f"[{effective_id}] Analysis Baseline Date: {data_date.strftime('%Y-%m-%d')}")
    
    # ✅ Asset Type Routing: INDEX vs EQUITY
    if asset.asset_type == "INDEX":
        # 📊 MarketRiskCard Path (Index-specific)
        print(f"[{effective_id}] Detected as INDEX (role: {asset.index_role}) - Building MarketRiskCard")
        return _build_market_risk_card(
            symbol=effective_id,
            stock_name=stock_name,
            asset=asset,
            prices=prices,
            data_date=data_date,
            snapshot_id=snapshot_id
        )
    
    # 📈 Standard EquityRiskCard Path (continues below)
    print(f"[{effective_id}] Detected as {asset.asset_type or 'EQUITY'} - Building standard RiskCard")
    # 2. 获取基本面 (TTM + 历史)
    fundamentals, bank_metrics = fetch_fundamentals(effective_id, as_of_date=end_date)

    # 3. 陷阱与分红 (Trap Detection)
    is_value_trap = detect_value_trap(fundamentals)
    
    # 2. 风险计算 (Module 1)
    # RiskEngine requires a pandas Series with DatetimeIndex
    series = PriceSeries(prices)
    risk_results = RiskEngine.calculate_risk_metrics(prices["close"])
    
    # --- 核心状态机完善 (Module 1.1) ---
    from metrics.state_machine import StateMachine
    sm = StateMachine(effective_id)
    
    # 状态机检查：如果历史记录不足，自动回填
    try:
        # Avoid shadowing global get_connection
        _conn = get_connection()
        count_row = _conn.execute("SELECT COUNT(*) FROM drawdown_state_history WHERE asset_id = ?", (effective_id,)).fetchone()
        _conn.close()
        
        if count_row and count_row[0] < 10: # 认为历史缺失
            sm.run_backfill(prices["close"], lookback_days=200)
    except Exception as e:
        print(f"Error checking/running backfill for {effective_id}: {e}")
    
    # 状态机常规更新 (处理确认期、转移矩阵、风险事件)
    raw_info = risk_results.get('risk_state')
    confirmed_state_info = sm.update_state(
        trade_date=prices.index[-1].strftime("%Y-%m-%d"),
        raw_state=raw_info['state'],
        raw_metrics=raw_info.get('drawdown', {}), # Use drawdown metrics for history
        prices=prices["close"]
    )
    
    # 将确认后的状态回填到 risk_metrics
    # FIX: Calculate Numeric Progress (Drawdown Position: 0=Peak, 1=Valley)
    # The 'progress' field is used by RiskMatrix to determine Zone (Peak/Trough).
    rec_val = raw_info.get('drawdown', {}).get('recovery_pct', 1.0)
    numeric_progress = 1.0 - rec_val if rec_val is not None else 0.0
    
    risk_metrics = risk_results.copy()
    
    # 保持主周期 code 与确认后的对齐
    # 还原为单层状态逻辑
    risk_metrics = risk_results.copy()
    risk_metrics['risk_state'] = {
        "state": confirmed_state_info['state'],
        "desc": raw_info['desc'],
        "drawdown": raw_info['drawdown'],
        "recent_cycle": raw_info.get("recent_cycle"),
        "confirmed": True,
        "days": confirmed_state_info['days'],
        "transition_progress": confirmed_state_info.get('confirm_progress'),
        "has_new_high": raw_info.get("has_new_high", False),
        "progress": numeric_progress,
        "raw_metrics": raw_info.get('raw_metrics')
    }
    
    # --- Refine Market Index Logic (Link Sector -> Index) ---
    # We resolve sector context here to see if it dictates a specific index (e.g. HK_TECH -> HSTECH)
    # ❗ FIX: Use canonical asset_id
    sector_ctx = resolve_sector_context(asset.asset_id, data_date.strftime("%Y-%m-%d") if isinstance(data_date, datetime) else data_date)
    if sector_ctx and sector_ctx.market_index_id:
        # Override the generic market index (e.g. HSI default) with specific (e.g. HSTECH)
        # We need an AssetKey-like object or just the symbol. 
        # market_index variable is an AssetKey, so we update its symbol.
        from engine.asset_resolver import AssetKey
        # Assume generic type is INDEX for now
        market_index = AssetKey(
            asset_id=sector_ctx.market_index_id,
            symbol=sector_ctx.market_index_id,
            market=asset.market,
            asset_type="INDEX"
        )
        print(f"[{symbol}] Refined Market Index to: {market_index.symbol} (based on Sector: {sector_ctx.sector_code})")

    # --- Market Context: Index I-state -> Amplifier -> Alpha Headroom ---
    index_risk = get_or_compute_index_risk(
        index_symbol=market_index.symbol,
        as_of_date=data_date,
        price_loader=load_price_series,
        method_profile_id="default"
    )

    amp = compute_market_amplifier(
        stock_state=risk_metrics["risk_state"]["state"],
        index_state=index_risk["index_risk_state"],
        index_symbol=market_index.symbol
    )

    alpha = compute_alpha_headroom(
        index_state=index_risk["index_risk_state"],
        amplification_level=amp["amplification_level"]
    )

    # Simplified regime label v1.0 (no dispersion yet)
    if index_risk["index_risk_state"] == "I5":
        regime_label = "危机模式"
    elif amp["amplification_level"] in ("High","Extreme") and alpha["alpha_headroom"] in ("Low","None"):
        regime_label = "系统性压缩"
    elif amp["amplification_level"] in ("Medium","High") and alpha["alpha_headroom"] in ("Medium","Low"):
        regime_label = "结构性行情"
    else:
        regime_label = "良性分化"

    market_context = {
        "market_index_symbol": market_index.symbol,
        "index_risk_state": index_risk["index_risk_state"],
        "market_amplifier": amp,
        "alpha_headroom": alpha,
        "regime_label": regime_label
    }
    
    # 3. 估值锚选择 (Module 2)
    anchor = choose_valuation_anchor(fundamentals)
    # Note: fundamentals.npl_deviation passed from fetcher
    
    # --- 3.5 Historical Valuation Analysis (Module 3.5 - Simplified) ---
    # Direct DB Query approach (v2)
    pe_percentile = None
    valuation_path_result = None
    
    # Query history first (needed for both valuation and path)
    hist_pes = []
    hist_prices = []
    hist_dates = []
    
    # Try fetching history if symbol is valid, regardless of current PE presence
    # (Because we need history for INSUFFICIENT_HISTORY check even if current PE exists)
    try:
         _conn = get_connection()
         hist_rows = _conn.execute(
             """
             SELECT trade_date, close, pe, pe_ttm
             FROM vera_price_cache 
             WHERE symbol = ? AND (pe > 0 OR pe_ttm > 0)
             ORDER BY trade_date ASC
             """, 
             (asset.asset_id,)
         ).fetchall()
         _conn.close()
         
         if hist_rows:
             hist_dates = [r[0] for r in hist_rows]
             hist_prices = [r[1] for r in hist_rows]
             # Prefer PE TTM, Fallback to Static PE
             hist_pes = [r[3] if r[3] is not None else r[2] for r in hist_rows]
             # Filter out None/0 again if mixed
             hist_pes = [p for p in hist_pes if p and p > 0]
    except Exception as e:
         print(f"Error fetching history for {asset.asset_id}: {e}")

    # 1. Compute Valuation Status (Centralized Logic)
    from core.valuation_engine import compute_valuation_status
    
    # Pass TTM PE (can be None) and History (can be empty)
    # compute_valuation_status handles NO_PE and INSUFFICIENT_HISTORY
    val_info = compute_valuation_status(fundamentals.pe_ttm, hist_pes)
    
    # Update Fundamentals
    fundamentals.valuation_status = val_info.label_en
    fundamentals.valuation_status_key = val_info.key
    fundamentals.valuation_status_label_zh = val_info.label_zh
    fundamentals.valuation_status_label_en = val_info.label_en
    fundamentals.valuation_bucket = val_info.bucket
    fundamentals.valuation_color = val_info.color

    # 2. Calculate Percentile (Only if status allows / history sufficient)
    # If INSUFFICIENT_HISTORY or NO_PE, percentile is meaningless or N/A
    if val_info.key not in ["NO_PE", "INSUFFICIENT_HISTORY"] and hist_pes and fundamentals.pe_ttm:
         count_lower = sum(1 for p in hist_pes if p < fundamentals.pe_ttm)
         total = len(hist_pes)
         if total > 0:
             pe_percentile = int((count_lower / total) * 100)
    else:
         pe_percentile = None # Explicitly None for UI handling

    # 3. Valuation Path Analysis (Requires history)
    # Only run if we have some history, regardless of current status (e.g. might be NO_PE now but have history?)
    # Actually analyze_valuation_path needs current PE to compare with Peak.
    # If current PE is None (NO_PE), path analysis might fail or return Normal.
    if fundamentals.pe_ttm and hist_pes:
                 
                 # 3. Valuation Path Analysis
                 valuation_path_result = analyze_valuation_path(hist_pes, hist_prices, hist_dates)
                 
                 if valuation_path_result.get("path_type") != "Normal":
                     print(f"[{symbol}] Valuation Path: {valuation_path_result['path_type']} (Drawdown: {valuation_path_result['drawdown_pct']:.1%})")



    # 4. 陷阱与兑现 (Module 3)
    is_trap = detect_value_trap(fundamentals)
    # 5. 银行质量评分 (Module 5)
    bank_score = None
    if fundamentals.industry == "Bank" and bank_metrics:
        bank_score = calc_bank_quality_score(bank_metrics)
    
    # 5.4 Prepare Dividend & Earnings Inputs (NEW)
    from core.dividend_engine import evaluate_dividend_safety, DividendFacts
    from core.earnings_state import determine_earnings_state
    
    div_info = None
    earnings_info = None
    
    try:
        _conn = get_connection()
        # Fetch financial history (Annual/TTM)
        # Assuming financial_history stores report_date, eps_ttm, net_profit_ttm, dividend_amount
        # Order by date ASC
        fin_rows = _conn.execute("""
            SELECT report_date, eps_ttm, net_profit_ttm, dividend_amount 
            FROM financial_history 
            WHERE asset_id = ? 
            ORDER BY report_date ASC
        """, (asset.asset_id,)).fetchall()
        _conn.close()
        
        if fin_rows:
            import numpy as np
            
            # --- Earnings State Prep ---
            # eps_series: list of (date_str, eps_val)
            # Filter valid EPS
            eps_series = []
            for r in fin_rows:
                rd = r[0] if isinstance(r[0], str) else r[0].strftime("%Y-%m-%d")
                val = r[1] # eps_ttm
                if val is not None:
                    eps_series.append((rd, float(val)))
            
            if eps_series:
                earnings_info = determine_earnings_state(eps_series)
                
            # --- Dividend Safety Prep ---
            # Need: dps_5y_mean, dps_5y_std, cut_years, recovery
            # Filter rows with valid dividend_amount
            # Use last 10 years max
            div_history = []
            for r in fin_rows:
                 val = r[3] # dividend_amount
                 if val is not None:
                     div_history.append(float(val))
            
            if div_history:
                # Basic Metrics
                # Use last entry as TTM/Current (assuming data is up to date annual/TTM)
                current_div = div_history[-1]
                
                # Calc 5y stats
                hist_5y = div_history[-5:]
                mean_5y = np.mean(hist_5y) if hist_5y else None
                std_5y = np.std(hist_5y) if len(hist_5y) > 1 else 0.0
                
                # Calc cuts in last 10y
                hist_10y = div_history[-10:]
                cut_count = 0
                if len(hist_10y) > 1:
                    for i in range(1, len(hist_10y)):
                        if hist_10y[i] < hist_10y[i-1] * 0.99: # 1% tolerance
                            cut_count += 1
                            
                # Calc Recovery
                # Max in history (or last 10-15y)
                max_div = np.max(div_history)
                rec_progress = current_div / max_div if max_div and max_div > 0 else 1.0
                
                # Net Income TTM (Latest)
                ni_ttm = None
                if fin_rows[-1][2]: # net_profit_ttm
                    ni_ttm = float(fin_rows[-1][2])
                    
                facts = DividendFacts(
                    asset_id=asset.asset_id,
                    dividends_ttm=current_div,
                    net_income_ttm=ni_ttm,
                    dps_5y_mean=mean_5y,
                    dps_5y_std=std_5y,
                    cut_years_10y=cut_count,
                    dividend_recovery_progress=rec_progress
                )
                
                div_info = evaluate_dividend_safety(facts)
                
    except Exception as e:
        print(f"Warning: Failed to compute dividend/earnings state for {symbol}: {e}")

    # 5.5 质量缓冲评估 (Module 5.5 - NEW Quality Snapshot)
    from analysis.quality_assessment import build_quality_snapshot
    from db.quality_snapshot import save_quality_snapshot
    
    quality = build_quality_snapshot(
        asset_id=symbol,
        fundamentals=fundamentals,
        bank_metrics=bank_metrics,
        risk_context={'risk_state': risk_metrics['risk_state']['state']},
        dividend_info=div_info,
        earnings_info=earnings_info
    )
    
    if save_to_db:
        save_quality_snapshot(
            snapshot_id=snapshot_id,
            asset_id=symbol,
            revenue_stability_flag=quality.revenue_stability_flag,
            cyclicality_flag=quality.cyclicality_flag,
            moat_proxy_flag=quality.moat_proxy_flag,
            balance_sheet_flag=quality.balance_sheet_flag,
            cashflow_coverage_flag=quality.cashflow_coverage_flag,
            leverage_risk_flag=quality.leverage_risk_flag,
            payout_consistency_flag=quality.payout_consistency_flag,
            dilution_risk_flag=quality.dilution_risk_flag,
            regulatory_dependence_flag=quality.regulatory_dependence_flag,
            quality_buffer_level=quality.quality_buffer_level,
            quality_summary=quality.quality_summary,
            quality_template_name=quality.quality_template_name,
            notes=quality.notes
        )
        
    # 6. 统一结论生成 (Module 4)
    conclusion_input = ConclusionInput(
        max_drawdown=risk_metrics['max_drawdown'],
        annual_volatility=risk_metrics['annual_volatility'],
        is_value_trap=is_trap,
        dividend_yield=fundamentals.dividend_yield,
        buyback_ratio=fundamentals.buyback_ratio,
        valuation_status=fundamentals.valuation_status,
        industry=fundamentals.industry,
        bank_quality_score=None # 强制不入模；bank_score 仅用于 overlay 展示
    )
    conclusion = generate_conclusion(conclusion_input)
    
    # 7. VERA 2.0 风险矩阵生成 (New)
    risk_metrics['report_date'] = data_date.strftime("%Y-%m-%d")
    risk_card = build_risk_card(
        snapshot_id, 
        symbol, 
        prices["close"].iloc[-1], 
        risk_metrics, 
        as_of_date=data_date.strftime("%Y-%m-%d"),
        market_context=market_context
    )
    
    # 7.5 Risk × Quality 联动（NEW - Generate Quality Risk Interaction Flag）
    from analysis.quality_overlay_rules import quality_risk_interaction_flag, valuation_quality_interaction_flag
    
    dd_state = risk_metrics.get('risk_state', {}).get('state')
    quality_risk_flag = quality_risk_interaction_flag(
        dd_state=dd_state,
        quality_buffer_level=quality.quality_buffer_level
    )
    
    # 7.6 Valuation x Quality 联动
    val_quality_flag = valuation_quality_interaction_flag(
        valuation_status=fundamentals.valuation_status,
        quality_buffer_level=quality.quality_buffer_level
    )
    
    # 若有质量风险交互flag，写入behavior_flags表
    new_flags = []
    if quality_risk_flag: new_flags.append(quality_risk_flag)
    if val_quality_flag: new_flags.append(val_quality_flag)
    
    if new_flags and save_to_db:
        _conn = None
        try:
            _conn = get_connection()
            _cursor = _conn.cursor()
            
            for f in new_flags:
                _cursor.execute("""
                    INSERT INTO behavior_flags (snapshot_id, flag_code, flag_level, flag_dimension, flag_title, flag_description)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    snapshot_id,
                    f['flag_code'],
                    f['flag_level'],
                    f['flag_dimension'],
                    f['flag_title'],
                    f['flag_description']
                ))
            _conn.commit()
        except Exception as e:
            print(f"Warning: Failed to save behavior flags: {e}")
        finally:
            if _conn:
                _conn.close()
    
    # 获取刚生成的行为护栏
    behavior_flags = []
    try:
        _conn = get_connection()
        _cursor = _conn.cursor()
        _cursor.execute("""
            SELECT flag_code, flag_level, flag_dimension, flag_title, flag_description
            FROM behavior_flags
            WHERE snapshot_id = ?
        """, (snapshot_id,))
        behavior_flags = [dict(row) for row in _cursor.fetchall()]
        _conn.close()
    except Exception as e:
        print(f"Error fetching behavior flags: {e}")

    except Exception as e:
        print(f"Error fetching behavior flags: {e}")

    # --- 7.4 Unified Standardized Risk Structures ---
    # Individual Asset Risk
    asset_risk = {
        "state": risk_metrics["risk_state"]["state"],
        "label_zh": risk_metrics["risk_state"]["desc"],
        "drawdown": risk_metrics["risk_state"]["drawdown"],
        "path_risk": risk_card.get("path_risk_level", "MID") if risk_card else "MID",
        "recent_cycle": risk_metrics["risk_state"].get("recent_cycle"),
        "volatility_1y": risk_metrics.get("volatility_1y")
    }

    # Sector Overlay
    sector_ctx = resolve_sector_context(asset.asset_id, as_of_date=data_date.strftime("%Y-%m-%d"))
    sector_raw = build_sector_overlay(
        asset_id=asset.asset_id,
        as_of_date=data_date.strftime("%Y-%m-%d"),
        proxy_etf_id=sector_ctx.proxy_etf_id,
        sector_name=sector_ctx.sector_name,
        market_index_id=sector_ctx.market_index_id or "^GSPC",
        snapshot_id=snapshot_id
    )
    
    from core.config_loader import load_vera_rules
    lbls = load_vera_rules().get("d_state", {}).get("labels", {})
    s_code = sector_raw.get("sector_dd_state")
    s_label = lbls.get(s_code, {}).get("label_zh", "-") if s_code else "-"

    sector_risk = {
        "name": sector_raw.get("sector_name") or "Sector",
        "state": s_code,
        "label_zh": s_label,
        "recent_cycle": sector_raw.get("sector_recent_cycle"),
        "path_risk": sector_raw.get("sector_path_risk"),
        "drawdown": sector_raw.get("sector_drawdown", {}),
        "volatility_1y": sector_raw.get("sector_volatility_1y")
    }

    # Market Regime Overlay
    market_raw = build_market_regime(
        as_of_date=data_date.strftime("%Y-%m-%d"),
        asset_id=sector_ctx.market_index_id or "^GSPC",
        growth_proxy=sector_ctx.growth_proxy,
        value_proxy=sector_ctx.value_proxy,
        snapshot_id=snapshot_id
    )
    
    m_code = market_raw.get("market_dd_state")
    m_label = lbls.get(m_code, {}).get("label_zh", "-") if m_code else "-"

    market_risk = {
        "name": market_raw.get("market_index_id") or "Market",
        "state": m_code,
        "label_zh": m_label,
        "recent_cycle": market_raw.get("market_recent_cycle"),
        "path_risk": market_raw.get("market_path_risk"),
        "drawdown": market_raw.get("market_drawdown", {}),
        "volatility_1y": market_raw.get("market_volatility_1y")
    }
    
    # --- 7.5 Attribution Rule Mapping ---
    # Prepare dictionaries that match analysis/overlay_rules.py expectations
    overlay_ind = {
        "id": asset.asset_id,
        "state": asset_risk.get("state"),
        "label_zh": asset_risk.get("label_zh"),
        "path_risk": asset_risk.get("path_risk"),
        "recent_cycle": asset_risk.get("recent_cycle"),
        "position_pct": asset_risk.get("drawdown", {}).get("current_dd_pct", 0.0),
        "drawdown": asset_risk.get("drawdown"),
        "volatility_1y": asset_risk.get("volatility_1y")
    }
    overlay_sec = {
        "id": sector_raw.get("sector_etf_id"),
        "name": sector_risk.get("name"),
        "state": sector_risk.get("state"),
        "label_zh": sector_risk.get("label_zh"),
        "path_risk": sector_risk.get("path_risk"),
        "recent_cycle": sector_risk.get("recent_cycle"),
        "stock_vs_sector_rs_3m": sector_raw.get("stock_vs_sector_rs_3m", 0.0),
        "sector_vs_market_rs_3m": sector_raw.get("sector_vs_market_rs_3m", 0.0),
        "drawdown": sector_risk.get("drawdown"),
        "volatility_1y": sector_risk.get("volatility_1y")
    }
    overlay_mkt = {
        "id": market_raw.get("market_index_id"),
        "name": market_risk.get("name"),
        "state": market_risk.get("state"),
        "label_zh": market_risk.get("label_zh"),
        "path_risk": market_risk.get("path_risk"),
        "recent_cycle": market_risk.get("recent_cycle"),
        "market_regime_label": market_raw.get("market_regime_label") or m_label,
        "drawdown": market_risk.get("drawdown"),
        "volatility_1y": market_risk.get("volatility_1y")
    }

    overlay_summary, overlay_flags = run_overlay_rules(overlay_ind, overlay_sec, overlay_mkt)
    overlay_flags_json = flags_to_json(overlay_flags)
    
    # Save Overlay Snapshot
    if save_to_db:
        save_risk_overlay_snapshot(
            snapshot_id=snapshot_id,
            asset_id=symbol,
            as_of_date=data_date.strftime("%Y-%m-%d"),
            ind=overlay_ind,
            sec=overlay_sec,
            mkt=overlay_mkt,
            summary=overlay_summary,
            flags_json=overlay_flags_json
        )

    overlay = {
        "individual": overlay_ind,
        "sector": overlay_sec,
        "market": overlay_mkt,
        "summary": overlay_summary,
        "flags": overlay_flags
    }
    
    if risk_card is not None and "ind_position_pct" in overlay_ind:
        risk_card["ind_position_pct"] = overlay_ind["ind_position_pct"]

    # --- Expert Mode Audit Building (NEW) ---
    expert_audit = None
    formatted_history = []
    
    # 7.1 Try to Load History (Fragile part)
    try:
        conn = get_connection()
        rows = conn.execute("""
            SELECT trade_date, state, confirmed 
            FROM drawdown_state_history 
            WHERE asset_id = ? 
            ORDER BY trade_date DESC LIMIT 10
        """, (asset.asset_id,)).fetchall()
        conn.close()
        for r in reversed(rows):
             formatted_history.append({"t": r[0], "d_state": r[1], "confirmed": bool(r[2])})
    except Exception as e:
        print(f"Warning: Audit History load failed (usually due to missing table): {e}")

    # 7.2 Core Audit Build (Resilient part)
    try:
        eval_res = {
            "state": risk_metrics["risk_state"]["state"],
            "d_state": risk_metrics["risk_state"]["state"],
            "d_label_zh": risk_metrics["risk_state"]["desc"],
            "i_state": index_risk["index_risk_state"],
            "confidence": 0.85
        }
        vol_long = risk_metrics.get("volatility_10y", 0.3)
        vol_now = risk_metrics.get("volatility_1y", 0.3)
        estimated_vol_pct = max(0.01, min(0.99, 0.5 + (vol_now - vol_long) / (vol_long + 0.01)))
        
        indicators = {
            "vol_pctile": estimated_vol_pct,
            "recovery_progress": risk_metrics.get("recovery_progress", 0.0),
            "ind_position_pct": overlay_ind.get("position_pct", 0.5)
        }
        expert_audit = ExpertAuditBuilder.build(eval_res, indicators, formatted_history)
        
    except Exception as e:
        print(f"Critical Error: Expert Audit Builder failed: {e}")

    # --- 7.8 AI CapEx Risk Model (NEW) ---
    ai_rules = load_ai_capex_rules()
    ai_metrics = ai_capex_metrics_for_symbol(asset.asset_id, data_date.strftime("%Y-%m-%d"))
    
    # 获取资产标签和行业信息（用于准入判断）
    industry = "Unknown"
    tags = []
    try:
        _conn_meta = get_connection()
        _meta_row = _conn_meta.execute("SELECT industry, tags FROM assets WHERE asset_id = ?", (asset.asset_id,)).fetchone()
        _conn_meta.close()
        if _meta_row:
            industry = _meta_row[0] or "Unknown"
            tags = (_meta_row[1] or "").split(",") if _meta_row[1] else []
    except:
        pass

    asset_meta_for_ai = {
        "sector_name": sector_ctx.sector_name if sector_ctx else "Unknown",
        "industry_name": industry,
        "tags": tags,
    }

    # 全局强制激活检测
    import streamlit as st
    forced_active = st.session_state.get("ai_capex_forced_active", False)

    should_run_ai, ai_reason = should_run_ai_capex_risk(asset_meta_for_ai, ai_metrics, ai_rules)
    
    if forced_active:
        should_run_ai = True
        ai_reason = "FORCED_BY_USER_GLOBAL_TOGGLE"

    if should_run_ai:
        ai_overlay = run_ai_capex_risk(ai_metrics, ai_rules)
        print(f"[{symbol}] AI CapEx Risk Model Enabled: {ai_overlay['scoring']['overall_ai_capex_risk_level']}")
    else:
        ai_overlay = {"enabled": False, "reason": ai_reason}
        if ai_reason != "capex_intensity_too_low": # Avoid too much noise
            print(f"[{symbol}] AI CapEx Risk Model Skipped: {ai_reason}")

    # 8. 仪表盘数据生成 (Module 6)
    dashboard_data = generate_dashboard_data(
        symbol=asset.asset_id, # Use canonical ID
        price=prices["close"].iloc[-1],
        report_date=data_date.strftime("%Y-%m-%d"),
        risk_metrics=risk_metrics,
        fundamentals=fundamentals,
        conclusion=conclusion,
        is_value_trap=is_trap,
        risk_card=risk_card,
        behavior_flags=behavior_flags,
        bank_score=bank_score,
        bank_metrics=bank_metrics,
        market_context=market_context,
        overlay=overlay,
        quality_obj=quality, # NEW: pass live quality results
        pe_percentile=pe_percentile,
        valuation_path=valuation_path_result,   # NEW: Path Analysis
        change_percent=change_pct, # NEW
        expert_audit=expert_audit,  # NEW
        ai_capex_overlay=ai_overlay # NEW
    )
    
    # 8.5 Behavior Engine (Phase 4)
    from core.behavior_engine import evaluate_behavior
    
    d_state = risk_metrics.get('risk_state', {}).get('state')
    risk_quad = risk_card.get('risk_quadrant') if risk_card else None
    val_bucket = getattr(fundamentals, 'valuation_bucket', None)
    qual_level = getattr(quality, 'quality_buffer_level', 'WEAK') if quality else 'WEAK'

    if d_state and risk_quad and val_bucket:
        try:
            val_status_key = getattr(fundamentals, 'valuation_status_key', None)
            behavior_res = evaluate_behavior(
                d_state=d_state,
                quadrant=risk_quad,
                valuation_bucket=val_bucket,
                quality_level=qual_level,
                valuation_status_key=val_status_key
            )
            
            # Overwrite Dashboard Data with Rule Engine Decision
            dashboard_data.behavior_suggestion = behavior_res.action_label_zh
            dashboard_data.cognitive_warning = behavior_res.note_zh
            
            # Inject action code into overlay for debugging/verification
            if dashboard_data.overlay is None: dashboard_data.overlay = {}
            dashboard_data.overlay['behavior_action_code'] = behavior_res.action_code
            dashboard_data.overlay['behavior_action_label_zh'] = behavior_res.action_label_zh
            
            print(f"[{symbol}] Behavior Rule Triggered: {behavior_res.triggered_rule_name} -> {behavior_res.action_code}")
            
        except Exception as be_err:
             print(f"[{symbol}] Behavior Engine Error: {be_err}")
    
    save_full_snapshot(snapshot_id, asset.asset_id, data_date.strftime("%Y-%m-%d"), 
                       risk_metrics, fundamentals, conclusion, 
                       anchor, is_trap, 0, bank_score, 
                       current_price=prices["close"].iloc[-1], # Pass current price
                       save_to_db=save_to_db)
                       
    # persist market context into risk_card_snapshot (best-effort)
    if save_to_db:
        save_market_context(
            snapshot_id=snapshot_id,
            symbol=symbol,
            market_index_symbol=market_index.symbol,
            amplifier=amp,
            alpha=alpha,
            regime_label=regime_label
        )
                       
    print(f"[{symbol}] Analysis Complete. Conclusion: {conclusion}")
    return dashboard_data

def ai_capex_metrics_for_symbol(symbol: str, report_date: str) -> Dict[str, float]:
    """获取 AI CapEx 评估所需的财务指标"""
    metrics = {}
    cols = [
        "capex_cash_additions_6m", "capex_cash_additions_3m", "ppe_total_net",
        "ppe_servers_net", "ppe_buildings_net", "depreciation_total_6m",
        "amortization_intangibles_6m", "depreciation_ppe_implied_6m",
        "lease_ppe_finance_net", "lease_rou_assets_operating",
        "lease_capex_finance_additions_6m", "lease_capex_operating_additions_6m",
        "leases_not_commenced_datacenter", "strategic_ai_investment_commitment_total",
        "strategic_ai_investment_funded", "revenue_ttm", "operating_income_ttm",
        "operating_cashflow_ttm", "total_assets", "net_debt"
    ]
    try:
        conn = get_connection()
        query = f"SELECT {', '.join(cols)} FROM financial_history WHERE asset_id = ? AND report_date <= ? ORDER BY report_date DESC LIMIT 1"
        row = conn.execute(query, (symbol, report_date)).fetchone()
        if row:
            metrics = dict(row)
    except Exception as e:
        print(f"Error fetching AI CapEx metrics for {symbol}: {e}")
    finally:
        if 'conn' in locals():
            conn.close()
    return metrics

def save_full_snapshot(snapshot_id, symbol, as_of_date, risk_metrics, 
                       fundamentals, conclusion, anchor, is_trap, payout_score, bank_score, 
                       current_price=None, save_to_db=False):
    """保存到 analysis_snapshot 和 metric_details 表"""
    conn = get_connection()
    cursor = conn.cursor()
    
    # A. 插入 analysis_snapshot (Phase 3 Core Table)
    # Determine basic risk level string for DB (high/med/low) - simplified
    risk_level = "Medium"
    if (risk_metrics.get('max_drawdown') is not None and risk_metrics['max_drawdown'] < -0.40) or \
       (risk_metrics.get('annual_volatility') is not None and risk_metrics['annual_volatility'] >= 0.35):
        risk_level = "High"
    elif (risk_metrics.get('max_drawdown') is not None and risk_metrics['max_drawdown'] > -0.25) and \
         (risk_metrics.get('annual_volatility') is not None and risk_metrics['annual_volatility'] <= 0.18):
        risk_level = "Low"
    
    # 只有用户明确选择保存时才写入数据库
    if save_to_db:
        cursor.execute("""
            INSERT INTO analysis_snapshot 
            (snapshot_id, asset_id, as_of_date, risk_level, valuation_anchor, 
             valuation_status, payout_score, is_value_trap, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (snapshot_id, symbol, as_of_date, risk_level, anchor, 
              fundamentals.valuation_status, payout_score, is_trap, 
              datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
          
        # B. 插入 metric_details
        def safe_val(v):
            import math
            if v is None or (isinstance(v, float) and math.isnan(v)):
                return 0.0
            return v

        # 1. Max Drawdown
        cursor.execute("""
            INSERT INTO metric_details (snapshot_id, metric_key, value)
            VALUES (?, ?, ?)
        """, (snapshot_id, "max_drawdown", safe_val(risk_metrics.get('max_drawdown'))))
        
        # 2. Volatility
        cursor.execute("""
            INSERT INTO metric_details (snapshot_id, metric_key, value)
            VALUES (?, ?, ?)
        """, (snapshot_id, "annual_volatility", safe_val(risk_metrics.get('annual_volatility'))))
        
        # 3. Bank Score (if applicable)
        if bank_score is not None:
            cursor.execute("""
                INSERT INTO metric_details (snapshot_id, metric_key, value)
                VALUES (?, ?, ?)
            """, (snapshot_id, "bank_quality_score", safe_val(bank_score)))
            
        # 4. Valuation Metrics
        cursor.execute("""
            INSERT INTO metric_details (snapshot_id, metric_key, value)
            VALUES (?, ?, ?)
        """, (snapshot_id, "pe_ttm", safe_val(fundamentals.pe_ttm)))
        
        cursor.execute("""
            INSERT INTO metric_details (snapshot_id, metric_key, value)
            VALUES (?, ?, ?)
        """, (snapshot_id, "pb_ratio", safe_val(fundamentals.pb_ratio)))

        # 5. Current Price (Critical for Snapshot View)
        if current_price is not None:
             cursor.execute("""
                INSERT INTO metric_details (snapshot_id, metric_key, value)
                VALUES (?, ?, ?)
            """, (snapshot_id, "current_price", safe_val(current_price)))
            
        conn.commit()
    
    conn.close()


def _build_market_risk_card(symbol: str, stock_name: str, asset, prices, data_date, snapshot_id: str):
    """
    📊 MarketRiskCard Builder (Index-specific path)
    
    For INDEX assets (SPX, NDX, DJI, HSI, etc.), build a simplified risk card
    focused on market-level metrics without fundamentals/valuation layers.
    """
    from metrics.risk_engine import RiskEngine
    from analysis.price_series import PriceSeries
    from metrics.state_machine import StateMachine
    
    # 1. Calculate Risk Metrics (same as equity)
    series = PriceSeries(prices)
    risk_results = RiskEngine.calculate_risk_metrics(prices["close"])
    
    # 2. State Machine (I-state for index)
    sm = StateMachine(symbol)
    
    # Backfill check
    try:
        _conn = get_connection()
        count_row = _conn.execute("SELECT COUNT(*) FROM drawdown_state_history WHERE asset_id = ?", (symbol,)).fetchone()
        _conn.close()
        
        if count_row and count_row[0] < 10:
            sm.run_backfill(prices["close"], lookback_days=200)
    except Exception as e:
        print(f"Error in state machine backfill for {symbol}: {e}")
    
    # State machine update
    raw_info = risk_results.get('risk_state')
    confirmed_state_info = sm.update_state(
        trade_date=prices.index[-1].strftime("%Y-%m-%d"),
        raw_state=raw_info['state'],
        raw_metrics=raw_info.get('raw_metrics', {}), # Use fallback
        prices=prices["close"]
    )
    
    # Confirmed metrics
    # FIX: Numeric Progress for Index
    rec_val = raw_info.get('drawdown', {}).get('recovery_pct', 1.0)
    numeric_progress = 1.0 - rec_val if rec_val is not None else 0.0

    risk_metrics = risk_results.copy()
    # 保持主周期 code 与确认后的对齐
    risk_metrics['risk_state'] = {
        "state": confirmed_state_info['state'],
        "desc": raw_info['desc'],
        "drawdown": raw_info['drawdown'],
        "confirmed": True,
        "days": confirmed_state_info['days'],
        "transition_progress": confirmed_state_info.get('confirm_progress'),
        "progress": numeric_progress,
        "raw_metrics": raw_info.get('raw_metrics')
    }
    
    # 3. Build MarketRiskCard (no valuation/fundamentals)
    from analysis.risk_matrix import build_risk_card
    
    risk_metrics['report_date'] = data_date.strftime("%Y-%m-%d")
    risk_card = build_risk_card(
        snapshot_id=snapshot_id,
        asset_id=symbol,
        price=float(prices["close"].iloc[-1]),
        risk_metrics=risk_metrics,
        as_of_date=data_date.strftime("%Y-%m-%d"),
        market_context=None  # INDEX is the market, no context needed
    )
    
    # 4. Generate Dashboard Data (market-specific)
    from analysis.dashboard import generate_dashboard_data
    from analysis.valuation import AssetFundamentals
    
    # Create minimal fundamentals for compatibility
    minimal_fundamentals = AssetFundamentals(
        symbol=symbol,
        pe_ttm=None,
        pb_ratio=None,
        revenue_ttm=0.0,
        net_profit_ttm=0.0,
        dividend_yield=0.0,
        buyback_ratio=0.0,
        industry="Index",
        valuation_status="N/A"
    )
    
    # Market-specific conclusion
    d_state = risk_metrics['risk_state']['state']
    conclusion = f"市场指数 {stock_name} 当前处于 {d_state} 状态。"
    
    if asset.index_role == "MARKET":
        conclusion += " 此为主要市场基准指数，反映广泛市场风险环境。"
    elif asset.index_role == "GROWTH_PROXY":
        conclusion += " 此为成长风格代理指数，反映科技/成长板块趋势。"
    elif asset.index_role == "VALUE_PROXY":
        conclusion += " 此为价值风格代理指数，反映传统行业趋势。"
    
    dashboard = generate_dashboard_data(
        symbol=symbol,
        price=float(prices["close"].iloc[-1]),
        report_date=data_date.strftime("%Y-%m-%d"),
        risk_metrics=risk_metrics,
        fundamentals=minimal_fundamentals,
        conclusion=conclusion,
        is_value_trap=False,
        risk_card=risk_card,
        behavior_flags=[],
        market_context=None,
        overlay={"asset_type": "INDEX", "index_role": asset.index_role}
    )
    
    print(f"[{symbol}] MarketRiskCard snapshot completed: {snapshot_id}")
    
    return {
        "snapshot_id": snapshot_id,
        "symbol": symbol,
        "asset_type": "INDEX",
        "index_role": asset.index_role,
        "dashboard": dashboard,
        "risk_card": risk_card
    }
