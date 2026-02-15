"""
Enrich scraped Betfair CSVs with pre-match Betfair Exchange odds from Football Data.

Downloads fixtures.csv + Latest_Results.csv from football-data.co.uk,
maps teams via team_mapping.csv, and adds BFEH/BFED/BFEA columns to each
matching partido_*.csv.

Usage:
    python enrich_prematch_odds.py             # use cached files if <12h old
    python enrich_prematch_odds.py --force      # re-download all sources
    python enrich_prematch_odds.py --dry-run    # preview without modifying CSVs
"""

import csv
import glob
import os
import re
import sys
import time
from urllib.parse import unquote
from urllib.request import urlretrieve

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "betfair_scraper", "data")
MAPPING_PATH = os.path.join(BASE_DIR, "historic_data", "team_mapping.csv")
SOURCES = [
    ("https://www.football-data.co.uk/fixtures.csv", "fixtures_cache.csv"),
    ("https://www.football-data.co.uk/mmz4281/2526/Latest_Results.csv", "latest_results.csv"),
]


def load_team_mapping() -> dict[str, tuple[str, str]]:
    """Load betfair_slug -> (football_data_name, league) mapping."""
    mapping = {}
    with open(MAPPING_PATH, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row["football_data_name"]:
                mapping[row["betfair_slug"]] = (
                    row["football_data_name"],
                    row["league"],
                )
    return mapping


def download_sources(force: bool = False) -> None:
    """Download fixtures + results CSVs, caching locally."""
    for url, filename in SOURCES:
        cache_path = os.path.join(BASE_DIR, "historic_data", filename)
        if not force and os.path.exists(cache_path):
            age_h = (time.time() - os.path.getmtime(cache_path)) / 3600
            if age_h < 12:
                print(f"  Cache {filename} ({age_h:.1f}h)")
                continue
        print(f"  Descargando {filename}...")
        urlretrieve(url, cache_path)


def load_fixtures() -> dict[tuple[str, str], tuple[str, str, str]]:
    """Load all sources into (HomeTeam, AwayTeam) -> (BFEH, BFED, BFEA) lookup."""
    fixtures = {}
    for _, filename in SOURCES:
        cache_path = os.path.join(BASE_DIR, "historic_data", filename)
        if not os.path.exists(cache_path):
            continue
        with open(cache_path, encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                home = row.get("HomeTeam", "").strip()
                away = row.get("AwayTeam", "").strip()
                bfeh = row.get("BFEH", "").strip()
                bfed = row.get("BFED", "").strip()
                bfea = row.get("BFEA", "").strip()
                if home and away and (home, away) not in fixtures:
                    fixtures[(home, away)] = (bfeh, bfed, bfea)
    return fixtures


def extract_slug(filename: str) -> str:
    """Extract match slug from partido_*.csv filename (same logic as build_team_mapping)."""
    name = os.path.basename(filename)
    name = name.replace("partido_", "").replace(".csv", "")
    name = re.sub(r"-apuestas-.*$", "", name)
    name = unquote(name)
    return name


def split_slug(slug: str, mapping: dict) -> tuple[tuple[str, str] | None, int]:
    """Split match slug into (home_slug, away_slug) using mapping for validation.

    Returns (best_split, score) where score = number of teams found in mapping (0-2).
    """
    parts = slug.split("-")
    best = None
    best_score = -1

    for i in range(1, len(parts)):
        t1 = "-".join(parts[:i])
        t2 = "-".join(parts[i:])
        score = (1 if t1 in mapping else 0) + (1 if t2 in mapping else 0)
        if score > best_score:
            best_score = score
            best = (t1, t2)

    return best, best_score


def enrich_csv(path: str, bfeh: str, bfed: str, bfea: str) -> bool:
    """Add BFEH/BFED/BFEA columns to a CSV file. Returns False if already enriched."""
    with open(path, encoding="utf-8") as f:
        rows = list(csv.reader(f))

    if not rows or "BFEH" in rows[0]:
        return False

    rows[0].extend(["BFEH", "BFED", "BFEA"])
    for row in rows[1:]:
        row.extend([bfeh, bfed, bfea])

    with open(path, "w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerows(rows)

    return True


def main():
    force = "--force" in sys.argv
    dry_run = "--dry-run" in sys.argv

    print("=== Enriquecimiento de CSVs con odds pre-match BFE ===\n")

    # 1. Load team mapping
    mapping = load_team_mapping()
    print(f"  Mapping: {len(mapping)} equipos mapeados")

    # 2. Download/cache sources
    download_sources(force)
    fixtures = load_fixtures()
    with_odds = sum(1 for v in fixtures.values() if any(v))
    print(f"  Fixtures: {len(fixtures)} partidos ({with_odds} con odds BFE)")

    # 3. Process each CSV
    csv_files = sorted(glob.glob(os.path.join(DATA_DIR, "partido_*.csv")))
    print(f"  CSVs: {len(csv_files)} archivos\n")

    enriched = []
    skipped_no_mapping = []
    skipped_no_fixture = []
    skipped_already = []
    skipped_no_odds = []

    for csv_path in csv_files:
        slug = extract_slug(csv_path)
        split, score = split_slug(slug, mapping)

        if not split or score < 2:
            skipped_no_mapping.append(slug)
            continue

        home_slug, away_slug = split
        fd_home = mapping[home_slug][0]
        fd_away = mapping[away_slug][0]

        key = (fd_home, fd_away)
        if key not in fixtures:
            skipped_no_fixture.append((slug, fd_home, fd_away))
            continue

        bfeh, bfed, bfea = fixtures[key]

        if not any([bfeh, bfed, bfea]):
            skipped_no_odds.append((slug, fd_home, fd_away))
            continue

        if dry_run:
            enriched.append((slug, fd_home, fd_away, bfeh, bfed, bfea))
        else:
            ok = enrich_csv(csv_path, bfeh, bfed, bfea)
            if ok:
                enriched.append((slug, fd_home, fd_away, bfeh, bfed, bfea))
            else:
                skipped_already.append(slug)

    # Summary
    prefix = "[DRY RUN] " if dry_run else ""
    print(f"{prefix}RESULTADOS:")
    print(f"  Enriquecidos:    {len(enriched)}")
    print(f"  Sin mapping:     {len(skipped_no_mapping)}")
    print(f"  Sin fixture:     {len(skipped_no_fixture)}")
    print(f"  Sin odds BFE:    {len(skipped_no_odds)}")
    if skipped_already:
        print(f"  Ya enriquecidos: {len(skipped_already)}")

    if enriched:
        print(f"\n{'PARTIDOS A ENRIQUECER' if dry_run else 'PARTIDOS ENRIQUECIDOS'}:")
        for slug, h, a, bfeh, bfed, bfea in enriched:
            print(f"  {h:20s} vs {a:20s}  BFEH={bfeh:>6s} BFED={bfed:>6s} BFEA={bfea:>6s}")

    if skipped_no_fixture:
        print(f"\nSIN DATOS EN FIXTURES.CSV:")
        for slug, h, a in skipped_no_fixture:
            print(f"  {h:20s} vs {a:20s}")

    if skipped_no_mapping:
        print(f"\nSIN MAPPING ({len(skipped_no_mapping)} partidos - ligas no europeas/mujeres):")
        for slug in skipped_no_mapping[:10]:
            print(f"  {slug}")
        if len(skipped_no_mapping) > 10:
            print(f"  ... y {len(skipped_no_mapping) - 10} mas")


if __name__ == "__main__":
    main()
