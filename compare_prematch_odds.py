#!/usr/bin/env python3
"""Compara cuotas pre-partido del scraper (Betfair Exchange) con datos del Excel historico.

Usa fuzzy matching automatico para encontrar coincidencias entre los nombres de equipos
del scraper (formato URL: "real-madrid-real-sociedad") y del Excel (formato: "Real Madrid" vs "Sociedad").
"""

import pandas as pd
import glob
import os
import re
from urllib.parse import unquote
from difflib import SequenceMatcher

DATA_DIR = r'c:\Users\agonz\OneDrive\Documents\Proyectos\Furbo\betfair_scraper\data'
EXCEL_PATH = r'c:\Users\agonz\OneDrive\Documents\Proyectos\Furbo\historic_data\all-euro-data-2025-2026.xlsx'


def normalize(s: str) -> str:
    """Normalize a string for fuzzy comparison: lowercase, remove accents, extra spaces."""
    s = s.lower().strip()
    # Common accent replacements
    replacements = {
        'á': 'a', 'é': 'e', 'í': 'i', 'ó': 'o', 'ú': 'u',
        'ä': 'a', 'ë': 'e', 'ï': 'i', 'ö': 'o', 'ü': 'u',
        'ñ': 'n', 'ç': 'c', 'ø': 'o', 'å': 'a',
    }
    for old, new in replacements.items():
        s = s.replace(old, new)
    # Remove common suffixes/prefixes that differ between sources
    s = re.sub(r'\bfc\b', '', s)
    s = re.sub(r'\bsc\b', '', s)
    s = re.sub(r'\bsv\b', '', s)
    s = re.sub(r'\bcf\b', '', s)
    s = re.sub(r'\bud\b', '', s)
    s = re.sub(r'\bcd\b', '', s)
    s = re.sub(r'\b1\.\b', '', s)  # "1. FC" patterns
    s = re.sub(r'\s+', ' ', s).strip()
    return s


def similarity(a: str, b: str) -> float:
    """Calculate similarity ratio between two normalized strings."""
    return SequenceMatcher(None, normalize(a), normalize(b)).ratio()


def extract_teams_from_filename(filename: str) -> str:
    """Extract the match name from a CSV filename, URL-decoded and cleaned."""
    name = filename.replace('partido_', '').replace('.csv', '')
    name = unquote(name)
    # Remove the trailing -apuestas-XXXX part
    name = re.sub(r'-apuestas-\d+.*$', '', name)
    return name


def build_excel_key(home: str, away: str) -> str:
    """Build a comparable key from Excel team names."""
    return f"{normalize(home)} {normalize(away)}"


# Alias map: Excel name -> list of scraper name variations
ALIAS_MAP = {
    'ath madrid': ['atletico madrid', 'atletico de madrid'],
    'ath bilbao': ['athletic bilbao', 'athletic de bilbao', 'athletic club'],
    "m'gladbach": ['monchengladbach', 'borussia monchengladbach', 'b monchengladbach'],
    'man city': ['manchester city'],
    'man united': ['manchester united', 'manchester utd'],
    'sheffield utd': ['sheffield united'],
    'sheffield wed': ['sheffield wednesday'],
    'west ham': ['west ham united'],
    'west brom': ['west bromwich', 'west bromwich albion'],
    'newcastle': ['newcastle united'],
    'wolves': ['wolverhampton'],
    "nott'm forest": ['nottingham forest', 'nottingham'],
    'tottenham': ['tottenham hotspur'],
    'brighton': ['brighton hove albion', 'brighton and hove albion'],
    'bayern munich': ['bayern munchen', 'bayern munich'],
    'ein frankfurt': ['eintracht frankfurt'],
    'fortuna dusseldorf': ['fortuna dusseldorf'],
    'greuther furth': ['greuther furth', 'greuther fuerth'],
    'nurnberg': ['nuremberg', 'nurnberg', 'nuremberg'],
    'st pauli': ['sankt pauli', 'st pauli'],
    'sp lisbon': ['sporting lisbon', 'sporting cp', 'sporting'],
    'guimaraes': ['vitoria guimaraes'],
    'st etienne': ['saint etienne', 'st etienne'],
    'paris sg': ['paris saint germain', 'paris'],
    'betis': ['real betis'],
    'sociedad': ['real sociedad'],
    'vallecano': ['rayo vallecano'],
    'espanol': ['espanyol'],
    'celta': ['celta de vigo', 'celta vigo'],
    'alaves': ['deportivo alaves', 'alaves'],
    'leganes': ['leganes'],
    'valladolid': ['real valladolid', 'valladolid'],
    'las palmas': ['ud las palmas', 'las palmas'],
    'cordoba': ['cordoba'],
    'zaragoza': ['real zaragoza'],
    'leonesa': ['cultural leonesa', 'leonesa'],
    'club brugge': ['club brugge', 'club bruges'],
    'gent': ['gante', 'kaa gent'],
    'genk': ['racing genk'],
    'mechelen': ['yellow red mechelen', 'kv mechelen'],
    'standard': ['standard liege', 'standard de lieja'],
    'st gilloise': ['union st gilloise', 'union saint gilloise'],
    'charleroi': ['charleroi'],
    'como': ['como'],
    'inter': ['inter milan', 'inter'],
    'fiorentina': ['fiorentina'],
    'lazio': ['lazio'],
    'atalanta': ['atalanta'],
    'juventus': ['juventus'],
    'milan': ['ac milan', 'milan'],
    'pisa': ['pisa'],
    'monaco': ['monaco'],
    'nantes': ['nantes'],
    'lens': ['lens'],
    'copenhagen': ['copenague', 'copenhagen'],
    'nordsjaelland': ['nordsjaelland'],
    'zurich': ['zurich'],
    'lucerne': ['lucerna'],
    'leverkusen': ['leverkusen', 'bayer leverkusen'],
    'hoffenheim': ['hoffenheim'],
    'freiburg': ['friburgo', 'freiburg'],
    'dortmund': ['borussia dortmund', 'dortmund'],
    'mainz': ['mainz'],
    'werder bremen': ['werder bremen'],
    'hamburg': ['hamburgo', 'hamburg'],
    'hertha': ['hertha berlin', 'hertha'],
    'elversberg': ['elversberg'],
    'dynamo dresden': ['dynamo dresden'],
    'osasuna': ['osasuna'],
    'elche': ['elche'],
    'sevilla': ['sevilla'],
    'espanyol': ['espanyol'],
    'ajax': ['ajax'],
    'utrecht': ['utrecht'],
    'groningen': ['groningen'],
    'fenerbahce': ['fenerbahce'],
    'trabzonspor': ['trabzonspor'],
    'galatasaray': ['galatasaray'],
    'eyupspor': ['eyupspor'],
    'genclerbirligi': ['genclerbirligi'],
    'rizespor': ['rizespor'],
    'olympiakos': ['olympiacos', 'olympiakos'],
    'levadiakos': ['levadiakos'],
    'burton': ['burton albion'],
    'barnsley': ['barnsley'],
    'blackpool': ['blackpool'],
    'plymouth': ['plymouth'],
    'bromley': ['bromley'],
    'notts county': ['notts county'],
    'barrow': ['barrow'],
    'colchester': ['colchester'],
    'barnet': ['barnet'],
    'cheltenham': ['cheltenham'],
    'reading': ['reading'],
    'wycombe': ['wycombe'],
    'stevenage': ['stevenage'],
    'huddersfield': ['huddersfield'],
    'hull': ['hull city', 'hull'],
    'chelsea': ['chelsea'],
    'wrexham': ['wrexham'],
    'ipswich': ['ipswich'],
}

# Reverse alias map: scraper variation -> excel name
REVERSE_ALIAS = {}
for excel_name, aliases in ALIAS_MAP.items():
    for alias in aliases:
        REVERSE_ALIAS[alias] = excel_name


def match_single_team(team_excel: str, scraper_full: str) -> float:
    """Score how well a single Excel team name is found within the scraper match string.

    Returns 0.0-1.0. Requires a clear presence of the team in the string.
    """
    team_norm = normalize(team_excel)
    s = scraper_full  # already normalized

    # 1. Direct substring match
    if team_norm in s:
        return 1.0

    # 2. Check via alias map
    if team_norm in ALIAS_MAP:
        for alias in ALIAS_MAP[team_norm]:
            if alias in s:
                return 0.95

    # 3. Check significant words (4+ chars) - ALL must match
    words = [w for w in team_norm.split() if len(w) >= 4]
    if words:
        matched = 0
        for w in words:
            if w in s:
                matched += 1
            else:
                # Try fuzzy match for this word against scraper words
                scraper_words = s.split()
                best_word_ratio = 0
                for sw in scraper_words:
                    if len(sw) >= 3:
                        r = SequenceMatcher(None, w, sw).ratio()
                        best_word_ratio = max(best_word_ratio, r)
                if best_word_ratio >= 0.8:
                    matched += 0.8

        word_score = matched / len(words)
        if word_score >= 0.8:
            return word_score * 0.9

    # 4. Short team names (< 4 chars each word): require exact match
    if not words:
        # All words are short, check full name
        if team_norm in s:
            return 1.0
        # Check aliases
        if team_norm in ALIAS_MAP:
            for alias in ALIAS_MAP[team_norm]:
                if alias in s:
                    return 0.9
        return 0.0

    return 0.0


def fuzzy_match_teams(scraper_name: str, excel_home: str, excel_away: str) -> float:
    """Calculate how well a scraper match name matches an Excel home-away pair.

    CRITICAL: BOTH teams must be independently found in the scraper name.
    Returns 0.0 if either team is not found.
    """
    scraper_norm = normalize(scraper_name.replace('-', ' '))

    home_score = match_single_team(excel_home, scraper_norm)
    away_score = match_single_team(excel_away, scraper_norm)

    # BOTH teams must score above minimum threshold
    if home_score < 0.7 or away_score < 0.7:
        return 0.0

    # Return the minimum (weakest link)
    return min(home_score, away_score)


def load_excel():
    """Load all sheets from Excel, return combined DataFrame."""
    xls = pd.ExcelFile(EXCEL_PATH)
    frames = []
    for sheet in xls.sheet_names:
        df = pd.read_excel(xls, sheet_name=sheet)
        df['_sheet'] = sheet
        frames.append(df)
    excel_df = pd.concat(frames, ignore_index=True).copy()
    excel_df['_date'] = pd.to_datetime(excel_df['Date'], errors='coerce')
    return excel_df


def load_scraper_prematch():
    """Load all scraper matches that have pre-match odds."""
    files = glob.glob(os.path.join(DATA_DIR, 'partido_*.csv'))
    matches = []

    for f in files:
        try:
            df = pd.read_csv(f)
            if 'estado_partido' not in df.columns:
                continue

            match_name = extract_teams_from_filename(os.path.basename(f))

            pre = df[df['estado_partido'] == 'pre_partido']
            if len(pre) == 0:
                continue

            for col in ['back_home', 'back_draw', 'back_away']:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')

            pre = df[df['estado_partido'] == 'pre_partido'].copy()
            bh = pre['back_home'].dropna().tolist() if 'back_home' in pre.columns else []
            bd = pre['back_draw'].dropna().tolist() if 'back_draw' in pre.columns else []
            ba = pre['back_away'].dropna().tolist() if 'back_away' in pre.columns else []

            if not bh or not bd or not ba:
                continue

            # Get timestamp of last pre-match capture
            ts_col = 'timestamp_utc' if 'timestamp_utc' in pre.columns else 'timestamp'
            capture_date = None
            if ts_col in pre.columns:
                try:
                    capture_date = pd.to_datetime(pre[ts_col].iloc[-1])
                except Exception:
                    pass

            matches.append({
                'file': os.path.basename(f),
                'name': match_name,
                'back_home': bh[-1],
                'back_draw': bd[-1],
                'back_away': ba[-1],
                'capture_date': capture_date,
            })
        except Exception as e:
            pass

    return matches


def find_best_match(scraper_match, excel_df, date_window_days=3):
    """Find the best matching Excel row for a scraper match using fuzzy matching.

    Returns (best_row, score, match_type) or (None, 0, None).
    match_type: 'exact_date' if within date_window_days, 'same_teams' if same matchup but different date.
    """
    scraper_name = scraper_match['name']
    capture_date = scraper_match['capture_date']

    best_row = None
    best_score = 0
    best_type = None

    for idx, row in excel_df.iterrows():
        home = str(row.get('HomeTeam', ''))
        away = str(row.get('AwayTeam', ''))

        if not home or not away or home == 'nan' or away == 'nan':
            continue

        # Check if this row has Betfair Exchange odds
        bfeh = row.get('BFEH')
        bfed = row.get('BFED')
        bfea = row.get('BFEA')
        if pd.isna(bfeh) and pd.isna(bfed) and pd.isna(bfea):
            continue

        # Calculate team name similarity
        team_score = fuzzy_match_teams(scraper_name, home, away)

        if team_score < 0.55:  # Threshold: below this, it's not a match
            continue

        # Date proximity bonus
        date_bonus = 0
        match_type = 'same_teams'
        if capture_date and pd.notna(row.get('_date')):
            days_diff = abs((capture_date - row['_date']).total_seconds()) / 86400
            if days_diff <= date_window_days:
                date_bonus = 0.3 * (1 - days_diff / date_window_days)
                match_type = 'exact_date'
            elif days_diff <= 30:
                date_bonus = 0.05

        total_score = team_score + date_bonus

        if total_score > best_score:
            best_score = total_score
            best_row = row
            best_type = match_type

    # Only return if score is good enough
    if best_score >= 0.6:
        return best_row, best_score, best_type
    return None, 0, None


def main():
    print("Cargando datos...")
    excel_df = load_excel()
    scraper_matches = load_scraper_prematch()

    print(f"Excel: {len(excel_df)} partidos")
    print(f"Scraper: {len(scraper_matches)} partidos con cuotas pre-match")
    print()

    # ======= FUZZY MATCHING =======
    print("=" * 130)
    print("  FUZZY MATCHING: Buscando cada partido del scraper en el Excel")
    print("=" * 130)
    print()

    exact_date_matches = []
    same_teams_matches = []
    not_found = []

    for sm in scraper_matches:
        print(f"  Buscando: {sm['name'][:50]:<50} (fecha: {sm['capture_date'].date() if sm['capture_date'] else '?'}) ... ", end='')

        row, score, match_type = find_best_match(sm, excel_df)

        if row is not None:
            home = row.get('HomeTeam', '?')
            away = row.get('AwayTeam', '?')
            sheet = row.get('_sheet', '?')
            excel_date = row['_date'].date() if pd.notna(row.get('_date')) else '?'

            result = {
                'scraper': sm,
                'excel_row': row,
                'score': score,
                'match_type': match_type,
                'excel_home': home,
                'excel_away': away,
                'excel_date': excel_date,
                'excel_sheet': sheet,
            }

            if match_type == 'exact_date':
                exact_date_matches.append(result)
                print(f"FOUND (exact) -> {home} vs {away} ({excel_date}, {sheet}) [score={score:.2f}]")
            else:
                same_teams_matches.append(result)
                print(f"FOUND (diff date) -> {home} vs {away} ({excel_date}, {sheet}) [score={score:.2f}]")
        else:
            not_found.append(sm)
            print("NOT FOUND")

    print()
    print(f"  Resumen: {len(exact_date_matches)} misma fecha, {len(same_teams_matches)} otra fecha, {len(not_found)} no encontrados")
    print()

    # ======= EXACT DATE COMPARISON =======
    if exact_date_matches:
        print("=" * 130)
        print(f"  COMPARACION DIRECTA - Mismo partido, misma fecha ({len(exact_date_matches)} partidos)")
        print("=" * 130)
        print()

        header = (f"  {'Partido':<45} {'Fecha':<12} "
                  f"{'Scr H':>7} {'BFE H':>7} {'%Diff':>6}  "
                  f"{'Scr D':>7} {'BFE D':>7} {'%Diff':>6}  "
                  f"{'Scr A':>7} {'BFE A':>7} {'%Diff':>6}")
        print(header)
        print("  " + "-" * 125)

        all_diffs = []

        for m in exact_date_matches:
            s = m['scraper']
            r = m['excel_row']
            name = f"{m['excel_home']} vs {m['excel_away']}"

            diffs_row = []
            cols = []
            for label, scr_val, bfe_col in [('H', s['back_home'], 'BFEH'), ('D', s['back_draw'], 'BFED'), ('A', s['back_away'], 'BFEA')]:
                bfe_val = r.get(bfe_col)
                if pd.notna(bfe_val) and bfe_val > 0:
                    pct = (scr_val - bfe_val) / bfe_val * 100
                    diffs_row.append(abs(pct))
                    cols.append(f"{scr_val:>7.2f} {bfe_val:>7.2f} {pct:>+5.1f}%")
                else:
                    cols.append(f"{scr_val:>7.2f} {'N/A':>7} {'':>6}")

            avg_diff = sum(diffs_row) / len(diffs_row) if diffs_row else 0
            all_diffs.extend(diffs_row)

            print(f"  {name:<45} {str(m['excel_date']):<12} {'  '.join(cols)}")

        print()
        if all_diffs:
            print(f"  Diferencia media absoluta: {sum(all_diffs)/len(all_diffs):.1f}%")
            print(f"  Diferencia mediana: {sorted(all_diffs)[len(all_diffs)//2]:.1f}%")
            print(f"  Diferencia maxima: {max(all_diffs):.1f}%")
            print(f"  Diferencia minima: {min(all_diffs):.1f}%")
        print()

    # ======= SAME TEAMS DIFFERENT DATE =======
    if same_teams_matches:
        print("=" * 130)
        print(f"  COMPARACION INDIRECTA - Mismos equipos, otra jornada ({len(same_teams_matches)} partidos)")
        print("  NOTA: Las cuotas varian entre jornadas. Solo se compara coherencia de escala.")
        print("=" * 130)
        print()

        header = (f"  {'Partido':<45} {'F.Scr':<12} {'F.Excel':<12} "
                  f"{'Scr H':>7} {'BFE H':>7}  "
                  f"{'Scr D':>7} {'BFE D':>7}  "
                  f"{'Scr A':>7} {'BFE A':>7}")
        print(header)
        print("  " + "-" * 125)

        for m in same_teams_matches:
            s = m['scraper']
            r = m['excel_row']
            name = f"{m['excel_home']} vs {m['excel_away']}"
            scr_date = str(s['capture_date'].date()) if s['capture_date'] else '?'

            cols = []
            for bfe_col in ['BFEH', 'BFED', 'BFEA']:
                bfe_val = r.get(bfe_col)
                scr_val = s[f"back_{'home' if bfe_col == 'BFEH' else 'draw' if bfe_col == 'BFED' else 'away'}"]
                if pd.notna(bfe_val):
                    cols.append(f"{scr_val:>7.2f} {bfe_val:>7.2f}")
                else:
                    cols.append(f"{scr_val:>7.2f} {'N/A':>7}")

            print(f"  {name:<45} {scr_date:<12} {str(m['excel_date']):<12} {'  '.join(cols)}")

        print()

    # ======= NOT FOUND =======
    if not_found:
        print("=" * 130)
        print(f"  NO ENCONTRADOS ({len(not_found)} partidos)")
        print("  Probablemente ligas no cubiertas por el Excel (Sudamerica, Asia, etc.)")
        print("=" * 130)
        print()
        for nf in not_found:
            print(f"    - {nf['name']}")
        print()

    # ======= CONCLUSION =======
    print("=" * 130)
    print("  CONCLUSION")
    print("=" * 130)
    print()

    total_found = len(exact_date_matches) + len(same_teams_matches)
    print(f"  De {len(scraper_matches)} partidos con cuotas pre-match en el scraper:")
    print(f"    - {len(exact_date_matches)} encontrados con FECHA EXACTA en el Excel")
    print(f"    - {len(same_teams_matches)} encontrados pero en OTRA JORNADA")
    print(f"    - {len(not_found)} no encontrados (ligas no cubiertas)")
    print(f"    - Total encontrados: {total_found}/{len(scraper_matches)} ({total_found/len(scraper_matches)*100:.0f}%)")
    print()

    if exact_date_matches and all_diffs:
        avg = sum(all_diffs) / len(all_diffs)
        print(f"  Diferencia media en cuotas (partidos con fecha exacta): {avg:.1f}%")
        if avg < 5:
            print(f"  -> EXCELENTE: La diferencia es minima ({avg:.1f}%). Ambas fuentes son la misma (Betfair Exchange).")
            print(f"     La pequena diferencia se debe al momento de captura (apertura vs minutos antes del kickoff).")
        elif avg < 15:
            print(f"  -> BUENA: La diferencia es aceptable ({avg:.1f}%). Las fuentes son comparables.")
        else:
            print(f"  -> ALTA: La diferencia es significativa ({avg:.1f}%). Las fuentes pueden no ser comparables.")
    print()
    print("  RECOMENDACION: Usar la columna BFED del Excel como cuota pre-partido del empate")
    print("  para ampliar la muestra de la estrategia Back Empate 0-0.")
    print()


if __name__ == '__main__':
    main()
