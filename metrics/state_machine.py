import json
import pandas as pd
import numpy as np
from datetime import datetime
from db.connection import get_connection

# 转移规则矩阵：带有风险语义和事件标记
TRANSITION_RULES = {
    "D0": {
        "allowed": ["D0", "D1"],
        "semantics": {
            "D0→D0": {"risk": "稳定", "desc": "持续在高位"},
            "D0→D1": {"risk": "警示", "desc": "开始回撤"}
        }
    },
    "D1": {
        "allowed": ["D0", "D1", "D2"],
        "semantics": {
            "D1→D0": {"risk": "修复", "desc": "回到高位"},
            "D1→D1": {"risk": "震荡", "desc": "浅回撤中"},
            "D1→D2": {"risk": "警示", "desc": "回撤加深"}
        }
    },
    "D2": {
        "allowed": ["D1", "D2", "D3"],
        "semantics": {
            "D2→D1": {"risk": "修复", "desc": "回撤减轻"},
            "D2→D2": {"risk": "压力", "desc": "中度回撤中"},
            "D2→D3": {"risk": "危险", "desc": "进入深度回撤"}
        }
    },
    "D3": {
        "allowed": ["D2", "D3", "D4"],
        "semantics": {
            "D3→D2": {"risk": "修复", "desc": "脱离谷底"},
            "D3→D3": {"risk": "脆弱", "desc": "深度回撤中"},
            "D3→D4": {"risk": "警示", "desc": "开始反弹（需验证）"}
        }
    },
    "D4": {
        "allowed": ["D3", "D4", "D5"],
        "semantics": {
            "D4→D3": {"risk": "极危险", "desc": "反弹夭折，二次探底", "event": "SECONDARY_DRAWDOWN"},
            "D4→D4": {"risk": "不稳", "desc": "早期反弹震荡"},
            "D4→D5": {"risk": "积极", "desc": "反弹确立，进入修复期"}
        }
    },
    "D5": {
        "allowed": ["D2", "D4", "D5", "D6"],
        "semantics": {
            "D5→D2": {"risk": "突发", "desc": "修复失败，重回中度回撤", "event": "FAILED_RECOVERY"},
            "D5→D4": {"risk": "警示", "desc": "修复遇阻，回落至早期反弹区"},
            "D5→D5": {"risk": "稳健", "desc": "修复趋势延续"},
            "D5→D6": {"risk": "积极", "desc": "突破关键阻力，进入完全修复期"}
        }
    },
    "D6": {
        "allowed": ["D5", "D6"],
        "semantics": {
            "D6→D6": {"risk": "强势", "desc": "高位震荡，结构完全修复"},
            "D6→D5": {"risk": "警示", "desc": "上攻乏力，回撤压力重现"},
            "D5→D6": {"risk": "积极", "desc": "重返强势区间"}
        }
    }
}

STATE_VERSION = "v1.1"
STATE_CONFIRM_DAYS = 7

class StateMachine:
    def __init__(self, asset_id: str):
        self.asset_id = asset_id

    def update_state(self, trade_date: str, raw_state: str, raw_metrics: dict, prices: pd.Series = None, commit: bool = True, _conn=None):
        """
        核心转移逻辑：判定是否确认切换状态，并记录事件
        """
        conn = _conn if _conn else get_connection()
        cursor = conn.cursor()

        # 1. 获取最新确认记录
        cursor.execute("""
            SELECT confirmed_state, confirm_counter, days_in_state 
            FROM drawdown_state_history 
            WHERE asset_id = ? AND trade_date < ?
            ORDER BY trade_date DESC LIMIT 1
        """, (self.asset_id, trade_date))
        # Use dict-like access if possible, or numeric
        row = cursor.fetchone()
        
        last_history = None
        if row:
            # Simple dict mapping if Row object
            if hasattr(row, 'keys'):
                last_history = dict(row)
            else:
                last_history = {
                    'confirmed_state': row[0],
                    'confirm_counter': row[1],
                    'days_in_state': row[2]
                }

        # 初始状态处理
        if not last_history:
            confirmed_state = raw_state
            confirm_counter = 0 
            days_in_state = 1
            is_transition = False
            prev_state = None
        else:
            last_confirmed = last_history['confirmed_state']
            last_counter = last_history['confirm_counter']
            last_days = last_history['days_in_state']
            
            if raw_state == last_confirmed:
                confirmed_state = last_confirmed
                confirm_counter = 0  
                days_in_state = last_days + 1
                is_transition = False
                prev_state = last_confirmed
            else:
                new_counter = last_counter + 1
                risk_stable = self._check_risk_stability(prices, end_date=trade_date) if prices is not None else True
                transition_allowed = self._is_transition_allowed(last_confirmed, raw_state)
                
                if new_counter >= STATE_CONFIRM_DAYS and risk_stable and transition_allowed:
                    confirmed_state = raw_state
                    confirm_counter = 0
                    days_in_state = 1
                    is_transition = True
                    prev_state = last_confirmed
                    self._check_and_log_event(prev_state, confirmed_state, raw_metrics, trade_date, _conn=conn)
                else:
                    confirmed_state = last_confirmed
                    confirm_counter = new_counter
                    days_in_state = last_days + 1
                    is_transition = False
                    prev_state = last_confirmed

        # 2. 写入历史
        cursor.execute("""
            INSERT OR REPLACE INTO drawdown_state_history 
            (asset_id, trade_date, raw_state, raw_metrics_snapshot, 
             confirmed_state, confirm_counter, days_in_state, 
             is_transition, prev_state, state_version)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            self.asset_id, trade_date, raw_state, json.dumps(raw_metrics or {}),
            confirmed_state, confirm_counter, days_in_state,
            1 if is_transition else 0, prev_state, STATE_VERSION
        ))
        
        if commit:
            conn.commit()
            
        if not _conn:
            conn.close()
        
        return {
            "state": confirmed_state,
            "days": days_in_state,
            "is_transition": is_transition,
            "confirm_progress": f"{confirm_counter}/{STATE_CONFIRM_DAYS}" if confirm_counter > 0 else None
        }

    def run_backfill(self, prices: pd.Series, lookback_days: int = 200):
        if len(prices) < lookback_days:
            lookback_days = len(prices)
        backfill_series = prices.tail(lookback_days)
        from metrics.risk_engine import RiskEngine
        conn = get_connection()
        try:
            for i in range(1, len(backfill_series) + 1):
                sub_series = prices.iloc[:len(prices)-len(backfill_series)+i]
                current_date = sub_series.index[-1].strftime("%Y-%m-%d")
                raw_info = RiskEngine.calculate_path_risk_state(sub_series)
                self.update_state(
                    trade_date=current_date,
                    raw_state=raw_info['state'],
                    raw_metrics=raw_info.get('raw_metrics', {}),
                    prices=sub_series,
                    commit=False, 
                    _conn=conn
                )
            conn.commit()
        finally:
            conn.close()

    def _is_transition_allowed(self, from_state, to_state):
        if from_state not in TRANSITION_RULES: return False
        return to_state in TRANSITION_RULES[from_state]["allowed"]

    def _check_risk_stability(self, prices: pd.Series, end_date: str = None):
        if end_date:
            prices = prices[:end_date]
        if len(prices) < 20: return True
        returns = prices.pct_change().dropna()
        if returns.empty: return True
        curr_vol = returns.tail(20).std() * np.sqrt(252)
        hist_returns = returns.tail(504)
        if len(hist_returns) >= 100:
            rolling_vols = hist_returns.rolling(20).std() * np.sqrt(252)
            p80 = rolling_vols.quantile(0.8)
            vol_spike = curr_vol > p80
        else:
            prev_vol = returns.iloc[-40:-20].std() * np.sqrt(252) if len(returns) > 40 else curr_vol
            vol_spike = curr_vol > (prev_vol * 1.2)
        return not vol_spike

    def _check_and_log_event(self, state_from, state_to, metrics, trade_date: str = None, _conn=None):
        key = f"{state_from}→{state_to}"
        if state_from in TRANSITION_RULES:
            rule = TRANSITION_RULES[state_from]["semantics"].get(key)
            if rule and "event" in rule:
                event_type = rule["event"]
                severity = "极危险" 
                log_date = trade_date if trade_date else datetime.now().date()
                conn = _conn if _conn else get_connection()
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR IGNORE INTO risk_events 
                    (asset_id, event_type, event_start_date, state_from, state_to, 
                     severity_level, volatility_at_event)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    self.asset_id, event_type, log_date, 
                    state_from, state_to, severity, (metrics or {}).get('volatility', 0)
                ))
                if not _conn:
                    conn.commit()
                    conn.close()
