import csv
from collections import defaultdict

# Parse CSV
with open("cartera_min_dd_realista_2026-02-18.csv", "r", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    rows = list(reader)

# Group by day and strategy
daily_stats = defaultdict(lambda: {
    "total": 0, "won": 0, "pl": 0, "stake": 0,
    "by_strategy": defaultdict(lambda: {"total": 0, "won": 0, "pl": 0})
})

for row in rows:
    ts = row["timestamp_utc"]
    date = ts.split(" ")[0]
    won = int(row["won"])
    pl = float(row["pl"])
    strategy = row["strategy"]

    daily_stats[date]["total"] += 1
    daily_stats[date]["won"] += won
    daily_stats[date]["pl"] += pl
    daily_stats[date]["stake"] += 10

    daily_stats[date]["by_strategy"][strategy]["total"] += 1
    daily_stats[date]["by_strategy"][strategy]["won"] += won
    daily_stats[date]["by_strategy"][strategy]["pl"] += pl

# Print summary
print("=" * 80)
print("ANÁLISIS DIARIO DE RENDIMIENTO")
print("=" * 80)

for date in sorted(daily_stats.keys()):
    stats = daily_stats[date]
    wr = (stats["won"] / stats["total"] * 100) if stats["total"] > 0 else 0
    roi = (stats["pl"] / stats["stake"] * 100) if stats["stake"] > 0 else 0

    print(f"\n📅 {date}")
    print(f"   Apuestas: {stats['total']} | Ganadas: {stats['won']} | Win Rate: {wr:.1f}%")
    print(f"   P/L: {stats['pl']:+.2f} EUR | Stake: {stats['stake']:.0f} EUR | ROI: {roi:+.1f}%")

    # Show strategy breakdown for Feb 17
    if date == "2026-02-17":
        print(f"\n   📊 DESGLOSE POR ESTRATEGIA (día 17):")
        for strat, strat_stats in sorted(stats["by_strategy"].items(), key=lambda x: x[1]["pl"]):
            strat_wr = (strat_stats["won"] / strat_stats["total"] * 100) if strat_stats["total"] > 0 else 0
            print(f"      {strat:25s}: {strat_stats['total']:2d} bets | {strat_stats['won']:2d} won ({strat_wr:4.0f}%) | P/L: {strat_stats['pl']:+7.2f}")

print("\n" + "=" * 80)
print("\n🔍 PROBLEMAS IDENTIFICADOS EL 17/02:")
print("=" * 80)

# Analyze Feb 17 in detail
feb17 = daily_stats["2026-02-17"]
print(f"\n1. VOLUMEN EXCESIVO:")
print(f"   - 38 apuestas (2-3x más que otros días)")
print(f"   - Win rate: {(feb17['won']/feb17['total']*100):.1f}% (por debajo del 50%)")

print(f"\n2. ESTRATEGIAS CON PEOR RENDIMIENTO:")
worst = sorted(feb17["by_strategy"].items(), key=lambda x: x[1]["pl"])[:5]
for strat, stats in worst:
    print(f"   - {strat}: {stats['won']}/{stats['total']} ({stats['won']/stats['total']*100:.0f}%), P/L: {stats['pl']:+.2f}")

print(f"\n3. LIGAS/COMPETICIONES:")
print(f"   - Muchos partidos de League One/Two inglesas (datos menos confiables)")
print(f"   - AFC Champions League (comportamiento atípico)")
print(f"   - Midweek con volumen alto de partidos simultáneos")