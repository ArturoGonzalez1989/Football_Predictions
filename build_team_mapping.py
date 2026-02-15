"""
Build team name mapping between Betfair scraper slugs and Football Data names.

Reads:
  - betfair_scraper/data/partido_*.csv  (team slugs from filenames)
  - historic_data/all-euro-data-2025-2026.xlsx (Football Data team names)

Outputs:
  - historic_data/team_mapping.csv
"""

import csv
import glob
import os
import re
from urllib.parse import unquote
from difflib import SequenceMatcher

import openpyxl

DATA_DIR = os.path.join(os.path.dirname(__file__), "betfair_scraper", "data")
EXCEL_PATH = os.path.join(os.path.dirname(__file__), "historic_data", "all-euro-data-2025-2026.xlsx")
OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "historic_data", "team_mapping.csv")


def normalize(s: str) -> str:
    """Normalize a string for comparison: lowercase, remove accents, remove common suffixes."""
    s = s.lower().strip()
    # Common replacements
    s = s.replace("ü", "u").replace("ö", "o").replace("ä", "a")
    s = s.replace("á", "a").replace("é", "e").replace("í", "i").replace("ó", "o").replace("ú", "u")
    s = s.replace("ñ", "n").replace("ç", "c")
    s = s.replace("'", "").replace("'", "")
    return s


def slug_to_words(slug: str) -> str:
    """Convert a Betfair slug to space-separated words."""
    return slug.replace("-", " ")


def similarity(a: str, b: str) -> float:
    """Calculate string similarity between two normalized strings."""
    return SequenceMatcher(None, normalize(a), normalize(b)).ratio()


def get_betfair_slugs() -> list[str]:
    """Extract unique match slugs from CSV filenames."""
    files = glob.glob(os.path.join(DATA_DIR, "partido_*.csv"))
    slugs = set()
    for f in files:
        name = os.path.basename(f).replace("partido_", "").replace(".csv", "")
        name = re.sub(r"-apuestas-.*$", "", name)
        name = unquote(name)
        slugs.add(name)
    return sorted(slugs)


def get_fd_teams() -> dict[str, str]:
    """Get all Football Data team names with their league."""
    wb = openpyxl.load_workbook(EXCEL_PATH, read_only=True)
    teams = {}
    for ws in wb.worksheets:
        for row in ws.iter_rows(min_row=2, values_only=True):
            if row and len(row) > 4:
                div = str(row[0]).strip() if row[0] else ""
                h = str(row[3]).strip() if row[3] else ""
                a = str(row[4]).strip() if row[4] else ""
                if h and not h[0].isdigit():
                    teams[h] = div
                if a and not a[0].isdigit():
                    teams[a] = div
    return teams


# Manual mappings for known tricky cases
# betfair_slug_part -> football_data_name
MANUAL_MAP = {
    # Spain
    "atlético-de-madrid": "Ath Madrid",
    "atletico-de-madrid": "Ath Madrid",
    "fc-barcelona": "Barcelona",
    "real-madrid": "Real Madrid",
    "real-sociedad": "Sociedad",
    "celta-de-vigo": "Celta",
    "athletic-de-bilbao": "Ath Bilbao",
    "alavés": "Alaves",
    "leganés": "Leganes",
    "mirandés": "Mirandes",
    "las-palmas": "Las Palmas",
    # Germany
    "borussia-dortmund": "Dortmund",
    "eintracht-frankfurt": "Ein Frankfurt",
    "b-mönchengladbach": "M'gladbach",
    "b-mönchengladbach-apuesta": "M'gladbach",
    "bayern-múnich": "Bayern Munich",
    "werder-bremen": "Werder Bremen",
    "hertha-berlín": "Hertha",
    "unión-berlín": "Union Berlin",
    "dynamo-dresden": "Dresden",
    "fortuna-dusseldorf": "Fortuna Dusseldorf",
    "preussen-munster": "Preußen Münster",
    "greuther-fürth": "Greuther Furth",
    "nüremberg": "Nurnberg",
    "fc-magdeburg": "Magdeburg",
    "arminia-bielefeld": "Bielefeld",
    "hamburgo": "Hamburg",
    "schalke-04": "Schalke 04",
    "st-pauli": "St Pauli",
    # Italy
    "ac-milán": "Milan",
    # France
    "mónaco": "Monaco",
    "paris-fc": "Paris FC",
    # Netherlands
    "fc-groningen": "Groningen",
    "fortuna-sittard": "For Sittard",
    "go-ahead-eagles": "Go Ahead Eagles",
    # Belgium
    "círculo-brujas": "Cercle Brugge",
    "club-brugge": "Club Brugge",
    "gante": "Gent",
    "standard-de-lieja": "Standard",
    "union-st-gilloise": "St. Gilloise",
    "yellow-red-mechelen": "Mechelen",
    # Turkey
    "gaziantep-fk": "Gaziantep",
    # Portugal
    "guimaraes-club-football": "Guimaraes",  # Betfair adds "club football"
    # Greece
    "levadiakos": "Levadeiakos",
    # England
    "afc-wimbledon": "AFC Wimbledon",
    "notts-county": "Notts County",
    "burton-albion": "Burton",
    "west-ham": "West Ham",
    # Switzerland
    "fc-zurich": "FC Zurich",
    "fc-basel": "FC Basel",
    "grasshoppers-zurich": "Grasshoppers",
    "st-gallen": "St Gallen",
    # Non-European (no FD equivalent)
    "america-de-cali-sa": None,
    "santa-fe": None,
    "corinthians": None,
    "red-bull-bragantino": None,
    "athletico-pr": None,
    "santos": None,
    "fluminense": None,
    "botafogo-fr": None,
    "internacional-se": None,
    "palmeiras": None,
    "independiente-rivadavia": None,
    "belgrano": None,
    "atl-tucuman": None,
    "estudiantes-rio-cuarto": None,
    "atletico-nacional-medellin": None,
    "fortaleza": None,
    "deportivo-pasto": None,
    "internacional-de-bogotá-apues": None,
    "liverpool-montevideo": None,
    "defensor-sp": None,
    "palestino": None,
    "universidad-de-chile": None,
    "univ-catolica-ecu": None,
    "juventud-de-las-piedras-apuestas": None,
    "arema-cronus": None,
    "semen-padang": None,
    "fc-gifu": None,
    "iwata": None,
    "ehime": None,
    "kanazawa": None,
    "fc-osaka": None,
    "kochi-univ": None,
    "kagoshima-utd": None,
    "fc-ryukyu": None,
    "kamatamare-sanuki": None,
    "toyama": None,
    "oita": None,
    "kitakyushu": None,
    "renofa-yamaguchi": None,
    "mio-biwako-shiga": None,
    "tegevajaro-miyazaki": None,
    "tottori": None,
    "tochigi-sc": None,
    "yamagata": None,
    "tochigi-uva-fc": None,
    "blaublitz-akita": None,
    "tokushima": None,
    "albirex-niigata": None,
    "tosu": None,
    "kumamoto": None,
    "monterrey": None,
    "leon": None,
    "fc-juarez": None,
    "necaxa": None,
    "atletico-san-luis": None,
    "querétaro": None,
    "pachuca": None,
    "atlas": None,
    "puebla": None,
    "pumas-unam": None,
    "anorthosis": None,
    "digenis-ypsona": None,
    "cska-1948-sofia": None,
    "cska-sofía": None,
    "lokomotiv-plovdiv": None,
    "cherno-more-varna": None,
    "ludogorets-razgrad": None,
    "beroe-stara-za": None,
    "spartak-varna": None,
    "lokomotiv-sofia": None,
    "olympiakos-nicosia-fc": None,
    "omonia-fc-aradippou-apuestas": None,
    "fredericia": None,
    "agf": None,
    "fc-copenague": None,
    "fc-nordsjaelland": None,
    "young-boys": None,
    "winterthur": None,
    "thun": None,
    "lausanne": None,
    "sion": None,
    "lucerna": None,
    # Women's football
    "aston-villa-femenino": None,
    "tottenham-femenino": None,
    "chelsea-femenino": None,
    "liverpool-femenino": None,
    "everton-femenino": None,
    "west-ham-united-w": None,
    # Betfair-specific cleanup
    "estrela": "Estrela",
    "leonesa": "Cultural Leonesa",
    "friburgo": "Freiburg",
    "kiel": "Holstein Kiel",
    "olympiacos": "Olympiakos",
    "núremberg": "Nurnberg",
    "espanyol": "Espanol",
    # Switzerland (not in FD but keep slug clean)
    "lucerna": None,
    "fc-copenague": None,
    "fc-nordsjaelland": None,
    "fc-basel": None,
}


def find_best_fd_match(betfair_part: str, fd_teams: dict[str, str]) -> tuple[str | None, float]:
    """Find the best Football Data match for a Betfair team slug part."""
    # Check manual map first
    if betfair_part in MANUAL_MAP:
        return MANUAL_MAP[betfair_part], 1.0

    words = slug_to_words(betfair_part)

    # Try exact match (normalized)
    for fd_name in fd_teams:
        if normalize(words) == normalize(fd_name):
            return fd_name, 1.0

    # Try fuzzy match
    best_match = None
    best_score = 0
    for fd_name in fd_teams:
        score = similarity(words, fd_name)
        if score > best_score:
            best_score = score
            best_match = fd_name

    if best_score >= 0.6:
        return best_match, best_score

    return None, 0


def split_slug_into_teams(slug: str) -> list[tuple[str, str | None, float]]:
    """
    Split a betfair slug into two team names and find FD matches.
    Returns list of (betfair_part, fd_match, score) tuples.
    """
    fd_teams = get_fd_teams()
    parts = slug.split("-")
    n = len(parts)

    # Try all possible split points
    best_split = None
    best_total_score = -1

    for split_at in range(1, n):
        team1_slug = "-".join(parts[:split_at])
        team2_slug = "-".join(parts[split_at:])

        fd1, score1 = find_best_fd_match(team1_slug, fd_teams)
        fd2, score2 = find_best_fd_match(team2_slug, fd_teams)

        total = score1 + score2
        if total > best_total_score:
            best_total_score = total
            best_split = [
                (team1_slug, fd1, score1),
                (team2_slug, fd2, score2),
            ]

    return best_split


def main():
    fd_teams = get_fd_teams()
    slugs = get_betfair_slugs()

    print(f"Betfair slugs: {len(slugs)}")
    print(f"Football Data teams: {len(fd_teams)}")
    print()

    results = []

    for slug in slugs:
        split = split_slug_into_teams(slug)
        if split:
            for betfair_part, fd_match, score in split:
                results.append({
                    "betfair_slug": betfair_part,
                    "football_data_name": fd_match or "",
                    "confidence": round(score, 2),
                    "match_slug": slug,
                    "league": fd_teams.get(fd_match, "") if fd_match else "",
                })

    # Deduplicate: keep the best match per betfair_slug
    best = {}
    for r in results:
        key = r["betfair_slug"]
        if key not in best or r["confidence"] > best[key]["confidence"]:
            best[key] = r

    # Write output
    rows = sorted(best.values(), key=lambda x: x["betfair_slug"])

    with open(OUTPUT_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["betfair_slug", "football_data_name", "league", "confidence"])
        writer.writeheader()
        for r in rows:
            writer.writerow({
                "betfair_slug": r["betfair_slug"],
                "football_data_name": r["football_data_name"],
                "league": r["league"],
                "confidence": r["confidence"],
            })

    print(f"Written {len(rows)} mappings to {OUTPUT_PATH}")
    print()

    # Summary
    mapped = [r for r in rows if r["football_data_name"]]
    unmapped = [r for r in rows if not r["football_data_name"]]
    low_conf = [r for r in mapped if r["confidence"] < 0.8]

    print(f"Mapped:   {len(mapped)} teams (have FD equivalent)")
    print(f"Unmapped: {len(unmapped)} teams (non-European / no FD data)")
    print()

    if low_conf:
        print("LOW CONFIDENCE MATCHES (review manually):")
        for r in low_conf:
            print(f"  {r['betfair_slug']:40s} -> {r['football_data_name']:20s} ({r['confidence']})")
        print()

    print("SAMPLE MAPPINGS:")
    for r in rows[:30]:
        fd = r["football_data_name"] or "(no FD equivalent)"
        lg = f" [{r['league']}]" if r["league"] else ""
        c = f" ({r['confidence']})" if r["football_data_name"] else ""
        print(f"  {r['betfair_slug']:45s} -> {fd}{lg}{c}")

    if len(rows) > 30:
        print(f"  ... and {len(rows) - 30} more")


if __name__ == "__main__":
    main()
