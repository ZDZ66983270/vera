# vera/explain/expert_audit_builder.py

from typing import Dict, Any, List, Optional
from vera.explain.counter_evidence_defs import get_checklist_for_state

class ExpertAuditBuilder:
    """
    专家审计构造器 (ExpertAuditBuilder)
    
    职责：
    1. 聚合判定引擎输出的各项指标（Evidence）
    2. 生成证据列表（基于布尔逻辑及阈值对照）
    3. 构造状态迁移历史路径
    4. 挂载状态专属的反证清单 (Counter-evidence Checklist)
    """

    @staticmethod
    def build(
        eval_result: Dict[str, Any], 
        indicators: Dict[str, Any], 
        history: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        
        # 1. 核心状态信息
        d_state = eval_result.get("d_state") or eval_result.get("state") # "D3", "D5" etc
        i_state = eval_result.get("i_state", "UNKNOWN")
        
        # 2. 构造证据列表 (Evidence)
        # 这里反映的是模型“为什么这么判”
        evidence = []
        
        # 波动率证据
        vol_pct = indicators.get("vol_pctile", 0.0)
        evidence.append({
            "key": "vol_extreme",
            "label": "波动率是否处于极端（博弈）区间",
            "value": vol_pct >= 0.90,
            "metric": {"name": "波动率分位点", "value": f"{vol_pct*100:.1f}%", "threshold": "90.0%"}
        })
        
        # 修复进度证据
        rec_prog = indicators.get("recovery_progress", indicators.get("recovery", 0.0))
        evidence.append({
            "key": "structural_repair",
            "label": "结构性修复是否已确立 (Rec >= 30%)",
            "value": rec_prog >= 0.30,
            "metric": {"name": "当前修复进度", "value": f"{rec_prog*100:.1f}%", "threshold": ">= 30.0%"}
        })
        
        # 价格位置证据
        pos_pct = indicators.get("ind_position_pct", 0.0)
        evidence.append({
            "key": "lower_zone_limit",
            "label": "价格是否处于极低分位区间 (Lower Zone)",
            "value": pos_pct <= 0.25,
            "metric": {"name": "价格历史分位", "value": f"{pos_pct*100:.1f}%", "threshold": "<= 25.0%"}
        })
        
        # 波动率对冲证据 (New)
        evidence.append({
            "key": "options_hedge_needed",
            "label": "期权保护性对冲需求是否触发",
            "value": vol_pct >= 0.75,
            "metric": {"name": "波动率风险等级", "value": "HIGH" if vol_pct >= 0.75 else "NORMAL", "threshold": "75th Pctile"}
        })

        # 3. 价格信号与置信度
        price_signal = {
            "status": eval_result.get("price_signal_status", "STABLE"),
            "confidence": float(eval_result.get("confidence", 0.85))
        }

        # 4. 迁移路径 (Path)
        # 取最近 5 次记录
        path = history[-5:] if history else []

        # 5. 反证清单 (Counter-evidence)
        checklist = get_checklist_for_state(d_state)

        return {
            "state": {
                "d_state": d_state,
                "i_state": i_state,
                "label": eval_result.get("d_label_zh", "未定义状态")
            },
            "price_signal": price_signal,
            "evidence": evidence,
            "transition_path": path,
            "counter_evidence_checklist": checklist
        }
