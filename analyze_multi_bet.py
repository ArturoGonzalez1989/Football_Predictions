#!/usr/bin/env python3
"""
Analisis de rendimiento por numero de apuestas simultaneas en el mismo partido.
Usa el CSV exportado desde la cartera Min DD.
"""
import csv, io
from collections import defaultdict

RAW = """\
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
Monaco Psg,monaco-psg-apuestas-35207322,Odds Drift,1,18.24
"""

def main():
    rows = list(csv.DictReader(io.StringIO(RAW)))

    print(f"Total apuestas: {len(rows)}")

    # Agrupar por partido
    matches = defaultdict(list)
    for r in rows:
        mid = r["match_id"].strip()
        matches[mid].append(r)

    print(f"Partidos únicos: {len(matches)}")

    # Análisis por grupo de apuestas
    by_count = defaultdict(lambda: {"matches": [], "pl_total": 0.0, "stake": 0.0,
                                     "bet_wins": 0, "bet_total": 0, "match_wins": 0})

    for mid, bets in matches.items():
        n = len(bets)
        pl = sum(float(b["pl"]) for b in bets)
        wins = sum(1 for b in bets if int(b["won"]) == 1)
        stake = n * 10.0
        bucket = n if n <= 4 else "5+"
        by_count[bucket]["matches"].append({"mid": mid, "pl": pl, "n": n, "wins": wins, "bets": bets})
        by_count[bucket]["pl_total"] += pl
        by_count[bucket]["stake"] += stake
        by_count[bucket]["bet_wins"] += wins
        by_count[bucket]["bet_total"] += n
        if pl > 0:
            by_count[bucket]["match_wins"] += 1

    print("\n" + "="*70)
    print("RENDIMIENTO POR Nº DE APUESTAS POR PARTIDO")
    print("="*70)
    print(f"  {'N bets':>7}  {'Partidos':>9}  {'Match WR':>9}  {'Bet WR':>8}  {'P&L':>9}  {'Stake':>7}  {'ROI':>8}")
    print(f"  {'-'*65}")

    for k in sorted(by_count.keys(), key=lambda x: int(x) if str(x).isdigit() else 99):
        d = by_count[k]
        nm = len(d["matches"])
        mwr = d["match_wins"] / nm * 100
        bwr = d["bet_wins"] / d["bet_total"] * 100
        roi = d["pl_total"] / d["stake"] * 100
        print(f"  {str(k)+' apuesta/s':>9}  {nm:>9}  {mwr:>8.1f}%  {bwr:>7.1f}%  {d['pl_total']:>+9.2f}  {d['stake']:>7.0f}  {roi:>+7.1f}%")

    # Total
    all_pl = sum(d["pl_total"] for d in by_count.values())
    all_stake = sum(d["stake"] for d in by_count.values())
    all_bets = sum(d["bet_total"] for d in by_count.values())
    all_bet_wins = sum(d["bet_wins"] for d in by_count.values())
    all_nm = sum(len(d["matches"]) for d in by_count.values())
    all_mw = sum(d["match_wins"] for d in by_count.values())
    print(f"  {'':9}  {'─'*55}")
    print(f"  {'TOTAL':>9}  {all_nm:>9}  {all_mw/all_nm*100:>8.1f}%  {all_bet_wins/all_bets*100:>7.1f}%  {all_pl:>+9.2f}  {all_stake:>7.0f}  {all_pl/all_stake*100:>+7.1f}%")

    # Detalle combinaciones de estrategias en partidos con 2 apuestas
    print("\n" + "="*70)
    print("PARES DE ESTRATEGIAS (partidos con exactamente 2 apuestas)")
    print("="*70)

    pairs = defaultdict(lambda: {"pl": 0.0, "stake": 0.0, "wins": 0, "n": 0})
    for mid, bets in matches.items():
        if len(bets) != 2:
            continue
        s1, s2 = sorted(b["strategy"].strip() for b in bets)
        pair_key = f"{s1} + {s2}"
        match_pl = sum(float(b["pl"]) for b in bets)
        pairs[pair_key]["pl"] += match_pl
        pairs[pair_key]["stake"] += 20.0
        pairs[pair_key]["n"] += 1
        if match_pl > 0:
            pairs[pair_key]["wins"] += 1

    pairs_sorted = sorted(pairs.items(), key=lambda x: x[1]["pl"] / x[1]["stake"], reverse=True)
    print(f"  {'Par':45}  {'N':>3}  {'WR%':>6}  {'ROI':>8}  {'P&L':>8}")
    print(f"  {'-'*70}")
    for name, d in pairs_sorted:
        roi = d["pl"] / d["stake"] * 100
        wr = d["wins"] / d["n"] * 100
        print(f"  {name:45}  {d['n']:>3}  {wr:>5.0f}%  {roi:>+7.1f}%  {d['pl']:>+8.2f}")

    # Pares problemáticos (todos pierden)
    print("\n" + "="*70)
    print("ANÁLISIS: ¿QUÉ PARES TIENEN WR=0%?")
    print("="*70)
    for name, d in pairs_sorted:
        if d["wins"] == 0:
            print(f"  ⚠  {name}  → {d['n']} partidos, -€{abs(d['pl']):.2f} (-100% ROI)")

    # Los 5 peores partidos multi-apuesta
    print("\n" + "="*70)
    print("TOP 5 PARTIDOS MULTI-APUESTA POR PÉRDIDA")
    print("="*70)
    multi = [(mid, bets) for mid, bets in matches.items() if len(bets) > 1]
    multi_sorted = sorted(multi, key=lambda x: sum(float(b["pl"]) for b in x[1]))
    for mid, bets in multi_sorted[:5]:
        pl = sum(float(b["pl"]) for b in bets)
        strats = " + ".join(b["strategy"] for b in bets)
        print(f"  {mid[:50]:50}  P&L:{pl:+.2f}  [{strats}]")

    # Los 5 mejores partidos multi-apuesta
    print("\n" + "="*70)
    print("TOP 5 PARTIDOS MULTI-APUESTA POR GANANCIA")
    print("="*70)
    for mid, bets in multi_sorted[-5:][::-1]:
        pl = sum(float(b["pl"]) for b in bets)
        strats = " + ".join(b["strategy"] for b in bets)
        print(f"  {mid[:50]:50}  P&L:{pl:+.2f}  [{strats}]")

    # Correlacion: cuando 2 bets del mismo partido, ¿tienden a ganar/perder juntas?
    print("\n" + "="*70)
    print("CORRELACIÓN DE RESULTADOS EN PARTIDOS CON 2+ APUESTAS")
    print("="*70)
    both_win = both_lose = mixed = 0
    both_win_pl = both_lose_pl = mixed_pl = 0.0
    for mid, bets in matches.items():
        if len(bets) < 2:
            continue
        wins = sum(1 for b in bets if int(b["won"]) == 1)
        pl = sum(float(b["pl"]) for b in bets)
        if wins == len(bets):
            both_win += 1; both_win_pl += pl
        elif wins == 0:
            both_lose += 1; both_lose_pl += pl
        else:
            mixed += 1; mixed_pl += pl
    total_multi = both_win + both_lose + mixed
    print(f"  Todos ganan:     {both_win:3d} partidos ({both_win/total_multi*100:.0f}%)  P&L: {both_win_pl:+.2f}")
    print(f"  Todos pierden:   {both_lose:3d} partidos ({both_lose/total_multi*100:.0f}%)  P&L: {both_lose_pl:+.2f}")
    print(f"  Mixto (1W+1L+):  {mixed:3d} partidos ({mixed/total_multi*100:.0f}%)  P&L: {mixed_pl:+.2f}")
    print(f"  → Cuando todo gana: P&L promedio {both_win_pl/max(both_win,1):+.2f}")
    print(f"  → Cuando todo pierde: P&L promedio {both_lose_pl/max(both_lose,1):+.2f}")

if __name__ == "__main__":
    main()
