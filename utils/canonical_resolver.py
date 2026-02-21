from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, List, Tuple


class CanonicalResolutionError(ValueError):
    """Base error for canonical resolution."""


class AmbiguousSymbolError(CanonicalResolutionError):
    """Raised when a raw symbol maps to multiple canonical IDs."""


class UnknownSymbolError(CanonicalResolutionError):
    """Raised when symbol cannot be resolved (strict mode)."""


@dataclass(frozen=True)
class CanonicalResult:
    raw_symbol: str
    canonical_id: str
    strategy: str  # "MAP" | "ASSET" | "RAW"
    note: str = ""


def _norm(s: str) -> str:
    return (s or "").strip().upper()


def _is_cn_suffixed(symbol: str) -> bool:
    s = _norm(symbol)
    return s.endswith((".SS", ".SH", ".SZ"))


def _strip_cn_suffix(symbol: str) -> str:
    s = _norm(symbol)
    if "." in s:
        return s.split(".")[0]
    return s


def resolve_canonical_symbol(
    conn,
    raw_symbol: str,
    *,
    asset_type_hint: Optional[str] = None,   # "INDEX" | "STOCK" | "ETF"
    market_hint: Optional[str] = None,       # "HK" | "CN" | "US"
    strict_ambiguous: bool = True,
    strict_unknown: bool = False,
    cn_namespace: bool = True,
) -> str:
    """
    Resolve raw symbol to canonical_id.
    """

    raw = _norm(raw_symbol)
    if not raw:
        raise CanonicalResolutionError("Empty symbol")

    # --- ❗ Idempotency Check ---
    # If it's already a standard canonical ID (MARKET:TYPE:CODE), return it directly
    # This prevents HK:INDEX:HK:INDEX:... redundancies.
    parts = raw.split(":")
    if len(parts) == 3 and parts[0] in {"HK", "CN", "US", "WORLD"} and parts[1] in {"STOCK", "ETF", "INDEX", "CRYPTO", "TRUST"}:
        return raw

    hint = _norm(asset_type_hint) if asset_type_hint else None
    m_hint = _norm(market_hint) if market_hint else None
    cur = conn.cursor()

    # 0) Direct construction if hints are robust
    if m_hint in {"HK", "CN", "US"} and hint in {"STOCK", "ETF", "INDEX", "CRYPTO", "TRUST"}:
        code = raw
        if m_hint == "HK":
            base_code = raw.replace(".HK", "")
            # 只对纯数字代码补零
            code = base_code.zfill(5) if base_code.isdigit() else base_code
        elif m_hint == "CN":
            code = _strip_cn_suffix(raw)
        elif m_hint == "US":
             code = raw.replace(".US", "")
        return f"{m_hint}:{hint}:{code}"

    # 1) Mapping table (Precise override) - PRIORITY
    rows = cur.execute(
        """
        SELECT DISTINCT canonical_id, priority
        FROM asset_symbol_map
        WHERE symbol = ? AND is_active = 1
        ORDER BY priority ASC
        """,
        (raw,),
    ).fetchall()
    
    if not rows and "." in raw:
        # Try without suffix
        base = raw.split(".")[0]
        rows = cur.execute(
            """
            SELECT DISTINCT canonical_id, priority
            FROM asset_symbol_map
            WHERE symbol = ? AND is_active = 1
            ORDER BY priority ASC
            """,
            (base,),
        ).fetchall()

    if rows:
        cands = [r[0] for r in rows]
        if len(cands) == 1:
            return cands[0]
        
        if hint:
            for cid in cands:
                if f":{hint}:" in cid:
                    return cid
        
        return cands[0] # Highest priority

    # 2) Heuristic resolution (Autonomous)
    # HK Logic
    if raw.endswith(".HK"):
        code = raw.replace(".HK", "")
        # 只对纯数字代码补零
        if code.isdigit():
            code = code.zfill(5)
        return f"HK:STOCK:{code}"
    
    # CN Logic
    if _is_cn_suffixed(raw):
        base = _strip_cn_suffix(raw)
        if base.isdigit() and len(base) == 6:
            # Simple heuristic: stock by default unless hint says otherwise
            asset_type = hint if hint else "STOCK"
            return f"CN:{asset_type}:{base}"
    
    # US Logic
    if raw.isalpha() and len(raw) <= 5: # Likely US Stock like TSLA, AAPL
        return f"US:STOCK:{raw}"
    
    # Numerical fallbacks
    if raw.isdigit():
        if len(raw) == 6:
            # Check pattern for ETF (SSE 51xxxx, 58xxxx; SZSE 15xxxx)
            if raw.startswith(("51", "15", "58")):
                return f"CN:ETF:{raw}"
            return f"CN:STOCK:{raw}"
        elif len(raw) <= 5:
            return f"HK:STOCK:{raw.zfill(5)}"

    # 3) Asset ID check
    in_assets = cur.execute(
        "SELECT 1 FROM assets WHERE asset_id = ? LIMIT 1",
        (raw,),
    ).fetchone()
    if in_assets:
        return raw

    # 4) Fallback: Try removing caret (^)
    if raw.startswith("^"):
        stripped = raw.lstrip("^")
        if stripped:
            try:
                # Recursively try to resolve the stripped version
                # pass strict_unknown=False to allow checking without raising immediately
                return resolve_canonical_symbol(
                    conn, stripped,
                    asset_type_hint=asset_type_hint,
                    market_hint=market_hint,
                    strict_ambiguous=strict_ambiguous,
                    strict_unknown=True, # If stripped version is also unknown, we want to know
                    cn_namespace=cn_namespace
                )
            except (UnknownSymbolError, CanonicalResolutionError):
                pass # Fallback to original flow if stripped also fails

    # 5) Unknown
    if strict_unknown:
        raise UnknownSymbolError(f"Unknown symbol '{raw}'.")

    return raw

def resolve_symbol_for_provider(canonical_id: str, provider: str = "yahoo") -> str:
    """
    Resolve canonical ID to provider-specific symbol (e.g. Yahoo Ticker).
    """
    if not canonical_id:
        return ""
        
    cid = canonical_id.upper()
    
    # 1. CN Standard Handling
    if cid.startswith(("CN:STOCK:", "CN:ETF:")):
        code = cid.split(":")[-1]
        if code.startswith(("6", "51", "58")):
            return f"{code}.SS"
        else:
            return f"{code}.SZ"
            
    if cid.startswith("CN:INDEX:"):
        code = cid.split(":")[-1]
        return f"{code}.SS"
        
    # 2. HK Standard Handling
    if cid.startswith(("HK:STOCK:", "HK:ETF:")):
        code = cid.split(":")[-1]
        return f"{code.zfill(5)}.HK"
    
    # 3. WORLD Market Handling (e.g., WORLD:CRYPTO:BTC-USD)
    if cid.startswith("WORLD:CRYPTO:"):
        code = cid.split(":")[-1]
        return code  # Return the ticker directly (e.g., BTC-USD)
        
    # 4. Existing Dot Suffixes (legacy support)
    if "." in cid:
        return cid
        
    # 5. US Stocks / Indices
    if cid in {"SPX", "NDX", "DJI", "HSI", "HSTECH"}:
        y_map = {"SPX": "^GSPC", "NDX": "^NDX", "DJI": "^DJI", "HSI": "^HSI", "HSTECH": "^HSTECH"}
        return y_map.get(cid, cid)

    # 6. US TRUST Logic
    if cid.startswith("US:TRUST:"):
        # US Trust Fund (e.g. 0P00014FO3) -> 0P00014FO3
        # No suffix needed for Morningstar IDs on Yahoo usually
        return cid.split(":")[-1]

    return cid
