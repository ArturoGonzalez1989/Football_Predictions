#!/usr/bin/env python3
"""
signal_outcome_report.py
========================
Lee signals_audit.log y genera un informe de calidad de señales por estrategia:
- N apuestas, WR, P/L total, P/L medio, odds medio de entrada
- Detecta señales que expiraron sin ser colocadas (SIGNAL_EXPIRED)
- Desglose por outcome: won / lost / cashout

Uso:
    python auxiliar/signal_outcome_report.py
    python auxiliar/signal_outcome_report.py --log betfair_scraper/signals_audit.log
    python auxiliar/signal_outcome_report.py --since 2026-03-15  (solo desde esa fecha)
"""

import re
import sys
import argparse
from pathlib import Path
from collections import defaultdict
from datetime import datetime

# ── Ruta por defecto ─────────────────────────────────────────────────────────
DEFAULT_LOG = Path(__file__).resolve().parent.parent / "betfair_scraper" / "signals_audit.log"


# ── Parsers de línea ──────────────────────────────────────────────────────────

def _field(line: str, key: str) -> str:
    """Extrae el valor de un campo 'key=value' de una línea de log."""
    m = re.search(rf'\b{re.escape(key)}=([^\s|]+)', line)
    return m.group(1) if m else ""


def _ts(line: str) -> str:
    m = re.match(r'^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', line)
    return m.group(1) if m else ""


def _event(line: str) -> str:
    m = re.search(r'\|\s+(\w+)\s+\|', line)
    return m.group(1) if m else ""


def parse_log(log_path: Path, since: str = None) -> dict:
    """
    Parsea el log y devuelve:
    {
        'bets':     {bet_id: {...datos BET_PLACED...}},
        'outcomes': {bet_id: {result, pl, type}},  # type = settlement | cashout
        'expired':  [{...datos SIGNAL_EXPIRED...}],
    }
    """
    since_dt = datetime.strptime(since, "%Y-%m-%d") if since else None

    bets = {}
    outcomes = {}
    expired = []

    with open(log_path, encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.rstrip()
            if not line or line.startswith("═") or line.startswith("─"):
                continue

            ts = _ts(line)
            if since_dt and ts:
                try:
                    if datetime.strptime(ts[:10], "%Y-%m-%d") < since_dt:
                        continue
                except ValueError:
                    pass

            ev = _event(line)

            if ev == "BET_PLACED":
                bid = _field(line, "bet_id")
                if bid:
                    bets[bid] = {
                        "ts":       ts,
                        "match":    _field(line, "match"),
                        "strategy": _field(line, "strategy"),
                        "minute":   _field(line, "min"),
                        "score":    _field(line, "score"),
                        "odds":     _field(line, "odds"),
                        "rec":      _field(line, "rec"),
                        "stake":    _field(line, "stake"),
                    }

            elif ev == "SETTLEMENT":
                bid = _field(line, "bet_id")
                if bid:
                    outcomes[bid] = {
                        "type":         "settlement",
                        "result":       _field(line, "result"),
                        "pl":           _field(line, "pl"),
                        "score_final":  _field(line, "score_final"),
                        "min_final":    _field(line, "min_final"),
                    }

            elif ev == "CASHOUT":
                bid = _field(line, "bet_id")
                if bid:
                    outcomes[bid] = {
                        "type":   "cashout",
                        "result": "cashout",
                        "pl":     _field(line, "pl"),
                    }

            elif ev == "SIGNAL_EXPIRED":
                expired.append({
                    "ts":       ts,
                    "match":    _field(line, "match"),
                    "strategy": _field(line, "strategy"),
                    "minute":   _field(line, "min"),
                    "score":    _field(line, "score"),
                    "odds":     _field(line, "odds"),
                })

    return {"bets": bets, "outcomes": outcomes, "expired": expired}


def build_report(data: dict) -> dict:
    """
    Agrupa resultados por estrategia y calcula métricas.
    """
    bets = data["bets"]
    outcomes = data["outcomes"]

    by_strategy = defaultdict(lambda: {
        "n": 0, "won": 0, "lost": 0, "cashout": 0,
        "pl_total": 0.0, "odds_sum": 0.0,
        "no_outcome": 0,  # apuestas colocadas sin settlement todavía
        "rows": [],
    })

    for bid, bet in bets.items():
        strat = bet["strategy"]
        out = outcomes.get(bid)

        s = by_strategy[strat]
        s["n"] += 1

        try:
            s["odds_sum"] += float(bet["odds"])
        except (ValueError, TypeError):
            pass

        if out is None:
            s["no_outcome"] += 1
            s["rows"].append({**bet, "result": "pending", "pl": 0.0, "bet_id": bid})
            continue

        pl_str = out["pl"].replace("+", "") if out["pl"] else "0"
        try:
            pl = float(pl_str)
        except ValueError:
            pl = 0.0

        s["pl_total"] += pl
        result = out["result"]

        if result == "won":
            s["won"] += 1
        elif result == "lost":
            s["lost"] += 1
        elif result == "cashout":
            s["cashout"] += 1

        s["rows"].append({**bet, **out, "bet_id": bid, "pl": pl})

    return dict(by_strategy)


def print_report(report: dict, expired: list, verbose: bool = False):
    # ── Cabecera ──────────────────────────────────────────────────────────────
    settled_total = sum(
        s["won"] + s["lost"] + s["cashout"]
        for s in report.values()
    )
    pl_total = sum(s["pl_total"] for s in report.values())
    pending_total = sum(s["no_outcome"] for s in report.values())

    print(f"\n{'='*90}")
    print(f"  SIGNAL OUTCOME REPORT  --  {settled_total} apuestas liquidadas | {pending_total} pendientes | {len(expired)} expiradas")
    print(f"  P/L total (1 stake): {pl_total:+.2f}")
    print(f"{'='*90}\n")

    # ── Por estrategia ────────────────────────────────────────────────────────
    sorted_strats = sorted(
        report.items(),
        key=lambda x: x[1]["pl_total"],
        reverse=True,
    )

    for strat, s in sorted_strats:
        settled = s["won"] + s["lost"] + s["cashout"]
        if settled == 0:
            wr_str = "n/a"
        else:
            wr = s["won"] / settled * 100
            wr_str = f"{wr:.0f}%"

        avg_odds = s["odds_sum"] / s["n"] if s["n"] > 0 else 0
        pending_str = f"  [{s['no_outcome']} pending]" if s["no_outcome"] else ""

        pl_color = "+" if s["pl_total"] >= 0 else ""
        print(
            f"  {strat:<35}  N={s['n']:>3}  "
            f"W={s['won']:>2} L={s['lost']:>2} CO={s['cashout']:>2}  "
            f"WR={wr_str:>5}  "
            f"P/L={pl_color}{s['pl_total']:.2f}  "
            f"avgOdds={avg_odds:.2f}"
            f"{pending_str}"
        )

        if verbose:
            for row in s["rows"]:
                result = row.get("result", "?")
                pl_v = row.get("pl", 0.0)
                pl_str = f"{pl_v:+.2f}" if isinstance(pl_v, float) else str(pl_v)
                score_f = row.get("score_final", "")
                score_info = f" → {score_f}" if score_f else ""
                print(
                    f"      bet#{row['bet_id']:>4}  min={row['minute']:>3}  "
                    f"score={row['score']}{score_info}  "
                    f"odds={row['odds']}  {result.upper()}  {pl_str}"
                )

    # ── Señales expiradas ─────────────────────────────────────────────────────
    if expired:
        print(f"\n{'-'*90}")
        print(f"  SENALES EXPIRADAS (dispararon pero desaparecieron antes de madurar): {len(expired)}")
        expired_by_strat = defaultdict(int)
        for e in expired:
            expired_by_strat[e["strategy"]] += 1
        for strat, cnt in sorted(expired_by_strat.items(), key=lambda x: -x[1]):
            print(f"    {strat:<35}  {cnt:>3} expiradas")

    print(f"\n{'='*90}\n")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Signal outcome report desde signals_audit.log")
    parser.add_argument("--log", default=str(DEFAULT_LOG), help="Ruta al signals_audit.log")
    parser.add_argument("--since", default=None, help="Filtrar desde fecha YYYY-MM-DD")
    parser.add_argument("--verbose", "-v", action="store_true", help="Mostrar detalle por apuesta")
    args = parser.parse_args()

    log_path = Path(args.log)
    if not log_path.exists():
        print(f"ERROR: No se encuentra {log_path}", file=sys.stderr)
        sys.exit(1)

    data = parse_log(log_path, since=args.since)
    report = build_report(data)
    print_report(report, data["expired"], verbose=args.verbose)


if __name__ == "__main__":
    main()
