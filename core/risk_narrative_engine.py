import yaml
import os
import pandas as pd
from typing import Dict, Any, List, Optional
from core.config_loader import load_yaml_config

class RiskNarrativeEngine:
    """
    VERA Risk Narrative Engine
    Generates structured risk narratives based on long-cycle and short-window metrics.
    """
    
    def __init__(self):
        config_path = "/Users/zhangzy/My Docs/Privates/22-AI编程/VERA/config/risk_narrative_rules.yaml"
        self.rules = load_yaml_config(config_path)
    
    def generate_narrative(self, metrics: Dict[str, Any]) -> Dict[str, Any]:
        """
        Input: Dictionary of raw risk metrics.
        Output: Structured sections with narrative strings.
        """
        if not self.rules:
            return {"error": "Rules not loaded"}
        
        # 1. Map metrics to bands
        mapped_bands = self._map_to_bands(metrics)
        
        # 2. Determine composite pattern
        composite_pattern = self._match_composite_pattern(mapped_bands, metrics)
        
        # 3. Assemble sections
        sections = self._assemble_sections(mapped_bands, composite_pattern, metrics)
        
        return sections

    def _map_to_bands(self, metrics: Dict[str, Any]) -> Dict[str, Any]:
        """
        Determines which 'band' (LOW/MID/HIGH etc.) each metric falls into.
        """
        bands = {}
        
        # A. Position Band (10Y)
        pos_pct = metrics.get('position_10y_pctile', 50.0)
        bands['position'] = self._find_band(pos_pct, self.rules['long_cycle']['position_bands'])
        
        # B. Max MDD Band (10Y)
        max_dd_10y_abs = abs(metrics.get('max_drawdown_10y_pct', 0.0))
        bands['max_dd_10y'] = self._find_band(max_dd_10y_abs, self.rules['long_cycle']['max_dd_bands'])
        
        # C. DD Ratio Band (1Y vs 10Y)
        dd_ratio = metrics.get('dd_1y_vs_10y_ratio', 0.0)
        bands['dd_ratio'] = self._find_band(dd_ratio, self.rules['short_window']['dd_ratio_bands'])
        
        # D. Speed Band (Relative to 10Y)
        # speed_ratio = days_to_max_dd_10y / days_to_max_dd_1y
        d10 = metrics.get('days_to_max_dd_10y', 1)
        d1 = metrics.get('days_to_max_dd_1y', 1)
        speed_ratio = d10 / d1 if d1 > 0 else 1.0
        bands['speed'] = self._find_band(speed_ratio, self.rules['short_window']['speed_bands'])
        
        return bands

    def _find_band(self, value: float, bands_config: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Helper to find the correct band for a value."""
        for band in bands_config:
            r = band['range']
            if r[0] <= value <= r[1]:
                return band
        # Fallback to last if slightly outside (e.g. > 100) or first
        return bands_config[-1] if value > bands_config[-1]['range'][1] else bands_config[0]

    def _match_composite_pattern(self, bands: Dict[str, Any], metrics: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Matches composite patterns based on band IDs and context."""
        patterns = self.rules.get('composite_patterns', [])
        
        val_bucket = metrics.get('valuation_bucket', 'NEUTRAL')
        qual_grade = metrics.get('quality_grade', 'MEDIUM')
        
        for p in patterns:
            when = p['when']
            match = True
            
            # Check position_band
            if 'position_band' in when and bands['position']['key'] not in when['position_band']:
                match = False
            
            # Check valuation_bucket
            if match and 'valuation_bucket' in when and val_bucket not in when['valuation_bucket']:
                match = False
                
            # Check quality_grade
            if match and 'quality_grade' in when and qual_grade not in when['quality_grade']:
                match = False
                
            # Check dd_ratio_band
            if match and 'dd_ratio_band' in when and bands['dd_ratio']['key'] not in when['dd_ratio_band']:
                match = False
                
            # Check speed_band
            if match and 'speed_band' in when and bands['speed']['key'] not in when['speed_band']:
                match = False
                
            if match:
                return p
        
        return None

    def _assemble_sections(self, bands: Dict[str, Any], pattern: Optional[Dict[str, Any]], metrics: Dict[str, Any]) -> Dict[str, Any]:
        """Formats the final text segments."""
        result = {}
        
        # Prepare formatting dict
        fmt = {
            'position_pct': metrics.get('position_10y_pctile', 50.0),
            'upper_pct': 100.0 - metrics.get('position_10y_pctile', 50.0),
            'max_dd_10y_abs': abs(metrics.get('max_drawdown_10y_pct', 0.0)),
            'dd_ratio_pct': metrics.get('dd_1y_vs_10y_ratio', 0.0) * 100.0,
            'pe_history_years': metrics.get('pe_history_years', 0.0)
        }
        
        layout = self.rules.get('output_layout', {}).get('sections', [])
        
        for section in layout:
            key = section['key']
            sec_res = {
                "title_zh": section['title_zh'],
                "title_en": section['title_en'],
                "content_zh": "",
                "content_en": ""
            }
            
            includes = section.get('include', [])
            zh_parts = []
            en_parts = []
            
            if 'position_band_narrative' in includes:
                zh_parts.append(bands['position']['narrative_zh'].format(**fmt))
                en_parts.append(bands['position']['narrative_en'].format(**fmt))
            
            if 'max_dd_10y_narrative' in includes:
                zh_parts.append(bands['max_dd_10y']['narrative_zh'].format(**fmt))
                en_parts.append(bands['max_dd_10y']['narrative_en'].format(**fmt))
                
            if 'dd_ratio_band_narrative' in includes:
                zh_parts.append(bands['dd_ratio']['narrative_zh'].format(**fmt))
                en_parts.append(bands['dd_ratio']['narrative_en'].format(**fmt))
                
            if 'speed_band_narrative' in includes:
                zh_parts.append(bands['speed']['narrative_zh'].format(**fmt))
                en_parts.append(bands['speed']['narrative_en'].format(**fmt))
                
            if 'composite_long_term_pattern' in includes or 'composite_short_window_pattern' in includes:
                if pattern:
                    # Determine if the pattern fits this section
                    # Bubble/Valley are long-term, Crash/Correction are short-window
                    is_long = pattern['key'] in ["LONG_TERM_BUBBLE", "LONG_TERM_VALLEY"]
                    if ('composite_long_term_pattern' in includes and is_long) or \
                       ('composite_short_window_pattern' in includes and not is_long):
                        zh_parts.append(pattern['narrative_zh'].strip())
                        en_parts.append(pattern['narrative_en'].strip())
            
            if 'pe_history_disclaimer' in includes:
                disc = self.rules['disclaimers']['pe_history']
                if fmt['pe_history_years'] < disc['min_years_for_full_cycle']:
                    zh_parts.append(disc['narrative_zh'].format(**fmt).strip())
                    en_parts.append(disc['narrative_en'].format(**fmt).strip())
            
            sec_res['content_zh'] = " ".join(zh_parts).replace("\n", " ").strip()
            sec_res['content_en'] = " ".join(en_parts).replace("\n", " ").strip()
            
            result[key] = sec_res
            
        return result
