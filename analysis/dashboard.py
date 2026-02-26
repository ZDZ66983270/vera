from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from analysis.valuation import AssetFundamentals
from analysis.bank_quality import BankMetrics
from db.connection import get_connection

def _format_percent(x: Optional[float]) -> Optional[str]:
    if x is None:
        return None
    try:
        return f"{round(x * 100, 1)}%"
    except Exception:
        return None

# Global Name Mapping Fallback (Single Source of Truth) - DEPRECATED
# Use assets table instead
ASSET_NAME_MAP = {}

def get_asset_name(symbol: str) -> str:
    """Robust name resolution: 1. DB assets.symbol_name -> 2. Symbol ID"""
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM assets WHERE asset_id = ?", (symbol,))
        row = cursor.fetchone()
        if row and row[0] and row[0] != symbol and row[0] != "-":
            return row[0]
            
        # Fallback for indices
        indices = {
            "SPX": "标普500", "NDX": "纳斯达克100", "DJI": "道琼斯工业", 
            "HSI": "恒生指数", "HSTECH": "恒生科技",
            "HSCE": "国企指数",
            "HSCC": "红筹指数"
        }
        if symbol in indices: return indices[symbol]
        
    except Exception as e:
        print(f"Error fetching symbol name for {symbol}: {e}")
    finally:
        if conn: conn.close()
    
    # Final fallback: strip namespace
    return symbol.split(":")[-1]


PositionZone = str # typing compatibility

def _build_position_card(position: Dict[str, Any]) -> Dict[str, Any]:
    """
    Position card (v2):
    - Input uses history percentile (price_percentile: 0..1) as the only numeric anchor
    - Endpoints (<=5% or >=95%) do not show percentage
    - No dependency on Path/Drawdown/Risk wording
    """

    price_percentile: Optional[float] = position.get("price_percentile")  # 0..1
    zone: PositionZone = "Unknown"
    show_pct = False
    label = "当前位置：—"

    if price_percentile is None:
        zone = "Unknown"
        show_pct = False
        label = "当前位置：—"
    elif price_percentile >= 0.95:
        zone = "Peak"
        show_pct = False
        label = "当前位置：阶段高点"
    elif price_percentile <= 0.05:
        zone = "Trough"
        show_pct = False
        label = "当前位置：阶段低点"
    else:
        zone = "Middle"  # Simplified from Upper/Lower/Middle logic
        show_pct = True
        label = "当前位置：区间中部"

    return {
        "zone": zone,  # Peak / Middle / Trough / Unknown
        "price_percentile": price_percentile,
        "show_percentile_pct": show_pct,
        "percentile_pct": f"{price_percentile*100:.0f}%" if (show_pct and price_percentile is not None) else None,
        "label": label,
    }


@dataclass
class DashboardData:
    """
    前端仪表盘所需的 ViewModel
    """
    # Meta
    symbol: str
    symbol_name: str
    price: float
    change_percent: Optional[float] # New field
    report_date: str
    overall_conclusion: str
    
    # Structured Data Layers (dicts)
    path: Dict[str, Any]
    position: Dict[str, Any]
    market_environment: Optional[Dict[str, Any]]
    value: Dict[str, Any]
    overlay: Dict[str, Any]
    
    # Legacy / Direct Fields (Kept for compatibility where needed or simplicity)
    behavior_suggestion: str 
    cognitive_warning: str   
    
    # Optional fields with defaults (must come after non-default fields)
    quality: Optional[Dict[str, Any]] = None  # NEW: Quality Buffer assessment
    ai_capex_overlay: Optional[Dict[str, Any]] = None  # NEW: AI CapEx Risk Overlay
    behavior_flags: list = field(default_factory=list)
    risk_card: Optional[Dict[str, Any]] = None # Keep raw card just in case
    
    # Helper fields for specific UI sections if not covered by above
    risk_events: list = field(default_factory=list)
    path_risk_history: list = field(default_factory=list)
    
    # Missing fields required by app.py
    recovery_time: Optional[float] = None
    recovery_period: Optional[str] = None
    volatility_period: Optional[str] = None
    
    # Valuation Path Analysis (NEW)
    valuation_path: Optional[Dict[str, Any]] = None
    
    # Expert Mode Audit Data (NEW)
    expert_audit: Optional[Dict[str, Any]] = None
    
    # Computed Properties (Helpers for UI compatibility)
    @property
    def max_drawdown(self): return self.risk_card.get('max_drawdown', 0.0)
    
    @property
    def volatility(self): return self.risk_card.get('annual_volatility', 0.0)

    @property
    def mdd_period(self): 
        peak = self.risk_card.get('mdd_peak_date')
        valley = self.risk_card.get('mdd_valley_date')
        return f"{peak} - {valley}" if peak and valley else None

    @property
    def mdd_peak_price(self): return self.risk_card.get('mdd_peak_price')
    
    @property
    def mdd_valley_price(self): return self.risk_card.get('mdd_valley_price')

    @property
    def stock_name(self): return self.symbol_name

    @property
    def asset_id(self): return self.symbol


def generate_dashboard_data(
    symbol: str, 
    price: float,
    report_date: str,
    risk_metrics: Dict[str, float],
    fundamentals: AssetFundamentals,
    conclusion: str,
    is_value_trap: bool = False,
    risk_card: Optional[Dict[str, Any]] = None,
    behavior_flags: list = None,
    bank_score: Optional[int] = None,
    bank_metrics: Optional[BankMetrics] = None,
    market_context: Optional[Dict[str, Any]] = None,
    overlay: Optional[Dict[str, Any]] = None,
    quality_obj: Any = None,
    pe_percentile: Optional[int] = None,  # NEW: Historical PE Percentile
    valuation_path: Optional[Dict[str, Any]] = None,  # NEW: Valuation Path
    change_percent: Optional[float] = None, # NEW
    expert_audit: Optional[Dict[str, Any]] = None,  # NEW: Expert Mode
    ai_capex_overlay: Optional[Dict[str, Any]] = None  # NEW
) -> DashboardData:
    """
    模块 6: 仪表盘数据生成器 (ViewModel Builder)
    """
    
    # 0. Fetch Symbol Name (Robustly)
    symbol_name = get_asset_name(symbol)

    # 1. 行为建议 & 认知预警生成
    suggestion = "保持观察"
    warning = "无特殊风险"
    
    # Calculate Periods for Dashboard
    mdd_period = None
    if risk_metrics.get('mdd_peak_date') and risk_metrics.get('mdd_valley_date'):
        mdd_period = f"{risk_metrics['mdd_peak_date']} - {risk_metrics['mdd_valley_date']}"

    recovery_period = None
    if risk_metrics.get('mdd_valley_date') and risk_metrics.get('recovery_end_date'):
        recovery_period = f"{risk_metrics['mdd_valley_date']} - {risk_metrics['recovery_end_date']}"
    
    if "不适合" in conclusion:
        suggestion = "禁止开仓"
        warning = "风险超出承受极限，切勿抱有侥幸心理"
    elif "价值陷阱" in conclusion:
        suggestion = "避免买入"
        warning = "看似便宜但可能是陷阱，警惕估值错觉"
    elif "长期持有" in conclusion:
        suggestion = "建议分批买入，长期持有"
        warning = "短期波动可能依然存在，需克服波动焦虑"
    elif "谨慎关注" in conclusion:
        suggestion = "小仓位尝试或继续等待"
        warning = "便宜但基本面一般，警惕时间成本"
        
    # 2. 构造 Structured Layers from inputs
    
    # -------- Path Layer (NEW 3-Layer Structure) --------
    path_card_data = {}
    if risk_card:
        risk_state_node = risk_metrics.get("risk_state", {})
        path_card_data = {
            "path_risk_level": risk_card.get("path_risk_level", "MID"),
            "path_text": risk_card.get("path_interpretation"),
            # NEW Structured fields
            "d_state_primary": risk_state_node.get("d_state_primary"),
            "d_state_overlay": risk_state_node.get("d_state_overlay"),
            "drawdown": risk_state_node.get("drawdown"),
            # Legacy fields for safety
            "state": risk_state_node.get("state"),
            "has_new_high": risk_state_node.get("has_new_high", False),
            "recent_cycle": risk_state_node.get("recent_cycle"),
        }
    
    path_risk_level = path_card_data.get("path_risk_level", "MID")
    
    # -------- Position Layer --------
    # Map from flat risk_card to expected position dict
    # -------- Position Layer --------
    # Map from flat risk_card to expected position dict
    raw_pos = {}
    if risk_card:
        # Calculate Current Drawdown (From Peak)
        # Current DD = Progress * Max DD
        # FIX: Prioritize ind_position_pct as the authoritative progress signal
        progress = risk_card.get("ind_position_pct")
        if progress is None:
             progress = risk_card.get("drawdown_stage")
             
        max_dd = risk_card.get("max_drawdown")
        raw_pos = {
            # Use price_percentile for position logic (v2)
            "price_percentile": progress,
            "progress": progress, 
            "drawdown": risk_metrics.get("current_drawdown"), # Use authoritative value
        }
    
    # Pass ONLY position dict (v2 logic no longer needs path_risk)
    position_card = _build_position_card(raw_pos)
    
    # Add interpretation from risk_card if needed, but new logic uses labels
    if risk_card and risk_card.get("position_interpretation"):
         position_card["interpretation"] = risk_card.get("position_interpretation")

    # -------- Market Regime Layer --------
    market_env = None
    if market_context:
        market_env = {
            "market_index": market_context.get("market_index_symbol"),
            "index_risk_state": market_context.get("index_risk_state"),
            "regime_label": market_context.get("regime_label"),
            "amplification_level": market_context.get("market_amplifier", {}).get("amplification_level"),
            "alpha_headroom": market_context.get("alpha_headroom", {}).get("alpha_headroom"),
            "notes": (
                market_context.get("market_amplifier", {}).get("notes", [])
                + market_context.get("alpha_headroom", {}).get("notes", [])
            ),
        }

    # 4. 构造 ViewModel
    anchor_name = "PE" 
    if fundamentals.net_profit_ttm <= 0: anchor_name = "PS"
    elif fundamentals.industry in ["Bank", "Insurance", "RealEstate", "Utility"]: anchor_name = "PB"
    
    # Map current valuation value based on anchor logic
    current_val = fundamentals.pe_ttm
    
    if anchor_name == "PB":
        current_val = fundamentals.pb_ratio
    elif anchor_name == "PS":
         if fundamentals.revenue_ttm and fundamentals.revenue_ttm > 0 and fundamentals.net_profit_ttm != 0 and fundamentals.pe_ttm:
             current_val = (fundamentals.pe_ttm * fundamentals.net_profit_ttm) / fundamentals.revenue_ttm
             if current_val < 0: current_val = abs(current_val)
         else:
             current_val = 0.0

    bank_data = None
    is_bank = (fundamentals.industry == "Bank")
    if is_bank and bank_metrics:
        bank_data = {
            "is_bank": True,
            "quality_score": bank_score,
            "bank_metrics": {
                "npl_deviation": getattr(fundamentals, 'npl_deviation', 0.0) or 0.0,
                "npl_ratio": getattr(bank_metrics, 'npl_ratio', 0.0) or 0.0,
                "special_mention_ratio": getattr(bank_metrics, 'special_mention_ratio', 0.0) or 0.0,
                "provision_coverage": getattr(bank_metrics, 'provision_coverage', 0.0) or 0.0,
                "allowance_to_loan": getattr(bank_metrics, 'allowance_to_loan', 0.0) or 0.0,
            },
            "desc": "质量优异" if (bank_score and bank_score >= 1) else "质量一般"
        }
    else:
        bank_data = {"is_bank": False}

    # 3. 获取历史风险路径和事件 (Helpers)
    risk_events = []
    conn2 = None
    try:
        conn2 = get_connection()
        cursor = conn2.cursor()
        cursor.execute("""
            SELECT event_type, severity_level, event_start_date, state_from, state_to
            FROM risk_events
            WHERE asset_id = ?
            ORDER BY event_start_date DESC LIMIT 5
        """, (symbol,))
        risk_events = [dict(row) for row in cursor.fetchall()]
    except Exception as e:
        print(f"Error fetching risk events: {e}")
    finally:
        if conn2:
            conn2.close()

    # 3.5 Fetch Quality Buffer data (NEW)
    quality_data = None
    
    # ❗ Priority 1: Use live quality_obj if provided (fixes no-save missing data)
    if quality_obj:
        quality_data = {
            "quality_template_name": getattr(quality_obj, 'quality_template_name', 'General'),
            "quality_buffer_level": getattr(quality_obj, 'quality_buffer_level', 'N/A'),
            "quality_summary": getattr(quality_obj, 'quality_summary', ''),
            "balance_sheet_flag": getattr(quality_obj, 'balance_sheet_flag', None),
            "cashflow_coverage_flag": getattr(quality_obj, 'cashflow_coverage_flag', None),
            "leverage_risk_flag": getattr(quality_obj, 'leverage_risk_flag', None),
            "revenue_stability_flag": getattr(quality_obj, 'revenue_stability_flag', None),
            "cyclicality_flag": getattr(quality_obj, 'cyclicality_flag', None),
            "moat_proxy_flag": getattr(quality_obj, 'moat_proxy_flag', None),
            "payout_consistency_flag": getattr(quality_obj, 'payout_consistency_flag', None),
            "dilution_risk_flag": getattr(quality_obj, 'dilution_risk_flag', None),
            "regulatory_dependence_flag": getattr(quality_obj, 'regulatory_dependence_flag', None),
            
            # New Ext: Dividend & Earnings
            "dividend_safety_level": getattr(quality_obj, 'dividend_safety_level', None),
            "dividend_safety_label_zh": getattr(quality_obj, 'dividend_safety_label_zh', None),
            "dividend_safety_score": getattr(quality_obj, 'dividend_safety_score', None),
            "dividend_notes": getattr(quality_obj, 'notes', {}).get("dividend_notes", []),
            
            "earnings_state_code": getattr(quality_obj, 'earnings_state_code', None),
            "earnings_state_label_zh": getattr(quality_obj, 'earnings_state_label_zh', None),
            "earnings_state_desc_zh": getattr(quality_obj, 'earnings_state_desc_zh', None),
        }
    
    # Priority 2: Fallback to DB (historical view)
    if not quality_data:
        conn = None
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT quality_buffer_level, quality_summary,
                       balance_sheet_flag, cashflow_coverage_flag, leverage_risk_flag,
                       revenue_stability_flag, cyclicality_flag, moat_proxy_flag,
                       payout_consistency_flag, dilution_risk_flag, regulatory_dependence_flag,
                       quality_template_name,
                       dividend_safety_level, dividend_safety_label_zh,
                       earnings_state_code, earnings_state_label_zh, earnings_state_desc_zh,
                       quality_notes
                FROM quality_snapshot
                WHERE asset_id = ?
                ORDER BY created_at DESC
                LIMIT 1
            """, (symbol,))
            row = cursor.fetchone()
            if row:
                import json
                notes_raw = row[17]
                notes_dict = {}
                if notes_raw:
                    try:
                        notes_dict = json.loads(notes_raw)
                    except:
                        pass
                
                quality_data = {
                    "quality_buffer_level": row[0],
                    "quality_summary": row[1],
                    "balance_sheet_flag": row[2],
                    "cashflow_coverage_flag": row[3],
                    "leverage_risk_flag": row[4],
                    "revenue_stability_flag": row[5],
                    "cyclicality_flag": row[6],
                    "moat_proxy_flag": row[7],
                    "payout_consistency_flag": row[8],
                    "dilution_risk_flag": row[9],
                    "regulatory_dependence_flag": row[10],
                    "quality_template_name": row[11],
                    
                    "dividend_safety_level": row[12],
                    "dividend_safety_label_zh": row[13],
                    "earnings_state_code": row[14],
                    "earnings_state_label_zh": row[15],
                    "earnings_state_desc_zh": row[16],
                    "dividend_notes": notes_dict.get("dividend_notes", [])
                }
        except Exception as e:
            print(f"Note: Quality snapshot extraction failed: {e}")
        finally:
            if conn:
                conn.close()

    # 4. Return DashboardData (With updated structure)
    return DashboardData(
        symbol=symbol,
        symbol_name=symbol_name,
        price=price,
        change_percent=change_percent,
        report_date=report_date,
        overall_conclusion=conclusion,
        path=path_card_data,
        position=position_card,
        market_environment=market_env,
        value={
            "valuation_status": getattr(fundamentals, "valuation_status", None),
            # New Rule Engine Fields
            "valuation_status_key": getattr(fundamentals, "valuation_status_key", None),
            "valuation_status_label_zh": getattr(fundamentals, "valuation_status_label_zh", None),
            "valuation_status_label_en": getattr(fundamentals, "valuation_status_label_en", None),
            "valuation_bucket": getattr(fundamentals, "valuation_bucket", None),
            "valuation_color": getattr(fundamentals, "valuation_color", None),
            
            "is_value_trap": is_value_trap,
            "anchor": anchor_name,
            "current_val": current_val,
            "pe_ttm": fundamentals.pe_ttm,
            "pe_static": fundamentals.pe_static,
            "eps_ttm": fundamentals.eps_ttm,
            "pb": fundamentals.pb_ratio,
            "dividend_yield": fundamentals.dividend_yield,
            "buyback_ratio": fundamentals.buyback_ratio,
            "pe_percentile": pe_percentile
        },
        overlay={**bank_data, **(overlay or {})},
        behavior_suggestion=suggestion,
        cognitive_warning=warning,
        behavior_flags=behavior_flags if behavior_flags else [],
        quality=quality_data,  # NEW
        ai_capex_overlay=ai_capex_overlay,  # NEW
        risk_card=risk_card,
        risk_events=risk_events,
        recovery_time=risk_metrics.get('recovery_time'),
        recovery_period=recovery_period,
        volatility_period=risk_metrics.get('volatility_period'),
        valuation_path=valuation_path,  # NEW
        expert_audit=expert_audit  # NEW
    )
