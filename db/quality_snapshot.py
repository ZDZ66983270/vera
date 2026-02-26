# db/quality_snapshot.py
from __future__ import annotations

import json
from typing import Dict, Any, Optional
from db.connection import get_connection

# Allowed flags based on VERA 2.5 spec
BQ_FLAG = {"STRONG", "MID", "WEAK", "-"}
CYCL_FLAG = {"LOW", "MID", "HIGH", "-"}
GOV_FLAG = {"POSITIVE", "NEUTRAL", "NEGATIVE", "-"}
DIL_FLAG = {"LOW", "HIGH", "-"}
BUFFER_LEVEL = {"STRONG", "MODERATE", "WEAK", "-"}

def _assert_enum(name: str, value: Optional[str], allowed: set):
    if value is None:
        return "-"
    v = value.strip().upper()
    if v not in allowed:
        return "-" # Graceful fallback
    return v

def save_quality_snapshot(
    *,
    snapshot_id: str,
    asset_id: str,
    revenue_stability_flag: str,
    cyclicality_flag: str,
    moat_proxy_flag: str,
    balance_sheet_flag: str,
    cashflow_coverage_flag: str,
    leverage_risk_flag: str,
    payout_consistency_flag: str,
    dilution_risk_flag: str,
    regulatory_dependence_flag: str,
    quality_buffer_level: str,
    quality_summary: str,
    quality_template_name: str = "General",
    dividend_safety_level: Optional[str] = None,
    dividend_safety_label_zh: Optional[str] = None,
    earnings_state_code: Optional[str] = None,
    earnings_state_label_zh: Optional[str] = None,
    earnings_state_desc_zh: Optional[str] = None,
    notes: Optional[Dict[str, Any]] = None,
):
    # ---- Enum validation ----
    revenue_stability_flag = _assert_enum("revenue_stability_flag", revenue_stability_flag, BQ_FLAG)
    cyclicality_flag = _assert_enum("cyclicality_flag", cyclicality_flag, CYCL_FLAG)
    moat_proxy_flag = _assert_enum("moat_proxy_flag", moat_proxy_flag, BQ_FLAG)

    balance_sheet_flag = _assert_enum("balance_sheet_flag", balance_sheet_flag, BQ_FLAG)
    cashflow_coverage_flag = _assert_enum("cashflow_coverage_flag", cashflow_coverage_flag, BQ_FLAG)
    leverage_risk_flag = _assert_enum("leverage_risk_flag", leverage_risk_flag, CYCL_FLAG)

    payout_consistency_flag = _assert_enum("payout_consistency_flag", payout_consistency_flag, GOV_FLAG)
    dilution_risk_flag = _assert_enum("dilution_risk_flag", dilution_risk_flag, DIL_FLAG)
    regulatory_dependence_flag = _assert_enum("regulatory_dependence_flag", regulatory_dependence_flag, CYCL_FLAG)

    quality_buffer_level = _assert_enum("quality_buffer_level", quality_buffer_level, BUFFER_LEVEL)

    # ---- Notes handling ----
    notes_json = json.dumps(notes or {}, ensure_ascii=False)

    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()

        # Consistent with VERA 2.5 unified schema
        cur.execute(
            """
            INSERT OR REPLACE INTO quality_snapshot (
                snapshot_id, asset_id,
                revenue_stability_flag, cyclicality_flag, moat_proxy_flag,
                balance_sheet_flag, cashflow_coverage_flag, leverage_risk_flag,
                payout_consistency_flag, dilution_risk_flag, regulatory_dependence_flag,
                quality_buffer_level, quality_summary,
                quality_notes, quality_template_name,
                dividend_safety_level, dividend_safety_label_zh,
                earnings_state_code, earnings_state_label_zh, earnings_state_desc_zh
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                snapshot_id, asset_id,
                revenue_stability_flag, cyclicality_flag, moat_proxy_flag,
                balance_sheet_flag, cashflow_coverage_flag, leverage_risk_flag,
                payout_consistency_flag, dilution_risk_flag, regulatory_dependence_flag,
                quality_buffer_level, quality_summary,
                notes_json, quality_template_name,
                dividend_safety_level, dividend_safety_label_zh,
                earnings_state_code, earnings_state_label_zh, earnings_state_desc_zh
            )
        )
        conn.commit()
    finally:
        if conn:
            conn.close()
