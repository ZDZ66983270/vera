import json
import sqlite3
from typing import Optional, Dict
from db.connection import get_connection

class RiskProfile:
    LEVEL_CONSERVATIVE = "CONSERVATIVE"
    LEVEL_BALANCED = "BALANCED"
    LEVEL_AGGRESSIVE = "AGGRESSIVE"

    def __init__(self, level: str, drawdown: str, verbosity: str, color: str):
        self.risk_tolerance_level = level
        self.drawdown_emphasis = drawdown
        self.warning_verbosity = verbosity
        self.color_intensity = color

def calculate_level(total_score: int) -> str:
    """
    0–3   → CONSERVATIVE
    4–6   → BALANCED
    7–10  → AGGRESSIVE
    """
    if total_score <= 3:
        return RiskProfile.LEVEL_CONSERVATIVE
    elif total_score <= 6:
        return RiskProfile.LEVEL_BALANCED
    else:
        return RiskProfile.LEVEL_AGGRESSIVE

def get_display_preferences(level: str) -> Dict[str, str]:
    """
    映射等级到展示偏好
    """
    mapping = {
        RiskProfile.LEVEL_CONSERVATIVE: {
            "drawdown_emphasis": "HIGH",
            "warning_verbosity": "DETAILED",
            "color_intensity": "LOW"
        },
        RiskProfile.LEVEL_BALANCED: {
            "drawdown_emphasis": "MEDIUM",
            "warning_verbosity": "STANDARD",
            "color_intensity": "NORMAL"
        },
        RiskProfile.LEVEL_AGGRESSIVE: {
            "drawdown_emphasis": "LOW",
            "warning_verbosity": "MINIMAL",
            "color_intensity": "GRAYSCALE"
        }
    }
    return mapping.get(level, mapping[RiskProfile.LEVEL_BALANCED])

def save_user_profile(total_score: int, answer_set: Dict[str, str]):
    """
    计算并保存用户风险画像
    """
    level = calculate_level(total_score)
    prefs = get_display_preferences(level)
    
    conn = get_connection()
    try:
        # 我们只保留最新的一个 profile
        conn.execute("DELETE FROM user_risk_profiles")
        conn.execute("""
            INSERT INTO user_risk_profiles (
                risk_tolerance_level, total_score, answer_set,
                drawdown_emphasis, warning_verbosity, color_intensity
            ) VALUES (?, ?, ?, ?, ?, ?)
        """, (
            level, total_score, json.dumps(answer_set),
            prefs['drawdown_emphasis'], prefs['warning_verbosity'], prefs['color_intensity']
        ))
        conn.commit()
    finally:
        conn.close()

def get_current_profile() -> Optional[RiskProfile]:
    """
    获取当前生效的风险画像，如果没有则返回 None
    """
    conn = get_connection()
    try:
        row = conn.execute("""
            SELECT risk_tolerance_level, drawdown_emphasis, warning_verbosity, color_intensity
            FROM user_risk_profiles
            ORDER BY created_at DESC LIMIT 1
        """).fetchone()
        
        if row:
            return RiskProfile(row[0], row[1], row[2], row[3])
        return None
    finally:
        conn.close()

def reset_profile():
    """
    重置风险画像
    """
    conn = get_connection()
    try:
        conn.execute("DELETE FROM user_risk_profiles")
        conn.commit()
    finally:
        conn.close()
