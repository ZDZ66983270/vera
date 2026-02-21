from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from core.config_loader import load_vera_rules

@dataclass
class BehaviorResult:
    action_code: str
    action_label_zh: str
    action_label_en: str
    note_zh: str
    note_en: str
    triggered_rule_name: str
    priority: int

def _map_d_state_group(d_state: str, groups: Dict[str, List[str]]) -> str:
    for group_name, states in groups.items():
        if d_state in states:
            return group_name
    return "UNKNOWN"

def _map_quality_bucket(quality_level: str, buckets: Dict[str, List[str]]) -> str:
    # Rule engine expects exact match from config lists
    # Input quality_level might be "HIGH", "MID", "LOW", "STRONG", "MODERATE", "WEAK"
    # Config has: STRONG: [HIGH, STRONG], AVERAGE: [MID, MODERATE], ...
    if not quality_level:
        return "WEAK" # Default conservative
        
    q_upper = quality_level.upper()
    for bucket_name, variants in buckets.items():
        if q_upper in variants:
            return bucket_name
    return "WEAK" # Default fallback

def evaluate_behavior(
    d_state: str,
    quadrant: str,       # Q1, Q2, Q3, Q4
    valuation_bucket: str, # CHEAP, NEUTRAL, EXPENSIVE
    quality_level: str,  # HIGH/MID/LOW or STRONG/MODERATE/WEAK
    rules_cfg: Dict[str, Any] | None = None,
    valuation_status_key: str | None = None  # NEW: For insufficient history check
) -> BehaviorResult:
    """
    根据 D-State, Struct Quadrant, Valuation Bucket, Quality Bucket
    匹配 vera_rules.yaml 中的行为规则。
    """
    if rules_cfg is None:
        rules_cfg = load_vera_rules()
    
    # Pre-process: Force NEUTRAL for insufficient history
    if valuation_status_key in ["NO_PE", "INSUFFICIENT_HISTORY"]:
        valuation_bucket = "NEUTRAL"
    
    brules = rules_cfg["behavior"]
    
    # 1. Map Inputs to Groups
    d_group = _map_d_state_group(d_state, brules["d_state_groups"])
    q_bucket = _map_quality_bucket(quality_level, brules["quality_buckets"])
    
    # 2. Iterate Rules (Ordered by priority desc in YAML usually, but let's sort to be safe if not)
    # YAML list order is implicitly priority if processed sequentially, but rules have "priority" field.
    # We should sort by priority desc.
    
    rule_list = sorted(brules["rules"], key=lambda x: x.get("priority", 0), reverse=True)
    
    for rule in rule_list:
        when = rule["when"]
        
        # Check conditions (AND logic across dimensions, OR logic within dimension list)
        
        # D-State Group
        if d_group not in when.get("d_state_group", []):
            continue
            
        # Quadrant
        if quadrant not in when.get("quadrant", []):
            continue
            
        # Valuation Bucket
        if valuation_bucket not in when.get("valuation_bucket", []):
            continue
            
        # Quality Bucket
        if q_bucket not in when.get("quality_bucket", []):
            continue
            
        # MATCH FOUND
        action = rule["action"]
        return BehaviorResult(
            action_code=action["code"],
            action_label_zh=action["label_zh"],
            action_label_en=action["label_en"],
            note_zh=action["note_zh"],
            note_en=action["note_en"],
            triggered_rule_name=rule["name"],
            priority=rule.get("priority", 0)
        )
        
    # Default Fallback (Should be covered by "Default neutral" rule in YAML, but safety first)
    return BehaviorResult(
        action_code="WATCH",
        action_label_zh="观望 (Fallback)",
        action_label_en="Watch (Fallback)",
        note_zh="未匹配到特定规则，默认观望。",
        note_en="No specific rule matched.",
        triggered_rule_name="HardFallback",
        priority=-1
    )
