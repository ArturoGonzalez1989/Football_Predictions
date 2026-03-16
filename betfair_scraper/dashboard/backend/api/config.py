"""
Cartera configuration API — single source of truth for all strategy settings.
Persists to betfair_scraper/cartera_config.json and is read by:
  - Signal detection (detect_betting_signals)
  - Cartera backtesting (analyze_cartera)
  - Backtesting simulator (backtest_signals) — future
  - Frontend StrategiesView + BettingSignalsView
"""

import asyncio
import csv
import json
import math
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException, Query

_executor = ThreadPoolExecutor(max_workers=1)

router = APIRouter()

# Config file lives alongside placed_bets.csv / games.csv
_CONFIG_PATH = Path(__file__).resolve().parent.parent.parent.parent / "cartera_config.json"
_ANALISIS_DIR = Path(__file__).resolve().parent.parent.parent.parent.parent / "analisis"

DEFAULT_CONFIG: Dict[str, Any] = {
    "bankroll_mode": "fixed",
    "active_preset": None,
    "risk_filter": "all",
    "min_duration": {
        "back_draw_00": 1,
        "xg_underperformance": 2,
        "odds_drift": 2,
        "goal_clustering": 4,
        "pressure_cooker": 2,
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


def _validate_config(config: Dict[str, Any]) -> None:
    """Raise ValueError if config contains values that would silently break the system."""
    if "strategies" in config and not isinstance(config["strategies"], dict):
        raise ValueError("'strategies' must be an object")
    if "bankroll_mode" in config and config["bankroll_mode"] not in ("fixed", "fractional", "pct"):
        raise ValueError(f"'bankroll_mode' must be 'fixed', 'fractional' or 'pct', got {config['bankroll_mode']!r}")
    flat_stake = config.get("flat_stake")
    if flat_stake is not None and (not isinstance(flat_stake, (int, float)) or flat_stake <= 0):
        raise ValueError(f"'flat_stake' must be a positive number, got {flat_stake!r}")
    min_dur = config.get("min_duration", {})
    if not isinstance(min_dur, dict):
        raise ValueError("'min_duration' must be an object")
    for k, v in min_dur.items():
        if not isinstance(v, (int, float)) or v < 0:
            raise ValueError(f"'min_duration.{k}' must be a non-negative number, got {v!r}")


_CHART_MAX_POINTS = 300  # downsample cumul to this many bars for the chart


_WEEKDAY_NAMES = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]
_ODDS_BUCKETS = ["1.0-1.5", "1.5-2.0", "2.0-3.0", "3.0-5.0", "5.0+"]


def _odds_bucket(odds: float) -> str:
    if odds < 1.5:
        return "1.0-1.5"
    if odds < 2.0:
        return "1.5-2.0"
    if odds < 3.0:
        return "2.0-3.0"
    if odds < 5.0:
        return "3.0-5.0"
    return "5.0+"


def _load_bt_csv(path: Path) -> Dict[str, Any]:
    """CPU-bound CSV parsing — runs in thread pool so it doesn't block the event loop."""
    with open(path, newline="", encoding="utf-8") as f:
        rows: List[Dict[str, str]] = list(csv.DictReader(f))

    cumul_pl = 0.0
    cumul_full: List[Dict[str, Any]] = []
    pls: List[float] = []
    match_ids: set = set()

    by_strat: Dict[str, Dict[str, Any]] = {}
    by_country: Dict[str, Dict[str, Any]] = {}
    by_league: Dict[str, Dict[str, Any]] = {}
    by_minute: Dict[int, Dict[str, Any]] = {}
    by_odds: Dict[str, Dict[str, Any]] = {}
    by_weekday: Dict[int, Dict[str, Any]] = {}
    by_hour: Dict[int, Dict[str, Any]] = {}
    by_month: Dict[str, Dict[str, Any]] = {}
    by_date: Dict[str, Dict[str, Any]] = {}
    strat_running: Dict[str, float] = {}
    strat_cumul_series: Dict[str, List[float]] = {}
    strat_league: Dict[str, Dict[str, Any]] = {}

    for r in rows:
        won = r.get("won", "").strip().lower() in ("true", "1", "yes")
        pl = float(r.get("pl", 0) or 0)
        strategy = r.get("strategy", "")
        label = r.get("strategy_label", strategy)
        country = r.get("País", "") or "Desconocido"
        league = r.get("Liga", "") or "Desconocida"

        cumul_pl += pl
        pls.append(pl)
        cumul_full.append({"won": won, "pl": pl, "cumul_pl": round(cumul_pl, 4), "strategy": label})
        if r.get("match_id"):
            match_ids.add(r["match_id"])

        # Strategy
        if strategy not in by_strat:
            by_strat[strategy] = {"label": label, "bets": 0, "wins": 0, "pl": 0.0}
        by_strat[strategy]["bets"] += 1
        by_strat[strategy]["pl"] += pl
        if won:
            by_strat[strategy]["wins"] += 1
        strat_running[strategy] = strat_running.get(strategy, 0.0) + pl
        if strategy not in strat_cumul_series:
            strat_cumul_series[strategy] = []
        strat_cumul_series[strategy].append(strat_running[strategy])

        # Country
        if country not in by_country:
            by_country[country] = {"bets": 0, "wins": 0, "pl": 0.0}
        by_country[country]["bets"] += 1
        by_country[country]["pl"] += pl
        if won:
            by_country[country]["wins"] += 1

        # League
        if league not in by_league:
            by_league[league] = {"bets": 0, "wins": 0, "pl": 0.0}
        by_league[league]["bets"] += 1
        by_league[league]["pl"] += pl
        if won:
            by_league[league]["wins"] += 1
        sl_key = f"{strategy}|{league}"
        if sl_key not in strat_league:
            strat_league[sl_key] = {"strategy": strategy, "league": league, "pl": 0.0, "bets": 0}
        strat_league[sl_key]["pl"] += pl
        strat_league[sl_key]["bets"] += 1

        # Minute bucket (5-min intervals)
        try:
            minuto = int(float(r.get("minuto", 0) or 0))
            bucket = (minuto // 5) * 5
            if bucket not in by_minute:
                by_minute[bucket] = {"bets": 0, "wins": 0, "pl": 0.0}
            by_minute[bucket]["bets"] += 1
            by_minute[bucket]["pl"] += pl
            if won:
                by_minute[bucket]["wins"] += 1
        except (ValueError, TypeError):
            pass

        # Odds bucket
        try:
            odds = float(r.get("back_odds", 0) or 0)
            if odds > 0:
                obkt = _odds_bucket(odds)
                if obkt not in by_odds:
                    by_odds[obkt] = {"bets": 0, "wins": 0, "pl": 0.0}
                by_odds[obkt]["bets"] += 1
                by_odds[obkt]["pl"] += pl
                by_odds[obkt]["odds_sum"] = by_odds[obkt].get("odds_sum", 0.0) + odds
                if won:
                    by_odds[obkt]["wins"] += 1
        except (ValueError, TypeError):
            pass

        # Timestamp-based: weekday, hour, month
        ts_str = (r.get("timestamp_utc") or "").strip()
        if ts_str:
            try:
                ts = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
                wd = ts.weekday()
                if wd not in by_weekday:
                    by_weekday[wd] = {"bets": 0, "wins": 0, "pl": 0.0}
                by_weekday[wd]["bets"] += 1
                by_weekday[wd]["pl"] += pl
                if won:
                    by_weekday[wd]["wins"] += 1

                hr = ts.hour
                if hr not in by_hour:
                    by_hour[hr] = {"bets": 0, "pl": 0.0}
                by_hour[hr]["bets"] += 1
                by_hour[hr]["pl"] += pl

                mo = ts.strftime("%Y-%m")
                if mo not in by_month:
                    by_month[mo] = {"bets": 0, "pl": 0.0}
                by_month[mo]["bets"] += 1
                by_month[mo]["pl"] += pl

                dt = ts.strftime("%Y-%m-%d")
                if dt not in by_date:
                    by_date[dt] = {"bets": 0, "wins": 0, "pl": 0.0}
                by_date[dt]["bets"] += 1
                by_date[dt]["pl"] += pl
                if won:
                    by_date[dt]["wins"] += 1
            except (ValueError, TypeError):
                pass

    # Downsample cumul for the chart (keep first, last, every N-th point)
    n = len(cumul_full)
    if n <= _CHART_MAX_POINTS:
        cumul = cumul_full
    else:
        step = n / _CHART_MAX_POINTS
        indices = set([0, n - 1]) | {int(i * step) for i in range(_CHART_MAX_POINTS)}
        cumul = [cumul_full[i] for i in sorted(indices)]

    # KPIs
    total = n
    wins = sum(1 for r in cumul_full if r["won"])
    win_rate = wins / total * 100 if total else 0
    total_pl_val = cumul_full[-1]["cumul_pl"] if cumul_full else 0
    roi = total_pl_val / total * 100 if total else 0

    peak = 0.0
    max_dd = 0.0
    for r in cumul_full:
        if r["cumul_pl"] > peak:
            peak = r["cumul_pl"]
        dd = peak - r["cumul_pl"]
        if dd > max_dd:
            max_dd = dd

    best_streak = worst_streak = cur_win = cur_loss = 0
    for r in cumul_full:
        if r["won"]:
            cur_win += 1; cur_loss = 0
            if cur_win > best_streak: best_streak = cur_win
        else:
            cur_loss += 1; cur_win = 0
            if cur_loss > worst_streak: worst_streak = cur_loss

    avg_pl = sum(pls) / len(pls) if pls else 0
    variance = sum((p - avg_pl) ** 2 for p in pls) / len(pls) if pls else 0
    sharpe = avg_pl / math.sqrt(variance) if variance > 0 else 0
    gross_wins = sum(p for p in pls if p > 0)
    gross_losses = abs(sum(p for p in pls if p < 0))
    profit_factor = gross_wins / gross_losses if gross_losses > 0 else (999 if gross_wins > 0 else 0)

    def _fmt_group(d: Dict[str, Any]) -> List[Dict[str, Any]]:
        return sorted([
            {
                "name": k,
                "bets": v["bets"],
                "wins": v.get("wins", 0),
                "win_pct": round(v.get("wins", 0) / v["bets"] * 100, 1) if v["bets"] else 0,
                "pl": round(v["pl"], 2),
                "roi": round(v["pl"] / v["bets"] * 100, 1) if v["bets"] else 0,
            }
            for k, v in d.items()
        ], key=lambda x: -x["pl"])

    by_strategy = sorted([
        {
            "strategy": s["label"],
            "bets": s["bets"],
            "wins": s["wins"],
            "win_pct": round(s["wins"] / s["bets"] * 100, 1) if s["bets"] else 0,
            "pl": round(s["pl"], 2),
            "roi": round(s["pl"] / s["bets"] * 100, 1) if s["bets"] else 0,
            "pl_per_bet": round(s["pl"] / s["bets"], 3) if s["bets"] else 0,
        }
        for s in by_strat.values()
    ], key=lambda x: -x["roi"])

    # Minute histogram: sorted by bucket value
    by_minute_list = sorted([
        {"bucket": f"{k}-{k+4}", "minute": k, "bets": v["bets"], "wins": v.get("wins", 0),
         "win_pct": round(v.get("wins", 0) / v["bets"] * 100, 1) if v["bets"] else 0,
         "pl": round(v["pl"], 2)}
        for k, v in by_minute.items()
    ], key=lambda x: x["minute"])

    # Odds histogram: in order of buckets
    by_odds_list = [
        {"bucket": b,
         "bets": by_odds.get(b, {}).get("bets", 0),
         "wins": by_odds.get(b, {}).get("wins", 0),
         "win_pct": round(by_odds.get(b, {}).get("wins", 0) / by_odds[b]["bets"] * 100, 1) if by_odds.get(b, {}).get("bets") else 0,
         "pl": round(by_odds.get(b, {}).get("pl", 0), 2)}
        for b in _ODDS_BUCKETS if b in by_odds
    ]

    # Weekday in Mon-Sun order
    by_weekday_list = [
        {"day": _WEEKDAY_NAMES[wd],
         "bets": by_weekday[wd]["bets"],
         "wins": by_weekday[wd].get("wins", 0),
         "win_pct": round(by_weekday[wd].get("wins", 0) / by_weekday[wd]["bets"] * 100, 1) if by_weekday[wd]["bets"] else 0,
         "pl": round(by_weekday[wd]["pl"], 2),
         "roi": round(by_weekday[wd]["pl"] / by_weekday[wd]["bets"] * 100, 1) if by_weekday[wd]["bets"] else 0}
        for wd in range(7) if wd in by_weekday
    ]

    # Hour list sorted 0-23
    by_hour_list = sorted([
        {"hour": hr, "bets": v["bets"], "pl": round(v["pl"], 2)}
        for hr, v in by_hour.items()
    ], key=lambda x: x["hour"])

    # Month list sorted chronologically
    by_month_list = sorted([
        {"month": mo, "bets": v["bets"], "pl": round(v["pl"], 2)}
        for mo, v in by_month.items()
    ], key=lambda x: x["month"])

    # ── Strategy cumulative P/L chart (downsampled to 100 pts per strategy) ──────
    _SC_MAX = 100
    strat_cumul_chart: Dict[str, List[float]] = {}
    for strat, series in strat_cumul_series.items():
        n_s = len(series)
        if n_s <= _SC_MAX:
            pts = series
        else:
            step = n_s / _SC_MAX
            indices = sorted({0, n_s - 1} | {int(i * step) for i in range(_SC_MAX)})
            pts = [series[i] for i in indices]
        label = by_strat[strat]["label"]
        strat_cumul_chart[label] = [round(v, 3) for v in pts]

    # ── Per-strategy max drawdown ──────────────────────────────────────────────
    strat_drawdown_list: List[Dict[str, Any]] = []
    for strat, series in strat_cumul_series.items():
        peak = dd = 0.0
        for v in series:
            if v > peak:
                peak = v
            cur_dd = peak - v
            if cur_dd > dd:
                dd = cur_dd
        strat_drawdown_list.append({
            "strategy": by_strat[strat]["label"],
            "max_dd": round(dd, 2),
            "total_pl": round(series[-1] if series else 0.0, 2),
        })
    strat_drawdown_list.sort(key=lambda x: -x["max_dd"])

    # ── Odds calibration (actual WR vs implied WR = 1/avg_odds) ───────────────
    odds_calibration_list: List[Dict[str, Any]] = []
    for b in _ODDS_BUCKETS:
        if b not in by_odds:
            continue
        od = by_odds[b]
        bts = od["bets"]
        if not bts:
            continue
        actual_wr = round(od.get("wins", 0) / bts * 100, 1)
        avg_odds = od.get("odds_sum", 0.0) / bts
        implied_wr = round(1.0 / avg_odds * 100, 1) if avg_odds > 1.0 else 0.0
        odds_calibration_list.append({
            "bucket": b,
            "bets": bts,
            "actual_wr": actual_wr,
            "implied_wr": implied_wr,
            "edge": round(actual_wr - implied_wr, 1),
        })

    # ── Strategy × league heatmap (top 10 leagues by bets) ───────────────────
    _HEATMAP_TOP = 10
    top_leagues = sorted(by_league.keys(), key=lambda lg: -by_league[lg]["bets"])[:_HEATMAP_TOP]
    strats_by_pl = sorted(by_strat.keys(), key=lambda s: -by_strat[s]["pl"])
    heatmap_rows: List[Dict[str, Any]] = []
    for strat in strats_by_pl:
        label = by_strat[strat]["label"]
        row_vals: List[Any] = []
        for lg in top_leagues:
            d = strat_league.get(f"{strat}|{lg}", {"pl": 0.0, "bets": 0})
            bts = d["bets"]
            row_vals.append({
                "pl": round(d["pl"], 2),
                "bets": bts,
                "roi": round(d["pl"] / bts * 100, 1) if bts >= 3 else None,
            })
        heatmap_rows.append({"strategy": label, "values": row_vals})

    return {
        "filename": path.name,
        "total_matches": len(match_ids),
        "kpis": {
            "total_bets": total,
            "wins": wins,
            "win_rate": round(win_rate, 1),
            "total_pl": round(total_pl_val, 2),
            "roi": round(roi, 1),
            "max_dd": round(max_dd, 2),
            "best_streak": best_streak,
            "worst_streak": worst_streak,
            "sharpe": round(sharpe, 2),
            "profit_factor": round(profit_factor, 2),
        },
        "cumul": cumul,
        "by_strategy": by_strategy,
        "by_country": _fmt_group(by_country),
        "by_league": _fmt_group(by_league),
        "by_minute": by_minute_list,
        "by_odds": by_odds_list,
        "by_weekday": by_weekday_list,
        "by_hour": by_hour_list,
        "by_month": by_month_list,
        "by_date": sorted([
            {"date": dt,
             "bets": v["bets"],
             "wins": v["wins"],
             "win_pct": round(v["wins"] / v["bets"] * 100, 1) if v["bets"] else 0,
             "pl": round(v["pl"], 2),
             "roi": round(v["pl"] / v["bets"] * 100, 1) if v["bets"] else 0}
            for dt, v in by_date.items()
        ], key=lambda x: x["date"]),
        "strat_cumul": strat_cumul_chart,
        "strat_drawdown": strat_drawdown_list,
        "odds_calibration": odds_calibration_list,
        "heatmap": {"leagues": top_leagues, "rows": heatmap_rows},
    }


@router.get("/config/bt-results")
async def get_bt_results() -> Dict[str, Any]:
    """Read the latest bt_results_*.csv — non-blocking, chart downsampled to 300 pts."""
    csv_files = sorted(_ANALISIS_DIR.glob("bt_results_*.csv"))
    if not csv_files:
        raise HTTPException(status_code=404, detail="No bt_results_*.csv found in analisis/")
    latest = csv_files[-1]
    try:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(_executor, _load_bt_csv, latest)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/config/cartera")
async def save_cartera_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """Persist the cartera configuration to disk."""
    try:
        _validate_config(config)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
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
