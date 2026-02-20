"""
Cartera configuration API — single source of truth for all strategy settings.
Persists to betfair_scraper/cartera_config.json and is read by:
  - Signal detection (detect_betting_signals)
  - Cartera backtesting (analyze_cartera)
  - Backtesting simulator (backtest_signals) — future
  - Frontend StrategiesView + BettingSignalsView
"""

import json
from pathlib import Path
from typing import Any, Dict

from fastapi import APIRouter, HTTPException

router = APIRouter()

# Config file lives alongside placed_bets.csv / games.csv
_CONFIG_PATH = Path(__file__).resolve().parent.parent.parent.parent / "cartera_config.json"

DEFAULT_CONFIG: Dict[str, Any] = {
    "versions": {
        "draw": "v2r",
        "xg": "base",
        "drift": "v1",
        "clustering": "v2",
        "pressure": "v1",
        "tarde_asia": "off",
        "momentum_xg": "off",
    },
    "bankroll_mode": "fixed",
    "active_preset": None,
    "risk_filter": "all",
    "min_duration": {
        "draw": 1,
        "xg": 2,
        "drift": 2,
        "clustering": 4,
        "pressure": 2,
    },
    "adjustments": {
        "enabled": False,
        "dedup": True,
        "max_odds": 6.0,
        "min_odds": 1.15,
        "drift_min_minute": 15,
        "slippage_pct": 2,
        "conflict_filter": True,
        "cashout_minute": None,
        "cashout_pct": 20,
    },
}


def load_config() -> Dict[str, Any]:
    """Load config from disk. Falls back to DEFAULT_CONFIG if file missing or corrupt."""
    if _CONFIG_PATH.exists():
        try:
            data = json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
            # Merge with defaults to fill any missing keys from older config files
            merged = _deep_merge(DEFAULT_CONFIG, data)
            return merged
        except Exception:
            pass
    return dict(DEFAULT_CONFIG)


def _deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge override into base (override wins on conflicts)."""
    result = dict(base)
    for k, v in override.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = _deep_merge(result[k], v)
        else:
            result[k] = v
    return result


@router.get("/config/cartera")
async def get_cartera_config() -> Dict[str, Any]:
    """Return the current cartera configuration (used by signals, cartera, backtester)."""
    return load_config()


@router.put("/config/cartera")
async def save_cartera_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """Persist the cartera configuration to disk."""
    try:
        _CONFIG_PATH.write_text(
            json.dumps(config, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        # Clear analytics cache so next cartera request uses new min_duration values
        try:
            from utils import csv_reader as _csv_reader
            _csv_reader.clear_analytics_cache()
        except Exception:
            pass
        return {"status": "ok", "path": str(_CONFIG_PATH)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not save config: {e}")
