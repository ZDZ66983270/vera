from functools import lru_cache
import yaml
from pathlib import Path
from typing import Dict, Any

@lru_cache()
def load_vera_rules() -> Dict[str, Any]:
    """加载 VERA 规则配置"""
    base_dir = Path(__file__).resolve().parent.parent
    cfg_path = base_dir / "config" / "vera_rules.yaml"
    
    if not cfg_path.exists():
        cfg_path = Path("config/vera_rules.yaml")
    
    if not cfg_path.exists():
        raise FileNotFoundError(f"VERA rules config not found: {cfg_path}")
        
    with cfg_path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)

@lru_cache()
def load_ai_capex_rules() -> Dict[str, Any]:
    """加载 AI CapEx 风险规则配置"""
    base_dir = Path(__file__).resolve().parent.parent
    cfg_path = base_dir / "config" / "ai_capex_risk_rules.yaml"
    
    if not cfg_path.exists():
        cfg_path = Path("config/ai_capex_risk_rules.yaml")
    
    if not cfg_path.exists():
        # Fallback to empty if not found, though should exist
        return {}
        
    with cfg_path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)

@lru_cache()
def load_csp_rules() -> Dict[str, Any]:
    """加载 CSP 许可与合约筛选规则配置"""
    base_dir = Path(__file__).resolve().parent.parent
    # 尝试多种路径为了兼容性
    cfg_paths = [
        base_dir / "config" / "csp_permission_rules.yaml",
        Path("config/csp_permission_rules.yaml")
    ]
    
    for p in cfg_paths:
        if p.exists():
            with p.open("r", encoding="utf-8") as f:
                return yaml.safe_load(f)
                
    # 如果没找到，返回空字典或默认值，以免报错
    return {}
def load_yaml_config(path: str) -> Dict[str, Any]:
    """通用 YAML 加载器 (无缓存版本，供特定需求使用)"""
    p = Path(path)
    if not p.exists():
        # 尝试相对 config 目录的路径
        base_dir = Path(__file__).resolve().parent.parent
        p_alt = base_dir / "config" / p.name
        if p_alt.exists():
            p = p_alt
    
    if not p.exists():
        return {}
        
    with p.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)
