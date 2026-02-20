"""
analyze_cashout_historico.py
============================
Analisis exhaustivo de cash-out para TODOS los partidos historicos del scraper.

Para cada partido con CSV disponible:
1. Re-detecta el trigger de cada estrategia (misma logica que el backend)
2. Obtiene back_odds exactas en el momento del trigger
3. Simula cash-out a cada captura posterior
4. Calcula el cash-out optimo (menor perdida / mayor ganancia garantizada)
5. Reporta patrones de score/minuto para reglas practicas

Cash-out formula:
  cashout_pl = stake * (back_odds / lay_odds_now - 1)
  recovery_pct = (cashout_pl + stake) / stake * 100
"""

import csv
import os
import re
import io
from collections import defaultdict
from pathlib import Path

# ─── CONFIGURACION ──────────────────────────────────────────────────────────

STAKE       = 10.0
DATA_DIR    = Path(r"c:\Users\agonz\OneDrive\Documents\Proyectos\Furbo\betfair_scraper\data")
PLACED_BETS = Path(r"c:\Users\agonz\OneDrive\Documents\Proyectos\Furbo\betfair_scraper\placed_bets.csv")

# Cartera historico Min DD (del analyze_multi_bet.py)
CARTERA_RAW = """\
match,match_id,strategy,won,pl
Corinthians Red Bull Bragantino,corinthians-red-bull-bragantino-apuestas-35207556,Momentum x xG V2,0,-10
Corinthians Red Bull Bragantino,corinthians-red-bull-bragantino-apuestas-35207556,xG Underperf,1,5.89
Corinthians Red Bull Bragantino,corinthians-red-bull-bragantino-apuestas-35207556,Odds Drift,1,7.13
Internacional Se Palmeiras,internacional-se-palmeiras-apuestas-35224753,Odds Drift,1,14.34
Spartak Varna Lokomotiv Sofia,spartak-varna-lokomotiv-sofia-apuestas-35239864,Goal Clustering,1,24.51
Anorthosis Digenis Ypsona,anorthosis-digenis-ypsona-apuestas-35247517,Back Empate,1,13.97
Galatasaray Eyupspor,galatasaray-eyupspor-apuestas-35243984,Odds Drift,1,8.45
Galatasaray Eyupspor,galatasaray-eyupspor-apuestas-35243984,Goal Clustering,1,2.47
Anorthosis Digenis Ypsona,anorthosis-digenis-ypsona-apuestas-35247517,Goal Clustering,1,3.23
Nuremberg Karlsruhe,nuremberg-karlsruhe-apuestas-35243488,Goal Clustering,1,5.13
Fortuna Dusseldorf Preussen Munster,fortuna-dusseldorf-preussen-munster-apuestas-35243,Back Empate,1,17.10
Nuremberg Karlsruhe,nuremberg-karlsruhe-apuestas-35243488,Odds Drift,1,39.81
Liverpool Montevideo Defensor Sp,liverpool-montevideo-defensor-sp-apuestas-35238332,Odds Drift,1,13.40
Liverpool Montevideo Defensor Sp,liverpool-montevideo-defensor-sp-apuestas-35238332,Goal Clustering,1,11.50
America De Cali Sa Santa Fe,america-de-cali-sa-santa-fe-apuestas-35238051,xG Underperf,0,-10
Braunschweig Darmstadt,braunschweig-darmstadt-apuestas-35243475,Back Empate,1,18.24
Braunschweig Darmstadt,braunschweig-darmstadt-apuestas-35243475,xG Underperf,1,7.03
Braunschweig Darmstadt,braunschweig-darmstadt-apuestas-35243475,Odds Drift,0,-10
Reading Wycombe,reading-wycombe-apuestas-35240945,xG Underperf,1,2.95
Reading Wycombe,reading-wycombe-apuestas-35240945,Goal Clustering,1,9.69
Hertha Berlin Hannover,hertha-berlin-hannover-apuestas-35243477,Goal Clustering,1,7.60
Cska 1948 Sofia,cska-1948-sofia-cska-sofia-apuestas-35239870,Back Empate,0,-10
Cska 1948 Sofia,cska-1948-sofia-cska-sofia-apuestas-35239870,Odds Drift,1,26.32
Espanyol Celta De Vigo,espanyol-celta-de-vigo-apuestas-35216696,Back Empate,1,13.78
Reading Wycombe,reading-wycombe-apuestas-35240945,Odds Drift,1,5.13
Espanyol Celta De Vigo,espanyol-celta-de-vigo-apuestas-35216696,Odds Drift,0,-10
Espanyol Celta De Vigo,espanyol-celta-de-vigo-apuestas-35216696,Goal Clustering,1,15.10
Eintracht Frankfurt Monchengladbach,eintracht-frankfurt-monchengladbach-apuesta,Goal Clustering,1,6.46
Eintracht Frankfurt Monchengladbach,eintracht-frankfurt-monchengladbach-apuesta,Odds Drift,1,16.72
Trabzonspor Fenerbahce,trabzonspor-fenerbahce-apuestas-35242066,Goal Clustering,1,6.27
Charleroi Gante,charleroi-gante-apuestas-35241421,Odds Drift,1,7.13
Charleroi Gante,charleroi-gante-apuestas-35241421,xG Underperf,1,3.23
Charleroi Gante,charleroi-gante-apuestas-35241421,Goal Clustering,1,17.67
Fc Groningen Utrecht,fc-groningen-utrecht-apuestas-35216585,Tarde Asia,1,10.07
Fc Groningen Utrecht,fc-groningen-utrecht-apuestas-35216585,Momentum x xG V2,1,24.03
Real Madrid Real Sociedad,real-madrid-real-sociedad-apuestas-35216679,Goal Clustering,1,35.15
Paris Fc Lens,paris-fc-lens-apuestas-35216501,Odds Drift,1,8.17
Fc Groningen Utrecht,fc-groningen-utrecht-apuestas-35216585,xG Underperf,1,3.99
Liverpool Brighton,liverpool-brighton-apuestas-35172770,xG Underperf,1,2.28
Paris Fc Lens,paris-fc-lens-apuestas-35216501,Goal Clustering,0,-10
Kocaelispor Gaziantep Fk,kocaelispor-gaziantep-fk-apuestas-35248519,Odds Drift,1,6.74
Fc Magdeburg Arminia Bielefeld,fc-magdeburg-arminia-bielefeld-apuestas-35243485,xG Underperf,1,3.99
Thun Sion,thun-sion-apuestas-35258535,Momentum x xG V2,1,6.84
Thun Sion,thun-sion-apuestas-35258535,Back Empate,0,-10
Mirandes Las Palmas,mirandes-las-palmas-apuestas-35247639,Momentum x xG V2,0,-10
Thun Sion,thun-sion-apuestas-35258535,Goal Clustering,0,-10
Grimsby Wolves,grimsby-wolves-apuestas-35172760,Back Empate,0,-10
Mirandes Las Palmas,mirandes-las-palmas-apuestas-35247639,xG Underperf,0,-10
Oviedo Athletic De Bilbao,oviedo-athletic-de-bilbao-apuestas-35216603,Odds Drift,0,-10
Oviedo Athletic De Bilbao,oviedo-athletic-de-bilbao-apuestas-35216603,Goal Clustering,1,12.45
Thun Sion,thun-sion-apuestas-35258535,Odds Drift,1,13.59
Amberes Westerlo,amberes-westerlo-apuestas-35245449,Momentum x xG V2,1,13.21
Amberes Westerlo,amberes-westerlo-apuestas-35245449,Odds Drift,1,7.03
Pfc Levski Sofia Botev Plovdiv,pfc-levski-sofia-botev-plovdiv-apuestas-35243302,Goal Clustering,1,1.80
Amberes Westerlo,amberes-westerlo-apuestas-35245449,Goal Clustering,0,-10
Esporte Clube Primavera Noroeste Bauru,esporte-clube-primavera-noroeste-bauru,xG Underperf,1,3.33
Ponte Preta Sao Paulo,ponte-preta-sao-paulo-apuestas-35245206,Momentum x xG V2,1,2.76
Santos Velo Clube Sp,santos-velo-clube-sp-apuestas-35245257,Odds Drift,1,28.69
Red Bull Bragantino Novorizontino,red-bull-bragantino-novorizontino-apuestas-3524529,Momentum x xG V2,1,5.98
Colo Colo Union La Calera,colo-colo-union-la-calera-apuestas-35244756,Back Empate,1,22.61
Red Bull Bragantino Novorizontino,red-bull-bragantino-novorizontino-apuestas-3524529,Odds Drift,1,12.83
Colo Colo Union La Calera,colo-colo-union-la-calera-apuestas-35244756,Momentum x xG V2,0,-10
Ponte Preta Sao Paulo,ponte-preta-sao-paulo-apuestas-35245206,Goal Clustering,1,13.97
Ponte Preta Sao Paulo,ponte-preta-sao-paulo-apuestas-35245206,Odds Drift,1,14.34
Botafogo Sp Capivariano Sp,botafogo-sp-capivariano-sp-apuestas-35245279,Momentum x xG V2,0,-10
Al Sharjah Nasaf,al-sharjah-nasaf-apuestas-35269093,Tarde Asia,1,9.69
Al Sharjah Nasaf,al-sharjah-nasaf-apuestas-35269093,Odds Drift,1,11.02
Atromitos Panserraikos,atromitos-panserraikos-apuestas-35216936,Momentum x xG V2,1,6.74
Nk Bravo Nk Aluminij,nk-bravo-nk-aluminij-apuestas-35247855,Goal Clustering,1,2.57
Kasimpasa Fatih Karagumruk Istanbul,kasimpasa-fatih-karagumruk-istanbul-apuestas-35248,Momentum x xG V2,1,10.07
Al Sharjah Nasaf,al-sharjah-nasaf-apuestas-35269093,xG Underperf,1,5.13
Nk Bravo Nk Aluminij,nk-bravo-nk-aluminij-apuestas-35247855,Pressure Cooker,1,4.37
Al Hilal Al Wahda Abu Dhabi,al-hilal-al-wahda-abu-dhabi-apuestas-35269089,Tarde Asia,1,1.52
Kasimpasa Fatih Karagumruk Istanbul,kasimpasa-fatih-karagumruk-istanbul-apuestas-35248,Odds Drift,1,21.66
Kasimpasa Fatih Karagumruk Istanbul,kasimpasa-fatih-karagumruk-istanbul-apuestas-35248,Goal Clustering,1,28.69
Cagliari Lecce,cagliari-lecce-apuestas-35216885,Momentum x xG V2,1,27.27
Cagliari Lecce,cagliari-lecce-apuestas-35216885,Back Empate,0,-10
Rio Ave Moreirense,rio-ave-moreirense-apuestas-35247028,Odds Drift,1,13.02
Rio Ave Moreirense,rio-ave-moreirense-apuestas-35247028,xG Underperf,1,2.09
Sociedad B Malaga,sociedad-b-malaga-apuestas-35248844,Pressure Cooker,1,5.80
Rio Ave Moreirense,rio-ave-moreirense-apuestas-35247028,Goal Clustering,1,2.09
Sociedad B Malaga,sociedad-b-malaga-apuestas-35248844,Goal Clustering,0,-10
Cagliari Lecce,cagliari-lecce-apuestas-35216885,Odds Drift,1,33.34
Coventry Middlesbrough,coventry-middlesbrough-apuestas-35239500,xG Underperf,1,6.84
Cagliari Lecce,cagliari-lecce-apuestas-35216885,xG Underperf,1,9.50
Coventry Middlesbrough,coventry-middlesbrough-apuestas-35239500,Odds Drift,1,18.05
Girona Fc Barcelona,girona-fc-barcelona-apuestas-35216932,xG Underperf,0,-10
Al Sadd Al Ittihad,al-sadd-al-ittihad-apuestas-35273530,Tarde Asia,1,4.75
Al Sadd Al Ittihad,al-sadd-al-ittihad-apuestas-35273530,Goal Clustering,1,12.45
Al Gharafa Tractor Sazi Fc,al-gharafa-tractor-sazi-fc-apuestas-35277632,Odds Drift,1,18.91
Al Sadd Al Ittihad,al-sadd-al-ittihad-apuestas-35273530,Momentum x xG V2,0,-10
Galatasaray Juventus,galatasaray-juventus-apuestas-35207338,Odds Drift,0,-10
Galatasaray Juventus,galatasaray-juventus-apuestas-35207338,Odds Drift,1,21.66
Al Hussein Sc Esteghlal Fc,al-hussein-sc-esteghlal-fc-apuestas-35277998,Odds Drift,0,-10
Tranmere Accrington,tranmere-accrington-apuestas-35263115,Momentum x xG V2,1,14.53
Lincoln Northampton,lincoln-northampton-apuestas-35268034,Momentum x xG V2,1,3.61
Shrewsbury Notts County,shrewsbury-notts-county-apuestas-35262993,Momentum x xG V2,0,-10
Monaco Psg,monaco-psg-apuestas-35207322,Tarde Asia,1,3.61
Stevenage Port Vale,stevenage-port-vale-apuestas-35266044,Odds Drift,0,-10
Barnsley Peterborough,barnsley-peterborough-apuestas-35268021,Momentum x xG V2,0,-10
Reading Bolton,reading-bolton-apuestas-35268029,Momentum x xG V2,0,-10
Barnsley Peterborough,barnsley-peterborough-apuestas-35268021,Odds Drift,0,-10
Bristol City Wrexham,bristol-city-wrexham-apuestas-35253015,Back Empate,0,-10
Doncaster Huddersfield,doncaster-huddersfield-apuestas-35266039,Back Empate,0,-10
Charlton Portsmouth,charlton-portsmouth-apuestas-35239489,Odds Drift,1,33.34
Stevenage Port Vale,stevenage-port-vale-apuestas-35266044,Odds Drift,1,6.55
Monaco Psg,monaco-psg-apuestas-35207322,Goal Clustering,1,4.46
Reading Bolton,reading-bolton-apuestas-35268029,xG Underperf,0,-10
Tranmere Accrington,tranmere-accrington-apuestas-35263115,Goal Clustering,0,-10
Exeter Wycombe,exeter-wycombe-apuestas-35268035,xG Underperf,0,-10
Bradford Stockport,bradford-stockport-apuestas-35268022,Odds Drift,1,21.19
Tranmere Accrington,tranmere-accrington-apuestas-35263115,Odds Drift,1,5.23
Bradford Stockport,bradford-stockport-apuestas-35268022,Goal Clustering,0,-10
Bristol City Wrexham,bristol-city-wrexham-apuestas-35253015,Goal Clustering,1,3.33
Lincoln Northampton,lincoln-northampton-apuestas-35268034,Goal Clustering,1,2.18
Shrewsbury Notts County,shrewsbury-notts-county-apuestas-35262993,xG Underperf,0,-10
Charlton Portsmouth,charlton-portsmouth-apuestas-35239489,Goal Clustering,1,3.99
Oldham Bristol Rovers,oldham-bristol-rovers-apuestas-35263000,Goal Clustering,0,-10
Chesterfield Gillingham,chesterfield-gillingham-apuestas-35263011,Momentum x xG V2,1,2.57
Cardiff Afc Wimbledon,cardiff-afc-wimbledon-apuestas-35268015,Odds Drift,1,18.05
Bromley Cheltenham,bromley-cheltenham-apuestas-35263015,Pressure Cooker,0,-10
Chesterfield Gillingham,chesterfield-gillingham-apuestas-35263011,xG Underperf,0,-10
Burton Albion Rotherham,burton-albion-rotherham-apuestas-35253017,xG Underperf,0,-10
Bromley Cheltenham,bromley-cheltenham-apuestas-35263015,Momentum x xG V2,0,-10
"""

# ─── HELPERS ────────────────────────────────────────────────────────────────

def flt(v):
    if not v or str(v).strip() in ("", "N/A", "None"): return None
    try: return float(v)
    except: return None

def resolve_partido(match_id):
    direct = DATA_DIR / f"partido_{match_id}.csv"
    if direct.exists(): return direct
    # Fuzzy: strip trailing digits and try wildcard
    prefix = re.sub(r"-?\d+$", "", match_id)
    if prefix:
        matches = list(DATA_DIR.glob(f"partido_{prefix}*.csv"))
        if matches: return matches[0]
    return None

def read_rows(path):
    with open(path, encoding="utf-8", errors="replace") as f:
        return list(csv.DictReader(f))

COMMISSION = 0.05  # Betfair standard 5%

def cashout_pl(back_odds, lay_odds, stake=STAKE):
    """
    Guaranteed P&L when closing a back position with a lay.
    Hedge: lay_stake = stake * back_odds / lay_odds
    Pre-commission: stake * (back_odds / lay_odds - 1)
    Betfair charges 5% commission ONLY on net profits (not on losses).
    """
    gross = stake * (back_odds / lay_odds - 1)
    if gross > 0:
        return round(gross * (1 - COMMISSION), 2)
    return round(gross, 2)

def recovery_pct(co_pl, stake=STAKE):
    return round((co_pl + stake) / stake * 100, 1)

def over_cols(n_goals):
    """Return (back_col, lay_col) for Over n_goals + 0.5"""
    line = n_goals + 0.5
    if line <= 0.5:   return "back_over05",  "lay_over05"
    if line <= 1.5:   return "back_over15",  "lay_over15"
    if line <= 2.5:   return "back_over25",  "lay_over25"
    if line <= 3.5:   return "back_over35",  "lay_over35"
    if line <= 4.5:   return "back_over45",  "lay_over45"
    return None, None

# ─── TRIGGER DETECTION ─────────────────────────────────────────────────────

def detect_back_draw(rows):
    """First row: 0-0, min >= 30, back_draw available."""
    for row in rows:
        if row.get("estado_partido") != "en_juego": continue
        m = flt(row.get("minuto"))
        if m is None or m < 30: continue
        gl = flt(row.get("goles_local")); gv = flt(row.get("goles_visitante"))
        if gl != 0 or gv != 0: continue
        odds = flt(row.get("back_draw"))
        if odds and 1.3 <= odds <= 4.0:
            return row, "draw", "back_draw", "lay_draw", odds, m
    return None

def detect_xg_underperf(rows):
    """First row where losing team has xG - goals >= 0.5. Bet Over (goals + 0.5)."""
    for row in rows:
        if row.get("estado_partido") != "en_juego": continue
        m = flt(row.get("minuto"))
        if m is None or m < 35 or m > 80: continue
        gl = flt(row.get("goles_local")); gv = flt(row.get("goles_visitante"))
        xg_l = flt(row.get("xg_local")); xg_v = flt(row.get("xg_visitante"))
        if None in [gl, gv, xg_l, xg_v]: continue
        total = int(gl) + int(gv)
        back_col, lay_col = over_cols(total)
        if not back_col: continue
        # Check which losing team underperforms
        underperf = False
        if gl < gv and (xg_l - gl) >= 0.5: underperf = True   # local losing, underperforming
        if gv < gl and (xg_v - gv) >= 0.5: underperf = True   # away losing, underperforming
        if not underperf: continue
        odds = flt(row.get(back_col))
        if odds and 1.2 <= odds <= 5.0:
            return row, f"over{total+1}h", back_col, lay_col, odds, m
    return None

def detect_goal_clustering(rows):
    """First new goal in min 15-80 where some team has SoT >= 3. Bet Over (goals + 0.5)."""
    prev_total = 0
    for row in rows:
        if row.get("estado_partido") != "en_juego": continue
        m = flt(row.get("minuto"))
        if m is None or m < 15 or m > 80: continue
        gl = flt(row.get("goles_local")); gv = flt(row.get("goles_visitante"))
        sot_l = flt(row.get("tiros_puerta_local")); sot_v = flt(row.get("tiros_puerta_visitante"))
        if None in [gl, gv]: continue
        total = int(gl) + int(gv)
        # New goal just scored?
        if total > prev_total:
            prev_total = total
            sot_max = max(sot_l or 0, sot_v or 0)
            if sot_max >= 3:
                back_col, lay_col = over_cols(total)
                if not back_col: continue
                odds = flt(row.get(back_col))
                if odds and 1.1 <= odds <= 6.0:
                    return row, f"over{total+1}h", back_col, lay_col, odds, m
        else:
            prev_total = max(prev_total, total)
    return None

def detect_pressure_cooker(rows):
    """First draw with goals (1-1+) in min 65-75. Bet Over (goals + 0.5)."""
    for row in rows:
        if row.get("estado_partido") != "en_juego": continue
        m = flt(row.get("minuto"))
        if m is None or m < 65 or m > 75: continue
        gl = flt(row.get("goles_local")); gv = flt(row.get("goles_visitante"))
        if None in [gl, gv]: continue
        if gl != gv or (gl == 0 and gv == 0): continue
        total = int(gl) + int(gv)
        back_col, lay_col = over_cols(total)
        if not back_col: continue
        odds = flt(row.get(back_col))
        if odds and 1.1 <= odds <= 4.0:
            return row, f"over{total+1}h", back_col, lay_col, odds, m
    return None

def detect_tarde_asia(rows):
    """Back Over 2.5 (simplified trigger: any point before min 60 with back_over25 available)."""
    for row in rows:
        if row.get("estado_partido") != "en_juego": continue
        m = flt(row.get("minuto"))
        if m is None or m > 60: continue
        gl = flt(row.get("goles_local")); gv = flt(row.get("goles_visitante"))
        if None in [gl, gv]: continue
        if int(gl) + int(gv) >= 3: continue  # Over 2.5 already settled
        odds = flt(row.get("back_over25"))
        if odds and 1.3 <= odds <= 4.0:
            return row, "over25", "back_over25", "lay_over25", odds, m
    return None

def detect_odds_drift(rows):
    """Team winning + odds drifted >30% within last ~10 min. Back that team."""
    window = []
    for row in rows:
        if row.get("estado_partido") != "en_juego": continue
        m = flt(row.get("minuto"))
        if m is None: continue
        gl = flt(row.get("goles_local")); gv = flt(row.get("goles_visitante"))
        bh = flt(row.get("back_home")); ba = flt(row.get("back_away"))
        if None in [gl, gv, bh, ba]: continue
        window.append((m, int(gl), int(gv), bh, ba, row))
        # Keep only last ~10 min window
        window = [(wm, wgl, wgv, wbh, wba, wr) for wm, wgl, wgv, wbh, wba, wr in window if m - wm <= 10]
        if len(window) < 2: continue
        first = window[0]
        # Check home drift (home losing? winning? - odds drifted means odds went UP while team winning)
        drift_home = (bh - first[3]) / first[3] if first[3] > 0 else 0
        drift_away = (ba - first[4]) / first[4] if first[4] > 0 else 0
        gl_now = int(gl); gv_now = int(gv)
        # Home winning + home odds drifting up (market mispricing)
        if gl_now > gv_now and drift_home >= 0.30 and 1.2 <= bh <= 6.0:
            return row, "home", "back_home", "lay_home", bh, m
        # Away winning + away odds drifting up
        if gv_now > gl_now and drift_away >= 0.30 and 1.2 <= ba <= 6.0:
            return row, "away", "back_away", "lay_away", ba, m
    return None

def detect_momentum_xg_v2(rows):
    """Dominant team (SoT ratio >= 1.05, xG underperf > 0.1) in min 5-85. Back dominant team."""
    for row in rows:
        if row.get("estado_partido") != "en_juego": continue
        m = flt(row.get("minuto"))
        if m is None or m < 5 or m > 85: continue
        gl = flt(row.get("goles_local")); gv = flt(row.get("goles_visitante"))
        xg_l = flt(row.get("xg_local")); xg_v = flt(row.get("xg_visitante"))
        sot_l = flt(row.get("tiros_puerta_local")); sot_v = flt(row.get("tiros_puerta_visitante"))
        bh = flt(row.get("back_home")); ba = flt(row.get("back_away"))
        if None in [gl, gv, xg_l, xg_v, sot_l, sot_v, bh, ba]: continue
        xg_up_l = xg_l - gl
        xg_up_v = xg_v - gv
        ratio_l = sot_l / sot_v if sot_v > 0 else (sot_l * 2 if sot_l >= 1 else 0)
        ratio_v = sot_v / sot_l if sot_l > 0 else (sot_v * 2 if sot_v >= 1 else 0)
        # Home dominant
        if sot_l >= 1 and ratio_l >= 1.05 and xg_up_l > 0.1 and 1.3 <= bh <= 8.0:
            return row, "home", "back_home", "lay_home", bh, m
        # Away dominant
        if sot_v >= 1 and ratio_v >= 1.05 and xg_up_v > 0.1 and 1.3 <= ba <= 8.0:
            return row, "away", "back_away", "lay_away", ba, m
    return None

STRATEGY_DETECTORS = {
    "Back Empate":       detect_back_draw,
    "xG Underperf":      detect_xg_underperf,
    "Goal Clustering":   detect_goal_clustering,
    "Pressure Cooker":   detect_pressure_cooker,
    "Tarde Asia":        detect_tarde_asia,
    "Odds Drift":        detect_odds_drift,
    "Momentum x xG V2":  detect_momentum_xg_v2,
}

# ─── SIMULATION ────────────────────────────────────────────────────────────

def is_corrupted_row(row, back_col, lay_col):
    """
    Detect rows captured during Betfair market suspension (goal events).
    Signs: lay < back (inverted spread), or spread > 50% of back price (absurd).
    """
    bk = flt(row.get(back_col))
    ly = flt(row.get(lay_col))
    if bk is None or ly is None or bk <= 1.0 or ly <= 1.0:
        return True
    if ly < bk:           # inverted: lay should always be >= back
        return True
    spread_pct = (ly - bk) / bk
    if spread_pct > 0.5:  # spread > 50% = market in suspension/reopening
        return True
    return False

def simulate_cashout(rows, trigger_minute, back_col, lay_col, back_odds):
    """For each row after trigger, compute cash-out value (net of 5% commission)."""
    series = []
    for row in rows:
        m = flt(row.get("minuto"))
        if m is None or m <= trigger_minute: continue
        if is_corrupted_row(row, back_col, lay_col):
            continue
        lay = flt(row.get(lay_col))
        if not lay or lay <= 1.01: continue
        gl = flt(row.get("goles_local")) or 0
        gv = flt(row.get("goles_visitante")) or 0
        co = cashout_pl(back_odds, lay)
        series.append({
            "minute":     m,
            "score":      f"{int(gl)}-{int(gv)}",
            "lay_odds":   lay,
            "cashout_pl": co,
            "recovery":   recovery_pct(co),
        })
    return series

# ─── MAIN ──────────────────────────────────────────────────────────────────

def main():
    # Parse cartera bets
    cartera = list(csv.DictReader(io.StringIO(CARTERA_RAW)))
    cartera = [r for r in cartera if r.get("match_id") and r["match_id"] != "match_id"]

    # Index by match_id
    by_match = defaultdict(list)
    for r in cartera:
        by_match[r["match_id"].strip()].append(r)

    # Results buckets
    results_losing  = []  # losing bets analyzed
    results_winning = []  # winning bets analyzed (for comparison)
    skipped = []

    total_matched = 0
    total_with_trigger = 0

    for match_id, bets in by_match.items():
        path = resolve_partido(match_id)
        if not path:
            skipped.append((match_id, "no partido CSV"))
            continue

        rows = read_rows(path)
        if len(rows) < 20:
            skipped.append((match_id, "too few rows"))
            continue

        # Check match finished (min >= 85)
        last_min = flt(rows[-1].get("minuto"))
        if last_min is None or last_min < 50:
            skipped.append((match_id, f"match not finished (last min={last_min})"))
            continue

        total_matched += 1
        match_name = bets[0]["match"].strip()

        for bet in bets:
            strategy = bet["strategy"].strip()
            won      = int(bet["won"])
            pl_real  = float(bet["pl"])

            detector = STRATEGY_DETECTORS.get(strategy)
            if detector is None:
                skipped.append((match_id, f"no detector for {strategy}"))
                continue

            result = detector(rows)
            if result is None:
                skipped.append((match_id, f"no trigger found for {strategy}"))
                continue

            total_with_trigger += 1
            trig_row, market, back_col, lay_col, back_odds, trigger_minute = result

            series = simulate_cashout(rows, trigger_minute, back_col, lay_col, back_odds)
            if not series:
                skipped.append((match_id, f"no post-trigger data for {strategy}"))
                continue

            best_co  = max(series, key=lambda x: x["cashout_pl"])
            mid70    = min(series, key=lambda x: abs(x["minute"] - 70))
            last_co  = series[-1]

            # Milestone every ~10 min
            milestones = {}
            for pt in series:
                bucket = int(pt["minute"] // 10) * 10
                if bucket not in milestones: milestones[bucket] = pt

            entry = {
                "match_name":    match_name,
                "match_id":      match_id,
                "strategy":      strategy,
                "market":        market,
                "back_odds":     back_odds,
                "trigger_min":   trigger_minute,
                "won":           won,
                "pl_real":       pl_real,
                "best_co":       best_co,
                "mid70_co":      mid70,
                "last_co":       last_co,
                "milestones":    milestones,
                "series":        series,
            }

            if won == 0:
                results_losing.append(entry)
            else:
                results_winning.append(entry)

    # ── OUTPUT ──────────────────────────────────────────────────────────────

    sep = "=" * 88
    print(sep)
    print(f"ANALISIS CASH-OUT HISTORICO")
    print(f"Partidos en cartera: {len(by_match)} | Con CSV: {total_matched} | Con trigger: {total_with_trigger}")
    print(f"Bets perdedoras analizadas: {len(results_losing)} | Ganadas: {len(results_winning)}")
    print(sep)

    # ── Section 1: LOSING BETS - detailed cashout scenarios ─────────────────
    print(f"\n{'='*88}")
    print("SECCION 1: APUESTAS PERDEDORAS - Evolucion de cash-out")
    print(f"{'='*88}\n")

    total_real_loss  = 0.0
    total_best_co    = 0.0
    total_mid70_co   = 0.0
    total_early_co   = 0.0  # ~5 min after trigger

    for r in results_losing:
        total_real_loss += r["pl_real"]
        total_best_co   += r["best_co"]["cashout_pl"]
        total_mid70_co  += r["mid70_co"]["cashout_pl"]
        # Early = first available milestone after trigger
        early = r["series"][0] if r["series"] else r["best_co"]
        total_early_co  += early["cashout_pl"]

        b = r["best_co"]; m70 = r["mid70_co"]
        print(f"{r['match_name'][:35]:<35} [{r['strategy'][:18]:<18}] @{r['back_odds']:<5} min{r['trigger_min']:.0f}")
        print(f"  Real: {r['pl_real']:+.2f}EUR  |  Mejor CO: min{b['minute']:.0f} ({b['score']}) lay={b['lay_odds']} -> {b['cashout_pl']:+.2f}EUR ({b['recovery']}%)  |  CO@70: {m70['cashout_pl']:+.2f}EUR ({m70['recovery']}%)")
        if r["milestones"]:
            timeline = "  Linea: " + "  ".join(
                f"m{bkt}[{pt['score']}]={pt['cashout_pl']:+.1f}({pt['recovery']}%)"
                for bkt, pt in sorted(r["milestones"].items())
            )
            print(timeline)
        print()

    n_l = len(results_losing)
    if n_l > 0:
        print(f"{'─'*88}")
        print(f"RESUMEN APUESTAS PERDEDORAS ({n_l} bets, stake total {n_l*STAKE:.0f}EUR)")
        print(f"  Perdida real (sin CO):        {total_real_loss:+.2f}EUR  (avg {total_real_loss/n_l:+.2f}EUR/bet)")
        print(f"  CO optimo (hindsight):        {total_best_co:+.2f}EUR  (avg {total_best_co/n_l:+.2f}EUR/bet)")
        print(f"  CO aprox min 70:              {total_mid70_co:+.2f}EUR  (avg {total_mid70_co/n_l:+.2f}EUR/bet)")
        print(f"  CO inmediato (1er captura):   {total_early_co:+.2f}EUR  (avg {total_early_co/n_l:+.2f}EUR/bet)")
        savings_70   = total_mid70_co  - total_real_loss
        savings_best = total_best_co   - total_real_loss
        savings_early= total_early_co  - total_real_loss
        print(f"  Ahorro CO optimo vs sin CO:   {savings_best:+.2f}EUR  ({savings_best/abs(total_real_loss)*100:.1f}%)")
        print(f"  Ahorro CO min70 vs sin CO:    {savings_70:+.2f}EUR  ({savings_70/abs(total_real_loss)*100:.1f}%)")
        print(f"  Ahorro CO inmediato vs sin CO:{savings_early:+.2f}EUR  ({savings_early/abs(total_real_loss)*100:.1f}%)")

    # ── Section 2: PATTERNS - when is cash-out worth it? ────────────────────
    print(f"\n{'='*88}")
    print("SECCION 2: PATRONES - Por estrategia y score")
    print(f"{'='*88}\n")

    # By strategy
    by_strat = defaultdict(lambda: {"losing": [], "winning": []})
    for r in results_losing:  by_strat[r["strategy"]]["losing"].append(r)
    for r in results_winning: by_strat[r["strategy"]]["winning"].append(r)

    print(f"{'ESTRATEGIA':<22} {'PERDIDAS':>8} {'GANADAS':>8} {'CO_OPTI_AVG':>12} {'CO_70_AVG':>10} {'MIN_OPTIMO':>10}")
    print(f"{'─'*22} {'─'*8} {'─'*8} {'─'*12} {'─'*10} {'─'*10}")
    for strat, grp in sorted(by_strat.items()):
        ls = grp["losing"]; ws = grp["winning"]
        if not ls: continue
        avg_best = sum(r["best_co"]["cashout_pl"] for r in ls) / len(ls)
        avg_70   = sum(r["mid70_co"]["cashout_pl"] for r in ls) / len(ls)
        avg_min  = sum(r["best_co"]["minute"] for r in ls) / len(ls)
        print(f"{strat[:22]:<22} {len(ls):>8} {len(ws):>8} {avg_best:>+12.2f} {avg_70:>+10.2f} {avg_min:>10.1f}")

    # By score at optimal cash-out
    print(f"\n-- Score al cash-out optimo (perdidas) --")
    score_groups = defaultdict(list)
    for r in results_losing:
        score_groups[r["best_co"]["score"]].append(r["best_co"]["cashout_pl"])
    for score, vals in sorted(score_groups.items(), key=lambda x: -len(x[1])):
        avg = sum(vals)/len(vals)
        print(f"  {score:<7}: {len(vals):>3} casos | CO promedio {avg:+.2f}EUR | recuperacion {recovery_pct(avg):.1f}%")

    # By trigger minute bucket
    print(f"\n-- Distribucion de minuto del trigger --")
    min_buckets = defaultdict(int)
    for r in results_losing:
        bucket = int(r["trigger_min"] // 10) * 10
        min_buckets[bucket] += 1
    for bkt in sorted(min_buckets):
        print(f"  min {bkt:2}-{bkt+9:2}: {min_buckets[bkt]} bets perdedoras")

    # ── Section 3: REGLAS PRACTICAS ─────────────────────────────────────────
    print(f"\n{'='*88}")
    print("SECCION 3: REGLAS PRACTICAS DERIVADAS")
    print(f"{'='*88}\n")

    # What recovery % is available at min 60 for each bet?
    min60_recoveries = []
    for r in results_losing:
        pt60 = min(r["series"], key=lambda x: abs(x["minute"] - 60)) if r["series"] else None
        if pt60: min60_recoveries.append(pt60["recovery"])

    if min60_recoveries:
        avg60 = sum(min60_recoveries) / len(min60_recoveries)
        above80 = sum(1 for v in min60_recoveries if v >= 80)
        above50 = sum(1 for v in min60_recoveries if v >= 50)
        print(f"Cash-out en min ~60 (apuestas perdedoras):")
        print(f"  Recuperacion promedio: {avg60:.1f}%")
        print(f"  % con recuperacion >= 80%: {above80}/{len(min60_recoveries)} ({above80/len(min60_recoveries)*100:.0f}%)")
        print(f"  % con recuperacion >= 50%: {above50}/{len(min60_recoveries)} ({above50/len(min60_recoveries)*100:.0f}%)")

    # Win vs loss comparison at min 70
    print(f"\nComparacion ganadas vs perdidas al cash-out min ~70:")
    winning_at70 = []
    for r in results_winning:
        pt = min(r["series"], key=lambda x: abs(x["minute"] - 70)) if r["series"] else None
        if pt: winning_at70.append(pt["cashout_pl"])
    losing_at70 = [r["mid70_co"]["cashout_pl"] for r in results_losing]
    if winning_at70 and losing_at70:
        print(f"  Ganadas: {len(winning_at70)} bets, CO@70 promedio = {sum(winning_at70)/len(winning_at70):+.2f}EUR (lock-in profit)")
        print(f"  Perdidas: {len(losing_at70)} bets, CO@70 promedio = {sum(losing_at70)/len(losing_at70):+.2f}EUR (partial loss)")

    # ── Section 4: SKIPPED ─────────────────────────────────────────────────
    print(f"\n{'='*88}")
    print(f"SECCION 4: NO ANALIZADOS ({len(skipped)} casos)")
    print(f"{'='*88}")
    skip_reasons = defaultdict(int)
    for _, reason in skipped:
        short = reason.split(" (")[0][:40]
        skip_reasons[short] += 1
    for reason, count in sorted(skip_reasons.items(), key=lambda x: -x[1]):
        print(f"  {reason}: {count}")

if __name__ == "__main__":
    main()