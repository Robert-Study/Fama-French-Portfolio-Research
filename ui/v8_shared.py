"""Portfolio Construction Lab V8.0 — Shared UI contracts, copy loader, and validators."""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import re
from typing import Any
import numpy as np

TOTAL = 10000

# Canonical root path resolution
REPO_ROOT = Path(__file__).resolve().parent.parent
DRIVE_V8_ROOT = Path(r"G:\My Drive\AI-File-Exchange\03 Investment Portfolio\V8.0 - Portfolio Construction Lab")

if (DRIVE_V8_ROOT / "00 Specifications").is_dir():
    SPEC = DRIVE_V8_ROOT / "00 Specifications"
    RES = DRIVE_V8_ROOT / "01 Resources"
else:
    SPEC = REPO_ROOT / "tests" / "fixtures"
    RES = REPO_ROOT / "tests" / "fixtures"

DATA_DIR = REPO_ROOT / "data"
RELEASE_DIR = DATA_DIR / "release"

REFERENCE_KEYS = ("sp500", "all_cap", "global_6040", "bonds", "value", "size")

_COPY_CACHE: dict[str, str] | None = None


def _load_copy_table() -> dict[str, str]:
    global _COPY_CACHE
    if _COPY_CACHE is not None:
        return _COPY_CACHE

    table: dict[str, str] = {}
    copy_path = SPEC / "07_interface_copy.md"
    if not copy_path.is_file():
        copy_path = DRIVE_V8_ROOT / "07 UI & Implementation" / "07_interface_copy.md"

    if copy_path.is_file():
        text = copy_path.read_text(encoding="utf-8")
        # Extract YAML code blocks
        blocks = re.findall(r"```yaml\s*\n(.*?)\n```", text, re.DOTALL)
        for block in blocks:
            for line in block.splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                match = re.match(r'^([a-zA-Z0-9_\.]+)\s*:\s*"(.*)"\s*$', line)
                if match:
                    table[match.group(1)] = match.group(2).replace(r"\"", '"')
                else:
                    match_single = re.match(r"^([a-zA-Z0-9_\.]+)\s*:\s*'(.*)'\s*$", line)
                    if match_single:
                        table[match_single.group(1)] = match_single.group(2)
                    else:
                        match_plain = re.match(r"^([a-zA-Z0-9_\.]+)\s*:\s*(.*)$", line)
                        if match_plain:
                            table[match_plain.group(1)] = match_plain.group(2).strip()

    _COPY_CACHE = table
    return _COPY_CACHE


def copy(key: str, **kwargs: Any) -> str:
    """Retrieve UI microcopy by key with optional named string interpolation."""
    table = _load_copy_table()
    val = table.get(key)
    if val is None:
        # Fallback to humanized key suffix
        val = key.split(".")[-1].replace("_", " ").capitalize()
    if kwargs:
        try:
            return val.format(**kwargs)
        except Exception:
            return val
    return val


def source_hash(path: Path | str) -> str:
    """Return SHA-256 hex digest of file contents."""
    p = Path(path)
    if not p.is_file():
        return ""
    return sha256(p.read_bytes()).hexdigest()


def checked_weights(q_bps: Any) -> np.ndarray:
    """Validate portfolio integer basis points allocation summing to 10,000."""
    arr = np.asarray(q_bps, dtype=np.int64)
    if arr.ndim != 1:
        raise ValueError("Allocation must be a 1D vector of basis points")
    if np.any(arr < 0):
        raise ValueError("Allocations cannot be negative")
    # Semi-continuous positioning gate: non-zero weights must be >= 10 bps
    non_zero = arr[arr > 0]
    if np.any(non_zero < 10):
        raise ValueError("Non-zero portfolio weights must satisfy 10 bps position gate")
    if int(arr.sum()) != TOTAL:
        raise ValueError(f"Portfolio allocations must sum to {TOTAL} basis points (got {int(arr.sum())})")
    return arr


def as_weights(q_bps: Any) -> np.ndarray:
    """Convert integer basis points to decimal weights summing to 1.0."""
    return checked_weights(q_bps).astype(np.float64) / float(TOTAL)


@dataclass(frozen=True)
class Portfolio:
    """Immutable representation of an allocated portfolio for comparison and analysis."""
    name: str
    q_bps: tuple[int, ...]
    method: str
    release_id: str

    def vector(self) -> np.ndarray:
        return np.asarray(self.q_bps, dtype=np.int64)


def diagnostics(model: Any, q_bps: np.ndarray, leverage: np.ndarray | None = None) -> dict[str, float]:
    """Calculate portfolio arithmetic expected return, volatility, and gross leverage."""
    w = np.asarray(q_bps, dtype=np.float64) / float(TOTAL)
    mu = float(w @ getattr(model, "mu_arith_ann", np.zeros_like(w)))
    cov = getattr(model, "cov_ann", np.zeros((len(w), len(w))))
    var = float(w @ cov @ w)
    sigma = float(np.sqrt(max(var, 0.0)))
    if leverage is not None:
        lev_arr = np.asarray(leverage, dtype=np.float64)
        gross = float(np.sum(np.abs(w) * lev_arr))
    else:
        gross = float(np.sum(np.abs(w)))
    return {"mu": mu, "sigma": sigma, "gross": gross}


def release_manifest() -> dict[str, Any]:
    """Load release manifest or return default development manifest."""
    manifest_file = RELEASE_DIR / "manifest.json"
    if manifest_file.is_file():
        import json
        with open(manifest_file, "r", encoding="utf-8") as f:
            return json.load(f)
    
    # Default manifest structure for development / testing
    return {
        "release_id": "V8.0-2026-10-18",
        "snapshot_date": "2026-10-18",
        "sha256": {},
        "references": {
            "sp500": {"available": True, "q_bps": [10000] + [0] * 67},
            "all_cap": {"available": True, "q_bps": [10000] + [0] * 67},
            "global_6040": {"available": True, "q_bps": [6000, 4000] + [0] * 66},
            "bonds": {"available": True, "q_bps": [0] * 68},
            "value": {"available": True, "q_bps": [0] * 68},
            "size": {"available": True, "q_bps": [0] * 68},
        }
    }


def require_release_path(relative: str) -> Path:
    """Resolve a required release file path from release directory or data root."""
    target = RELEASE_DIR / relative
    if target.is_file():
        return target
    target_data = DATA_DIR / relative
    if target_data.is_file():
        return target_data
    # Return release path even if not yet built so callers get clean FileNotFoundError
    return target


def _meta_get(meta: Any, key: str, default: Any = None) -> Any:
    """Retrieve metadata attribute supporting dict, SimpleNamespace, and dataclasses."""
    if isinstance(meta, dict):
        return meta.get(key, default)
    return getattr(meta, key, default)


def _get_reference_weights(ref_val: Any) -> list[int] | None:
    """Extract integer basis point weights from dict, list, or ndarray reference."""
    if ref_val is None:
        return None
    if isinstance(ref_val, dict):
        if not ref_val.get("available", True):
            return None
        q = ref_val.get("q_bps")
        if q is not None:
            return [int(x) for x in q]
        return None
    if isinstance(ref_val, (list, tuple, np.ndarray)):
        return [int(x) for x in ref_val]
    return None

