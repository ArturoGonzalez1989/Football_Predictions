"""
Season Standings Simulator — 2025/2026 European Leagues
=======================================================
Downloads (or uses cached) match data from football-data.co.uk and generates
comprehensive league standings for every league sheet in the Excel file.

Output: One CSV per league in output/ folder + a combined JSON summary.

Usage:
    python generate_standings.py              # use cached xlsx if present
    python generate_standings.py --refresh    # force re-download
"""

import argparse
import json
import math
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from urllib.request import urlretrieve

import pandas as pd

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
XLSX_URL = "https://www.football-data.co.uk/mmz4281/2526/all-euro-data-2025-2026.xlsx"
XLSX_PATH = BASE_DIR / "all-euro-data-2025-2026.xlsx"
OUTPUT_DIR = BASE_DIR / "output"

LEAGUE_NAMES = {
    "E0": "Premier League",
    "E1": "Championship",
    "E2": "League One",
    "E3": "League Two",
    "EC": "National League",
    "SC0": "Scottish Premiership",
    "SC1": "Scottish Championship",
    "SC2": "Scottish League One",
    "SC3": "Scottish League Two",
    "D1": "Bundesliga",
    "D2": "2. Bundesliga",
    "SP1": "La Liga",
    "SP2": "Segunda Division",
    "I1": "Serie A",
    "I2": "Serie B",
    "F1": "Ligue 1",
    "F2": "Ligue 2",
    "B1": "Belgian Pro League",
    "N1": "Eredivisie",
    "P1": "Primeira Liga",
    "T1": "Turkish Super Lig",
    "G1": "Greek Super League",
}

# ELO config
ELO_INITIAL = 1500
ELO_K = 32
ELO_HOME_ADV = 50

# Stats columns that may exist (H = Home, A = Away in source)
STAT_PAIRS = [
    ("HS", "AS", "shots"),
    ("HST", "AST", "shots_on_target"),
    ("HC", "AC", "corners"),
    ("HF", "AF", "fouls"),
]


# ---------------------------------------------------------------------------
# ELO helpers
# ---------------------------------------------------------------------------
def elo_expected(ra: float, rb: float) -> float:
    return 1.0 / (1.0 + 10 ** ((rb - ra) / 400))


def elo_update(ra: float, rb: float, score_a: float) -> tuple[float, float]:
    """Return (new_ra, new_rb). score_a: 1=win, 0.5=draw, 0=loss."""
    ea = elo_expected(ra, rb)
    eb = 1.0 - ea
    return ra + ELO_K * (score_a - ea), rb + ELO_K * ((1 - score_a) - eb)


# ---------------------------------------------------------------------------
# Team accumulator
# ---------------------------------------------------------------------------
class Team:
    __slots__ = (
        "name", "pj", "g", "e", "p", "gf", "gc",
        "home_pj", "home_g", "home_e", "home_p", "home_gf", "home_gc",
        "away_pj", "away_g", "away_e", "away_p", "away_gf", "away_gc",
        "ht_gf", "ht_gc",
        "shots_f", "shots_a", "shots_on_target_f", "shots_on_target_a",
        "corners_f", "corners_a", "fouls_f", "fouls_a",
        "yellow_cards", "red_cards",
        "clean_sheets", "btts_count", "over25_count",
        "first_half_goals_f", "first_half_goals_a",
        "form", "elo",
        "avg_odds_h", "avg_odds_d", "avg_odds_a",
        "odds_count_h", "odds_count_a",
        "wins_as_fav", "losses_as_fav", "wins_as_dog", "losses_as_dog",
        "last_date",
    )

    def __init__(self, name: str):
        self.name = name
        # Overall
        self.pj = self.g = self.e = self.p = self.gf = self.gc = 0
        # Home
        self.home_pj = self.home_g = self.home_e = self.home_p = 0
        self.home_gf = self.home_gc = 0
        # Away
        self.away_pj = self.away_g = self.away_e = self.away_p = 0
        self.away_gf = self.away_gc = 0
        # Half-time
        self.ht_gf = self.ht_gc = 0
        self.first_half_goals_f = self.first_half_goals_a = 0
        # Stats
        self.shots_f = self.shots_a = 0
        self.shots_on_target_f = self.shots_on_target_a = 0
        self.corners_f = self.corners_a = 0
        self.fouls_f = self.fouls_a = 0
        self.yellow_cards = self.red_cards = 0
        # Derived counters
        self.clean_sheets = 0
        self.btts_count = 0
        self.over25_count = 0
        # Form (last 5: W/D/L)
        self.form: list[str] = []
        # ELO
        self.elo = ELO_INITIAL
        # Betting profile
        self.avg_odds_h = self.avg_odds_d = self.avg_odds_a = 0.0
        self.odds_count_h = self.odds_count_a = 0
        self.wins_as_fav = self.losses_as_fav = 0
        self.wins_as_dog = self.losses_as_dog = 0
        # Last match date
        self.last_date = None

    # -- properties --
    @property
    def pts(self) -> int:
        return self.g * 3 + self.e

    @property
    def gd(self) -> int:
        return self.gf - self.gc

    @property
    def ppg(self) -> float:
        return round(self.pts / self.pj, 2) if self.pj else 0.0

    @property
    def gpg(self) -> float:
        return round(self.gf / self.pj, 2) if self.pj else 0.0

    @property
    def gcpg(self) -> float:
        return round(self.gc / self.pj, 2) if self.pj else 0.0

    @property
    def cs_pct(self) -> float:
        return round(100 * self.clean_sheets / self.pj, 1) if self.pj else 0.0

    @property
    def btts_pct(self) -> float:
        return round(100 * self.btts_count / self.pj, 1) if self.pj else 0.0

    @property
    def over25_pct(self) -> float:
        return round(100 * self.over25_count / self.pj, 1) if self.pj else 0.0

    @property
    def form_str(self) -> str:
        return "".join(self.form[-5:])

    @property
    def form_pts(self) -> int:
        return sum(3 if r == "W" else 1 if r == "D" else 0 for r in self.form[-5:])

    @property
    def shot_accuracy(self) -> float:
        return round(100 * self.shots_on_target_f / self.shots_f, 1) if self.shots_f else 0.0

    @property
    def home_ppg(self) -> float:
        return round((self.home_g * 3 + self.home_e) / self.home_pj, 2) if self.home_pj else 0.0

    @property
    def away_ppg(self) -> float:
        return round((self.away_g * 3 + self.away_e) / self.away_pj, 2) if self.away_pj else 0.0

    def record(self, gf: int, gc: int, is_home: bool, row: pd.Series, date):
        """Record a single match result."""
        self.pj += 1
        self.gf += gf
        self.gc += gc
        self.last_date = date

        if gf > gc:
            self.g += 1
            result = "W"
        elif gf == gc:
            self.e += 1
            result = "D"
        else:
            self.p += 1
            result = "L"

        self.form.append(result)

        # Home / Away split
        if is_home:
            self.home_pj += 1
            self.home_gf += gf
            self.home_gc += gc
            if result == "W":
                self.home_g += 1
            elif result == "D":
                self.home_e += 1
            else:
                self.home_p += 1
        else:
            self.away_pj += 1
            self.away_gf += gf
            self.away_gc += gc
            if result == "W":
                self.away_g += 1
            elif result == "D":
                self.away_e += 1
            else:
                self.away_p += 1

        # Half-time goals
        ht_gf = safe_int(row.get("HTHG" if is_home else "HTAG"))
        ht_gc = safe_int(row.get("HTAG" if is_home else "HTHG"))
        if ht_gf is not None:
            self.first_half_goals_f += ht_gf
        if ht_gc is not None:
            self.first_half_goals_a += ht_gc

        # Clean sheet / BTTS / Over 2.5
        if gc == 0:
            self.clean_sheets += 1
        total_goals = gf + gc
        if gf > 0 and gc > 0:
            self.btts_count += 1
        if total_goals > 2:
            self.over25_count += 1

        # Stats
        for h_col, a_col, attr in STAT_PAIRS:
            my_col = h_col if is_home else a_col
            opp_col = a_col if is_home else h_col
            val_f = safe_int(row.get(my_col))
            val_a = safe_int(row.get(opp_col))
            if val_f is not None:
                setattr(self, f"{attr}_f", getattr(self, f"{attr}_f", 0) + val_f)
            if val_a is not None:
                setattr(self, f"{attr}_a", getattr(self, f"{attr}_a", 0) + val_a)

        # Yellow/Red from team's side
        yc = safe_int(row.get("HY" if is_home else "AY"))
        rc = safe_int(row.get("HR" if is_home else "AR"))
        if yc is not None:
            self.yellow_cards += yc
        if rc is not None:
            self.red_cards += rc

        # Betting profile (Pinnacle odds preferred, fallback to B365)
        odds_h = safe_float(row.get("PSH")) or safe_float(row.get("B365H"))
        odds_a = safe_float(row.get("PSA")) or safe_float(row.get("B365A"))
        if is_home and odds_h:
            self.avg_odds_h = (self.avg_odds_h * self.odds_count_h + odds_h) / (self.odds_count_h + 1)
            self.odds_count_h += 1
            if odds_h < (odds_a or 99):
                if result == "W":
                    self.wins_as_fav += 1
                else:
                    self.losses_as_fav += 1
            elif odds_a and odds_h > odds_a:
                if result == "W":
                    self.wins_as_dog += 1
                else:
                    self.losses_as_dog += 1
        elif not is_home and odds_a:
            self.avg_odds_a = (self.avg_odds_a * self.odds_count_a + odds_a) / (self.odds_count_a + 1)
            self.odds_count_a += 1
            if odds_a < (odds_h or 99):
                if result == "W":
                    self.wins_as_fav += 1
                else:
                    self.losses_as_fav += 1
            elif odds_h and odds_a > odds_h:
                if result == "W":
                    self.wins_as_dog += 1
                else:
                    self.losses_as_dog += 1

    def to_dict(self, rank: int) -> dict:
        return {
            "Pos": rank,
            "Team": self.name,
            "PJ": self.pj,
            "G": self.g,
            "E": self.e,
            "P": self.p,
            "GF": self.gf,
            "GC": self.gc,
            "GD": self.gd,
            "Pts": self.pts,
            "PPG": self.ppg,
            # Home
            "Home_PJ": self.home_pj,
            "Home_G": self.home_g,
            "Home_E": self.home_e,
            "Home_P": self.home_p,
            "Home_GF": self.home_gf,
            "Home_GC": self.home_gc,
            "Home_PPG": self.home_ppg,
            # Away
            "Away_PJ": self.away_pj,
            "Away_G": self.away_g,
            "Away_E": self.away_e,
            "Away_P": self.away_p,
            "Away_GF": self.away_gf,
            "Away_GC": self.away_gc,
            "Away_PPG": self.away_ppg,
            # Goals
            "GPG": self.gpg,
            "GCPG": self.gcpg,
            "1H_GF": self.first_half_goals_f,
            "1H_GC": self.first_half_goals_a,
            # Derived
            "Clean_Sheets": self.clean_sheets,
            "CS%": self.cs_pct,
            "BTTS%": self.btts_pct,
            "Over25%": self.over25_pct,
            # Stats per game
            "Shots_F": self.shots_f,
            "Shots_A": self.shots_a,
            "SoT_F": self.shots_on_target_f,
            "SoT_A": self.shots_on_target_a,
            "Shot_Acc%": self.shot_accuracy,
            "Corners_F": self.corners_f,
            "Corners_A": self.corners_a,
            "Fouls_F": self.fouls_f,
            "Fouls_A": self.fouls_a,
            "Yellow": self.yellow_cards,
            "Red": self.red_cards,
            # Form
            "Form": self.form_str,
            "Form_Pts": self.form_pts,
            # ELO
            "ELO": round(self.elo),
            # Betting
            "Avg_Odds_H": round(self.avg_odds_h, 2),
            "Avg_Odds_A": round(self.avg_odds_a, 2),
            "Wins_Fav": self.wins_as_fav,
            "Losses_Fav": self.losses_as_fav,
            "Wins_Dog": self.wins_as_dog,
            "Losses_Dog": self.losses_as_dog,
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def safe_int(val) -> int | None:
    if val is None or (isinstance(val, float) and math.isnan(val)):
        return None
    try:
        return int(val)
    except (ValueError, TypeError):
        return None


def safe_float(val) -> float | None:
    if val is None or (isinstance(val, float) and math.isnan(val)):
        return None
    try:
        v = float(val)
        return v if not math.isnan(v) else None
    except (ValueError, TypeError):
        return None


def download_xlsx(skip: bool = False):
    if skip and XLSX_PATH.exists():
        print(f"Using cached {XLSX_PATH}")
        return
    print(f"Downloading {XLSX_URL} ...")
    urlretrieve(XLSX_URL, XLSX_PATH)
    print(f"  Saved to {XLSX_PATH}")


def process_league(sheet_name: str, df: pd.DataFrame) -> list[dict]:
    """Process all matches for a single league and return sorted standings."""
    teams: dict[str, Team] = {}

    # Filter rows with actual match data (need home team, goals)
    df = df.dropna(subset=["HomeTeam", "FTHG", "FTAG"])

    # Sort by date
    df = df.sort_values("Date", na_position="last").reset_index(drop=True)

    for _, row in df.iterrows():
        home_name = str(row["HomeTeam"]).strip()
        away_name = str(row["AwayTeam"]).strip()
        fthg = safe_int(row["FTHG"])
        ftag = safe_int(row["FTAG"])

        if fthg is None or ftag is None:
            continue

        # Get or create teams
        if home_name not in teams:
            teams[home_name] = Team(home_name)
        if away_name not in teams:
            teams[away_name] = Team(away_name)

        home = teams[home_name]
        away = teams[away_name]

        # ELO update (before recording result, using pre-match ratings)
        if fthg > ftag:
            score_h = 1.0
        elif fthg == ftag:
            score_h = 0.5
        else:
            score_h = 0.0

        new_elo_h, new_elo_a = elo_update(
            home.elo + ELO_HOME_ADV, away.elo, score_h
        )
        # Remove home advantage from stored ELO
        home.elo = new_elo_h - ELO_HOME_ADV
        away.elo = new_elo_a

        # Record match
        date = row.get("Date")
        home.record(fthg, ftag, is_home=True, row=row, date=date)
        away.record(ftag, fthg, is_home=False, row=row, date=date)

    # Sort: Points desc, GD desc, GF desc, Name asc
    sorted_teams = sorted(
        teams.values(),
        key=lambda t: (-t.pts, -t.gd, -t.gf, t.name),
    )

    return [t.to_dict(rank=i + 1) for i, t in enumerate(sorted_teams)]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Generate league standings from football-data.co.uk")
    parser.add_argument("--offline", action="store_true", help="Skip download, use cached Excel file")
    args = parser.parse_args()

    download_xlsx(skip=args.offline)
    OUTPUT_DIR.mkdir(exist_ok=True)

    # Read all sheets
    print(f"Reading {XLSX_PATH} ...")
    xl = pd.ExcelFile(XLSX_PATH, engine="openpyxl")

    summary = {}
    total_matches = 0

    for sheet_name in xl.sheet_names:
        league_name = LEAGUE_NAMES.get(sheet_name, sheet_name)
        print(f"\n{'='*60}")
        print(f"  {sheet_name} — {league_name}")
        print(f"{'='*60}")

        df = xl.parse(sheet_name)
        standings = process_league(sheet_name, df)

        if not standings:
            print("  (no data)")
            continue

        # Save CSV
        out_csv = OUTPUT_DIR / f"{sheet_name}_{league_name.replace(' ', '_').replace('.', '')}.csv"
        standings_df = pd.DataFrame(standings)
        standings_df.to_csv(out_csv, index=False)

        n_teams = len(standings)
        n_matches = sum(t["PJ"] for t in standings) // 2
        total_matches += n_matches
        leader = standings[0]

        print(f"  Teams: {n_teams} | Matches: {n_matches}")
        print(f"  Leader: {leader['Team']} ({leader['Pts']} pts, GD {leader['GD']:+d}, ELO {leader['ELO']})")
        print(f"  Saved: {out_csv.name}")

        # Print compact table (top 6 + bottom 3)
        print(f"\n  {'Pos':>3} {'Team':<22} {'PJ':>3} {'G':>3} {'E':>3} {'P':>3} {'GF':>3} {'GC':>3} {'GD':>4} {'Pts':>4} {'ELO':>5} {'Form':>6}")
        print(f"  {'---':>3} {'----':<22} {'--':>3} {'--':>3} {'--':>3} {'--':>3} {'--':>3} {'--':>3} {'---':>4} {'---':>4} {'----':>5} {'----':>6}")
        show = standings[:6] + ([{"_sep": True}] + standings[-3:] if n_teams > 9 else standings[6:])
        for s in show:
            if "_sep" in s:
                print(f"  {'...':>3}")
                continue
            print(f"  {s['Pos']:>3} {s['Team']:<22} {s['PJ']:>3} {s['G']:>3} {s['E']:>3} {s['P']:>3} {s['GF']:>3} {s['GC']:>3} {s['GD']:>+4} {s['Pts']:>4} {s['ELO']:>5} {s['Form']:>6}")

        summary[sheet_name] = {
            "league": league_name,
            "teams": n_teams,
            "matches_played": n_matches,
            "leader": leader["Team"],
            "leader_pts": leader["Pts"],
            "leader_elo": leader["ELO"],
            "file": out_csv.name,
        }

    # Save summary JSON
    summary_path = OUTPUT_DIR / "summary.json"
    summary["_meta"] = {
        "generated": datetime.now().isoformat(),
        "source": XLSX_URL,
        "total_matches": total_matches,
        "total_leagues": len(summary) - 1,
    }
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    print(f"\n{'='*60}")
    print(f"  DONE — {total_matches} matches across {len(xl.sheet_names)} leagues")
    print(f"  Output: {OUTPUT_DIR}")
    print(f"  Summary: {summary_path}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
