import json

def _dd_rank(dd: str | None) -> int:
    # D1..D5 -> 1..5，未知 -> 0
    if not dd or not dd.startswith("D"):
        return 0
    try:
        return int(dd[1:])
    except Exception:
        return 0

def run_overlay_rules(ind: dict, sec: dict, mkt: dict) -> tuple[str, list[dict]]:
    """
    返回 (summary, flags)
    flags: [{code, level, title, detail}]
    """
    flags: list[dict] = []
    
    ind_dd = ind.get("state")
    sec_dd = sec.get("state")
    mkt_dd = mkt.get("state")
    
    ind_path = ind.get("path_risk")
    mkt_path = mkt.get("path_risk")
    # sec_path = sec.get("sector_path_risk") # Unused variable
    
    rs_stock_sector = sec.get("stock_vs_sector_rs_3m")
    rs_sector_market = sec.get("sector_vs_market_rs_3m")
    regime = mkt.get("market_regime_label")
    
    # Derivations
    rs_stock_market = None
    if rs_stock_sector is not None and rs_sector_market is not None:
        rs_stock_market = rs_stock_sector + rs_sector_market

    # ---- Group A: risk source attribution (choose one) ----
    src = None
    if _dd_rank(mkt_dd) >= 4 or mkt_path == "HIGH":
        src = "SYSTEMIC"
        flags.append({
            "code": "SRC_SYSTEMIC",
            "level": "HIGH",
            "title": "系统性风险主导",
            "detail": "市场处于 D4/D5 状态或路径风险为高。"
        })
    elif _dd_rank(ind_dd) >= 4 and _dd_rank(sec_dd) >= 4:
        src = "SECTOR"
        flags.append({
            "code": "SRC_SECTOR",
            "level": "HIGH",
            "title": "板块共振风险",
            "detail": "个股与板块均处于深幅回撤状态。"
        })
    elif _dd_rank(ind_dd) >= 4 and (_dd_rank(sec_dd) <= 2 or (_dd_rank(sec_dd) <= 3 and rs_stock_sector < -0.08)):
        src = "INDIVIDUAL"
        flags.append({
            "code": "SRC_INDIVIDUAL",
            "level": "HIGH",
            "title": "个股特异性风险",
            "detail": "个股处于深幅回撤，而板块/大盘未见同等量级压力。"
        })
    else:
        src = "MIXED"
        flags.append({
            "code": "SRC_MIXED",
            "level": "MED",
            "title": "混合风险源",
            "detail": "风险无法由单一层级完全解释。"
        })
        
    # ---- Group B: divergence layers ----
    # 1. Stock vs Sector
    if rs_stock_sector is not None:
        if rs_stock_sector < -0.05:
            flags.append({
                "code": "DIV_STOCK_SECTOR_NEG", 
                "level": "MED",
                "title": "落后板块",
                "detail": f"个股相对板块 RS(3m)={rs_stock_sector:.2%}."
            })
        elif rs_stock_sector > 0.05:
            flags.append({
                "code": "DIV_STOCK_SECTOR_POS", 
                "level": "MED",
                "title": "领先板块",
                "detail": f"个股相对板块 RS(3m)={rs_stock_sector:.2%}."
            })

    # 2. Sector vs Market
    if rs_sector_market is not None:
        if rs_sector_market < -0.05:
            flags.append({
                "code": "DIV_SECTOR_MKT_NEG", 
                "level": "MED",
                "title": "板块拖累",
                "detail": f"所属板块明显跑输大盘 RS(3m)={rs_sector_market:.2%}."
            })
        elif rs_sector_market > 0.05:
            flags.append({
                "code": "DIV_SECTOR_MKT_POS", 
                "level": "LOW",
                "title": "强势板块",
                "detail": f"所属板块领跑大盘 RS(3m)={rs_sector_market:.2%}."
            })

    # 3. Stock vs Market (Global Context)
    if rs_stock_market is not None:
        if rs_stock_market < -0.10:
             flags.append({
                "code": "DIV_STOCK_MKT_NEG", 
                "level": "MED",
                "title": "全市场弱势",
                "detail": f"个股相对于全市场大盘 RS(3m)={rs_stock_market:.2%}."
            })

    # ---- Group D: market regime modifier ----
    # NOTE: regime string is now in Chinese from snapshot_builder
    if regime == "系统性压缩" or regime == "Systemic Compression":
        flags.append({
            "code": "REGIME_COMPRESSION", 
            "level": "MED",
            "title": "相关性上升",
            "detail": "系统性压缩降低了个股选择的优势，风险趋于同步。"
        })
    elif regime == "良性分化" or regime == "Healthy Differentiation":
        flags.append({
            "code": "REGIME_DIFFERENTIATION", 
            "level": "LOW",
            "title": "分化行情",
            "detail": "市场环境允许板块和个股展现更强的特异性走势。"
        })

    # ---- Summary composer (1-2 sentences) ----
    parts = []
    # Base source
    if src == "SYSTEMIC":
        parts.append("风险主要受全市场系统性压力主导。")
    elif src == "SECTOR":
        parts.append("风险由板块性调整驱动，个股与板块共振明显。")
    elif src == "INDIVIDUAL":
        parts.append("风险高度特异化，主要源自个股自身因素。")
    else:
        parts.append("风险驱动因素相对分散。")
    
    # Relative strength context
    if rs_stock_sector is not None and rs_sector_market is not None:
        if rs_stock_sector < -0.05 and rs_sector_market > 0.05:
            parts.append("个股受自身偏差影响，在强势板块中表现掉队。")
        elif rs_stock_sector > 0.05 and rs_sector_market < -0.05:
            parts.append("尽管板块拖累明显，但个股展现出极强的相对抗性。")
        elif rs_stock_sector < -0.05 and rs_sector_market < -0.05:
            parts.append("个股承受来自板块加速下挫与自身弱势的双重压力。")
        elif rs_stock_market and rs_stock_market > 0.10:
            parts.append("个股目前处于显著的高阿尔法强势通道中。")
            
    summary = " ".join(parts[:2])
    return summary, flags

def flags_to_json(flags: list[dict]) -> str:
    return json.dumps(flags, ensure_ascii=False)
