import os
import pandas as pd
from pathlib import Path
from urllib.parse import unquote

# ============================================================================
# MÉTODO 1: Mapping de patrones de URL a País y Liga
# ============================================================================
URL_LEAGUE_MAPPING = {
    # España
    'la-liga-española': ('España', 'La Liga'),
    'segunda-división-española': ('España', 'Segunda División'),
    'espa%C3%B1a-segunda-divisi%C3%B3n': ('España', 'Segunda División'),
    'españa-segunda-división': ('España', 'Segunda División'),
    'copa-del-rey': ('España', 'Copa del Rey'),

    # Inglaterra
    'fa-cup-inglesa': ('Inglaterra', 'FA Cup'),
    'liga-premiership-inglesa': ('Inglaterra', 'Premier League'),
    'championship-inglés': ('Inglaterra', 'Championship'),
    'league-one-inglés': ('Inglaterra', 'League One'),
    'league-two-inglés': ('Inglaterra', 'League Two'),
    'carabao-cup': ('Inglaterra', 'Carabao Cup'),
    'women-super-league': ('Inglaterra', "Women's Super League"),
    'inglaterra-sky-bet-league-1': ('Inglaterra', 'League One'),
    'inglaterra-sky-bet-league-2': ('Inglaterra', 'League Two'),
    'inglaterra-sky-bet-championship': ('Inglaterra', 'Championship'),

    # Alemania
    'bundesliga': ('Alemania', 'Bundesliga'),
    '2-bundesliga': ('Alemania', '2. Bundesliga'),
    'dfb-pokal': ('Alemania', 'DFB-Pokal'),

    # Italia
    'serie-a-italiana': ('Italia', 'Serie A'),
    'serie-b-italiana': ('Italia', 'Serie B'),
    'coppa-italia': ('Italia', 'Coppa Italia'),
    'serie-a-brasil': ('Brasil', 'Série A'),
    'serie-b-brasil': ('Brasil', 'Série B'),

    # Francia
    'ligue-1-francesa': ('Francia', 'Ligue 1'),
    'ligue-2-francesa': ('Francia', 'Ligue 2'),
    'copa-francesa': ('Francia', 'Coupe de France'),

    # Portugal
    'liga-portuguesa': ('Portugal', 'Primeira Liga'),
    'portugal-primeira-liga': ('Portugal', 'Primeira Liga'),
    'segunda-liga-portuguesa': ('Portugal', 'Segunda Liga'),
    'taça-portugal': ('Portugal', 'Taça de Portugal'),
    'taça-da-liga-portuguesa': ('Portugal', 'Taça da Liga'),

    # Holanda
    'eredivisie-holandesa': ('Holanda', 'Eredivisie'),
    'eerste-divisie': ('Holanda', 'Eerste Divisie'),
    'knvb-beker': ('Holanda', 'KNVB Beker'),

    # Bélgica
    'jupiler-league-pro': ('Bélgica', 'Jupiler Pro League'),
    'b%C3%A9lgica-pro-league': ('Bélgica', 'Jupiler Pro League'),
    'bélgica-pro-league': ('Bélgica', 'Jupiler Pro League'),
    'primera-división-belga': ('Bélgica', 'Primera División'),
    'copa-belga': ('Bélgica', 'Copa Belga'),

    # Suiza
    'super-league-suiza': ('Suiza', 'Super League'),
    'challenge-league-suiza': ('Suiza', 'Challenge League'),
    'copa-suiza': ('Suiza', 'Copa Suiza'),

    # Austria
    'bundesliga-austriaca': ('Austria', 'Bundesliga'),
    'segunda-liga-austriaca': ('Austria', 'Segunda Liga'),

    # República Checa
    'liga-checa': ('República Checa', 'Liga Checa'),

    # Dinamarca
    'superligaen-danesa': ('Dinamarca', 'Superligaen'),
    'dinamarca-superliga': ('Dinamarca', 'Superligaen'),
    'primera-división-danesa': ('Dinamarca', 'Primera División'),

    # Grecia
    'super-league-griega': ('Grecia', 'Super League'),
    'segunda-división-griega': ('Grecia', 'Segunda División'),

    # Turquía
    'superlig-turca': ('Turquía', 'Süper Lig'),
    'superliga-turca': ('Turquía', 'Süper Lig'),
    'primera-división-turca': ('Turquía', 'Primera División'),

    # Bulgaria
    'primera-división-búlgara': ('Bulgaria', 'Primera División'),
    'liga-a-b%C3%BAlgara': ('Bulgaria', 'Liga A'),
    'liga-a-búlgara': ('Bulgaria', 'Liga A'),
    'segunda-división-búlgara': ('Bulgaria', 'Segunda División'),

    # Rumania
    'liga-1-rumana': ('Rumania', 'Liga 1'),
    'romanian-liga-i': ('Rumania', 'Liga 1'),

    # Japón
    'j-league': ('Japón', 'J-League'),
    'j-league-2': ('Japón', 'J-League 2'),
    'japanese-j-league': ('Japón', 'J-League'),

    # Indonesia
    'liga-indonesia': ('Indonesia', 'Liga Indonesia'),
    'indonesia-super-league': ('Indonesia', 'Super League'),

    # América del Sur - Internacional
    'conmebol-copa-libertadores': ('Internacional', 'Copa Libertadores'),
    'conmebol-copa-sudamericana': ('Internacional', 'Copa Sudamericana'),
    'copa-argentina': ('Argentina', 'Copa Argentina'),
    'copa-brasil': ('Brasil', 'Copa do Brasil'),

    # Argentina
    'liga-argentina': ('Argentina', 'Liga Argentina'),
    'argentina-primera-divisi%C3%B3n': ('Argentina', 'Liga Argentina'),
    'argentina-primera-división': ('Argentina', 'Liga Argentina'),

    # Brasil
    'primeira-divisão-brasil': ('Brasil', 'Série A'),
    'paulista-seria-a1-brasil': ('Brasil', 'Paulista Serie A1'),

    # Chile
    'liga-chilena': ('Chile', 'Primera División'),
    'chile-primera-divisi%C3%B3n': ('Chile', 'Primera División'),
    'chile-primera-división': ('Chile', 'Primera División'),

    # Colombia
    'colombia-primera-a': ('Colombia', 'Liga Colombiana'),
    'liga-colombiana': ('Colombia', 'Liga Colombiana'),

    # Ecuador
    'liga-ecuatoriana': ('Ecuador', 'Liga Ecuatoriana'),

    # Perú
    'liga-peruana': ('Perú', 'Liga Peruana'),

    # Uruguay
    'liga-uruguaya': ('Uruguay', 'Liga Uruguaya'),
    'uruguayan-primera-division': ('Uruguay', 'Liga Uruguaya'),

    # Paraguay
    'liga-paraguaya': ('Paraguay', 'Liga Paraguaya'),

    # Bolivia
    'liga-boliviana': ('Bolivia', 'Liga Boliviana'),

    # Venezuela
    'liga-venezolana': ('Venezuela', 'Liga Venezolana'),

    # México
    'liga-mexicana': ('México', 'Liga Mexicana'),
    'liga-mx': ('México', 'Liga MX'),

    # Escocia
    'premiership-escocesa': ('Escocia', 'Premiership'),

    # Corea del Sur
    'k-league': ('Corea del Sur', 'K-League'),

    # Oriente Medio
    'saudi-pro-league': ('Arabia Saudita', 'Saudi Pro League'),
    'saudi-arabia': ('Arabia Saudita', 'Saudi Pro League'),
    'uae-pro-league': ('Emiratos Árabes Unidos', 'UAE Pro League'),
    'qatar-stars-league': ('Qatar', 'Qatar Stars League'),
    'iraqi-premier-league': ('Irak', 'Iraqi Premier League'),
    'iran-pro-league': ('Irán', 'Iran Pro League'),

    # Competiciones Asiáticas
    'champions-league-asiática': ('Internacional', 'AFC Champions League'),
    'champions-league-asi%C3%A1tica': ('Internacional', 'AFC Champions League'),

    # Chipre
    '1st-division-chipre': ('Chipre', 'Primera División'),

    # Egipto
    'egipto-premier-league': ('Egipto', 'Premier League'),

    # Eslovenia
    'premier-league-eslovena': ('Eslovenia', 'Premier League'),
}

# ============================================================================
# MÉTODO 2: Mapping de equipos conocidos a País y Liga
# ============================================================================
TEAM_COUNTRY_MAPPING = {
    # España
    'real-madrid': ('España', 'La Liga'),
    'barcelona': ('España', 'La Liga'),
    'atletico': ('España', 'La Liga'),
    'atlético': ('España', 'La Liga'),
    'sevilla': ('España', 'La Liga'),
    'valencia': ('España', 'La Liga'),
    'villarreal': ('España', 'La Liga'),
    'athletic': ('España', 'La Liga'),
    'bilbao': ('España', 'La Liga'),
    'real-sociedad': ('España', 'La Liga'),
    'real-betis': ('España', 'La Liga'),
    'osasuna': ('España', 'La Liga'),
    'getafe': ('España', 'La Liga'),
    'rayo-vallecano': ('España', 'La Liga'),
    'celta': ('España', 'La Liga'),
    'alaves': ('España', 'La Liga'),
    'alavés': ('España', 'La Liga'),
    'elche': ('España', 'La Liga'),
    'granada': ('España', 'La Liga'),
    'leganes': ('España', 'La Liga'),
    'leganés': ('España', 'La Liga'),
    'cordoba': ('España', 'La Liga'),
    'córdoba': ('España', 'La Liga'),

    # Inglaterra
    'liverpool': ('Inglaterra', 'Premier League'),
    'manchester-united': ('Inglaterra', 'Premier League'),
    'manchester-city': ('Inglaterra', 'Premier League'),
    'arsenal': ('Inglaterra', 'Premier League'),
    'chelsea': ('Inglaterra', 'Premier League'),
    'tottenham': ('Inglaterra', 'Premier League'),
    'newcastle': ('Inglaterra', 'Premier League'),
    'brighton': ('Inglaterra', 'Premier League'),
    'aston-villa': ('Inglaterra', 'Premier League'),
    'everton': ('Inglaterra', 'Premier League'),
    'west-ham': ('Inglaterra', 'Premier League'),
    'bournemouth': ('Inglaterra', 'Premier League'),
    'fulham': ('Inglaterra', 'Premier League'),
    'nottingham': ('Inglaterra', 'Championship'),
    'leeds': ('Inglaterra', 'Championship'),
    'ipswich': ('Inglaterra', 'Championship'),
    'blackburn': ('Inglaterra', 'Championship'),

    # Alemania
    'bayern': ('Alemania', 'Bundesliga'),
    'dortmund': ('Alemania', 'Bundesliga'),
    'leverkusen': ('Alemania', 'Bundesliga'),
    'hamburgo': ('Alemania', 'Bundesliga'),
    'hamburg': ('Alemania', 'Bundesliga'),
    'schalke': ('Alemania', 'Bundesliga'),
    'frankfurt': ('Alemania', 'Bundesliga'),
    'eintracht': ('Alemania', 'Bundesliga'),
    'hoffenheim': ('Alemania', 'Bundesliga'),
    'mainz': ('Alemania', 'Bundesliga'),
    'friburgo': ('Alemania', 'Bundesliga'),
    'freiburg': ('Alemania', 'Bundesliga'),
    'gladbach': ('Alemania', 'Bundesliga'),
    'mönchengladbach': ('Alemania', 'Bundesliga'),
    'cologne': ('Alemania', 'Bundesliga'),
    'köln': ('Alemania', 'Bundesliga'),
    'köppe': ('Alemania', 'Bundesliga'),

    # Italia
    'juventus': ('Italia', 'Serie A'),
    'inter': ('Italia', 'Serie A'),
    'milan': ('Italia', 'Serie A'),
    'roma': ('Italia', 'Serie A'),
    'lazio': ('Italia', 'Serie A'),
    'napoli': ('Italia', 'Serie A'),
    'atalanta': ('Italia', 'Serie A'),
    'fiorentina': ('Italia', 'Serie A'),
    'sassuolo': ('Italia', 'Serie A'),
    'torino': ('Italia', 'Serie A'),
    'udinese': ('Italia', 'Serie A'),
    'como': ('Italia', 'Serie A'),
    'pisa': ('Italia', 'Serie A'),

    # Francia
    'psg': ('Francia', 'Ligue 1'),
    'paris': ('Francia', 'Ligue 1'),
    'marseille': ('Francia', 'Ligue 1'),
    'marseilia': ('Francia', 'Ligue 1'),
    'lyon': ('Francia', 'Ligue 1'),
    'monaco': ('Francia', 'Ligue 1'),
    'mónaco': ('Francia', 'Ligue 1'),
    'lens': ('Francia', 'Ligue 1'),
    'nantes': ('Francia', 'Ligue 1'),
    'lille': ('Francia', 'Ligue 1'),
    'rennes': ('Francia', 'Ligue 1'),

    # Holanda
    'ajax': ('Holanda', 'Eredivisie'),
    'feyenoord': ('Holanda', 'Eredivisie'),
    'psv': ('Holanda', 'Eredivisie'),
    'eindhoven': ('Holanda', 'Eredivisie'),
    'utreght': ('Holanda', 'Eredivisie'),
    'groningen': ('Holanda', 'Eredivisie'),

    # Turquía
    'galatasaray': ('Turquía', 'Süper Lig'),
    'fenerbahce': ('Turquía', 'Süper Lig'),
    'besiktas': ('Turquía', 'Süper Lig'),
    'trabzonspor': ('Turquía', 'Süper Lig'),
    'alanyaspor': ('Turquía', 'Süper Lig'),
    'konyaspor': ('Turquía', 'Süper Lig'),

    # Brasil
    'fluminense': ('Brasil', 'Série A'),
    'botafogo': ('Brasil', 'Série A'),
    'corinthians': ('Brasil', 'Série A'),
    'palmeiras': ('Brasil', 'Série A'),
    'santos': ('Brasil', 'Série A'),
    'são-paulo': ('Brasil', 'Série A'),
    'sao-paulo': ('Brasil', 'Série A'),
    'internacional': ('Brasil', 'Série A'),
    'gremio': ('Brasil', 'Série A'),
    'cruzeiro': ('Brasil', 'Série A'),
    'atlético-mineiro': ('Brasil', 'Série A'),
    'atletico-mineiro': ('Brasil', 'Série A'),
    'red-bull-bragantino': ('Brasil', 'Série A'),
    'fortaleza': ('Brasil', 'Série A'),

    # Argentina
    'river-plate': ('Argentina', 'Liga Argentina'),
    'boca-juniors': ('Argentina', 'Liga Argentina'),
    'independiente': ('Argentina', 'Liga Argentina'),
    'racing': ('Argentina', 'Liga Argentina'),
    'san-lorenzo': ('Argentina', 'Liga Argentina'),
    'estudiantes': ('Argentina', 'Liga Argentina'),
    'belgrano': ('Argentina', 'Liga Argentina'),
    'union': ('Argentina', 'Liga Argentina'),

    # Japón
    'ehime': ('Japón', 'J-League'),
    'kanazawa': ('Japón', 'J-League'),
    'tokushima': ('Japón', 'J-League'),
    'osaka': ('Japón', 'J-League'),
    'kyoto': ('Japón', 'J-League'),
    'nagoya': ('Japón', 'J-League'),
    'kobe': ('Japón', 'J-League'),
    'kawasaki': ('Japón', 'J-League'),
    'tokyo': ('Japón', 'J-League'),
    'yokohama': ('Japón', 'J-League'),
    'tochigi': ('Japón', 'J-League 2'),
    'yamagata': ('Japón', 'J-League 2'),
    'akita': ('Japón', 'J-League 2'),
    'gifu': ('Japón', 'J-League 2'),
    'iwata': ('Japón', 'J-League 2'),
    'sanuki': ('Japón', 'J-League 2'),
    'toyama': ('Japón', 'J-League 2'),
    'kochi': ('Japón', 'J-League 2'),
    'biwako': ('Japón', 'J-League 2'),
    'shiga': ('Japón', 'J-League 2'),
    'oita': ('Japón', 'J-League 2'),
    'kitakyushu': ('Japón', 'J-League 2'),
    'kumamoto': ('Japón', 'J-League 2'),
    'kagoshima': ('Japón', 'J-League 2'),
    'ryukyu': ('Japón', 'J-League 2'),
    'miyazaki': ('Japón', 'J-League 2'),
    'tottori': ('Japón', 'J-League 2'),

    # Colombia
    'atletico-nacional': ('Colombia', 'Liga Colombiana'),
    'deportivo-pasto': ('Colombia', 'Liga Colombiana'),
    'america-de-cali': ('Colombia', 'Liga Colombiana'),
    'santa-fe': ('Colombia', 'Liga Colombiana'),
    'bogota': ('Colombia', 'Liga Colombiana'),
    'medellin': ('Colombia', 'Liga Colombiana'),
    'cali': ('Colombia', 'Liga Colombiana'),

    # Uruguay
    'liverpool-montevideo': ('Uruguay', 'Liga Uruguaya'),
    'nacional': ('Uruguay', 'Liga Uruguaya'),
    'peñarol': ('Uruguay', 'Liga Uruguaya'),
    'penarol': ('Uruguay', 'Liga Uruguaya'),
    'defensor': ('Uruguay', 'Liga Uruguaya'),

    # Perú
    'sporting-cristal': ('Perú', 'Liga Peruana'),
    'cristal': ('Perú', 'Liga Peruana'),
    'alianza-lima': ('Perú', 'Liga Peruana'),
    'alianza': ('Perú', 'Liga Peruana'),

    # Arabia Saudita
    'al-ahli': ('Arabia Saudita', 'Saudi Pro League'),
    'al-hilal': ('Arabia Saudita', 'Saudi Pro League'),
    'al-nassr': ('Arabia Saudita', 'Saudi Pro League'),
    'al-ittihad': ('Arabia Saudita', 'Saudi Pro League'),
    'al-shabab': ('Arabia Saudita', 'Saudi Pro League'),
    'al-fateh': ('Arabia Saudita', 'Saudi Pro League'),
    'al-wehda': ('Arabia Saudita', 'Saudi Pro League'),
    'al-khaleej': ('Arabia Saudita', 'Saudi Pro League'),

    # Emiratos Árabes Unidos
    'al-ain': ('Emiratos Árabes Unidos', 'UAE Pro League'),
    'dubai': ('Emiratos Árabes Unidos', 'UAE Pro League'),
    'sharjah': ('Emiratos Árabes Unidos', 'UAE Pro League'),
    'abu-dhabi': ('Emiratos Árabes Unidos', 'UAE Pro League'),
    'al-jazira': ('Emiratos Árabes Unidos', 'UAE Pro League'),
    'nasaf': ('Emiratos Árabes Unidos', 'UAE Pro League'),

    # Qatar
    'al-sadd': ('Qatar', 'Qatar Stars League'),
    'al-gharafa': ('Qatar', 'Qatar Stars League'),
    'al-rayyan': ('Qatar', 'Qatar Stars League'),
    'al-duhail': ('Qatar', 'Qatar Stars League'),
    'al-wakrah': ('Qatar', 'Qatar Stars League'),

    # Irán
    'esteghlal': ('Irán', 'Iran Pro League'),
    'persepolis': ('Irán', 'Iran Pro League'),

    # Irak
    'arema': ('Indonesia', 'Liga Indonesia'),
    'semen-padang': ('Indonesia', 'Liga Indonesia'),

    # Chipre
    'anorthosis': ('Chipre', 'Primera División'),
    'digenis': ('Chipre', 'Primera División'),
    'ypsona': ('Chipre', 'Primera División'),

    # Bulgaria
    'cska': ('Bulgaria', 'Primera División'),
    'sofia': ('Bulgaria', 'Primera División'),
    'spartak-varna': ('Bulgaria', 'Primera División'),
    'varna': ('Bulgaria', 'Primera División'),
    'lokomotiv-plovdiv': ('Bulgaria', 'Primera División'),
    'plovdiv': ('Bulgaria', 'Primera División'),
    'lokomotiv-sofia': ('Bulgaria', 'Primera División'),
    'cherno-more': ('Bulgaria', 'Primera División'),

    # Rumania
    'dinamo-bucuresti': ('Rumania', 'Liga 1'),
    'steaua-bucuresti': ('Rumania', 'Liga 1'),

    # Polonia
    'legia-warszawy': ('Polonia', 'Ekstraklasa'),
    'warszawa': ('Polonia', 'Ekstraklasa'),

    # Bélgica (adicionales)
    'anderlecht': ('Bélgica', 'Jupiler Pro League'),
    'amberes': ('Bélgica', 'Jupiler Pro League'),
    'brujas': ('Bélgica', 'Jupiler Pro League'),
    'brugge': ('Bélgica', 'Jupiler Pro League'),
    'estándar-lieja': ('Bélgica', 'Jupiler Pro League'),
    'standard-de-lieja': ('Bélgica', 'Jupiler Pro League'),
    'lieja': ('Bélgica', 'Jupiler Pro League'),
    'gilloise': ('Bélgica', 'Jupiler Pro League'),
    'westerlo': ('Bélgica', 'Jupiler Pro League'),
    'mechelen': ('Bélgica', 'Jupiler Pro League'),
    'genk': ('Bélgica', 'Jupiler Pro League'),
    'charleroi': ('Bélgica', 'Jupiler Pro League'),
    'gante': ('Bélgica', 'Jupiler Pro League'),

    # Suiza (adicionales)
    'thun': ('Suiza', 'Super League'),
    'lausanne': ('Suiza', 'Super League'),
    'sion': ('Suiza', 'Super League'),
    'fc-basel': ('Suiza', 'Super League'),
    'basel': ('Suiza', 'Super League'),
    'st-gallen': ('Suiza', 'Super League'),
    'grasshoppers': ('Suiza', 'Super League'),
    'zurich': ('Suiza', 'Super League'),
    'fc-zurich': ('Suiza', 'Super League'),
    'lucerna': ('Suiza', 'Super League'),
    'young-boys': ('Suiza', 'Super League'),
    'winterthur': ('Suiza', 'Super League'),

    # Dinamarca
    'fc-copenhague': ('Dinamarca', 'Superligaen'),
    'copenhague': ('Dinamarca', 'Superligaen'),
    'fc-nordsjaelland': ('Dinamarca', 'Superligaen'),
    'nordsjaelland': ('Dinamarca', 'Superligaen'),
    'aarhus': ('Dinamarca', 'Superligaen'),
    'odense': ('Dinamarca', 'Superligaen'),
    'agf': ('Dinamarca', 'Superligaen'),
    'fredericia': ('Dinamarca', 'Superligaen'),

    # Grecia
    'olympiacos': ('Grecia', 'Super League'),
    'panathinaikos': ('Grecia', 'Super League'),
    'aek-atenas': ('Grecia', 'Super League'),
    'atenas': ('Grecia', 'Super League'),
    'levadiakos': ('Grecia', 'Super League'),

    # Portugal (adicionales)
    'guimaraes': ('Portugal', 'Primeira Liga'),
    'porto': ('Portugal', 'Primeira Liga'),
    'benfica': ('Portugal', 'Primeira Liga'),
    'sporting': ('Portugal', 'Primeira Liga'),
    'braga': ('Portugal', 'Primeira Liga'),
    'estrela': ('Portugal', 'Primeira Liga'),
}

def extract_from_url(url):
    """Método 1: Extrae País y Liga de la URL"""
    if not isinstance(url, str) or not url:
        return None

    url_decoded = unquote(url.lower())

    # Buscar en el mapping
    for league_key, (country, league) in URL_LEAGUE_MAPPING.items():
        if league_key in url_decoded:
            return (country, league)

    return None

def extract_from_teams(filename):
    """Método 2: Extrae País y Liga basándose en equipos del nombre del archivo"""
    filename_lower = filename.lower()

    # Buscar equipos conocidos en el nombre del archivo
    for team, (country, league) in TEAM_COUNTRY_MAPPING.items():
        if team in filename_lower:
            return (country, league)

    return None

def infer_from_filename(filename):
    """Método 3: Intenta inferir País/Liga de patrones en el nombre"""
    filename_lower = filename.lower()

    # Patrones por país/región
    patterns = {
        # Oriente Medio
        ('Emiratos Árabes Unidos', 'UAE Pro League'): ['al-ahli-al-ahli-uae', 'al-gharafa-tractor-sazi', 'al-hilal-al-wahda-abu-dhabi', 'al-husein', 'al-sadd', 'al-sharjah', 'nasaf', 'kocaelispor'],
        ('Arabia Saudita', 'Saudi Pro League'): ['al-ahli', 'al-hilal', 'al-nassr'],
        ('Qatar', 'Qatar Stars League'): ['al-sadd', 'al-gharafa', 'al-rayyan'],
        ('Irak', 'Iraqi Premier League'): ['iraqi', 'baghdad'],

        # América del Sur - Otros
        ('Perú', 'Liga Peruana'): ['sporting-cristal', 'alianza-lima', 'universitario', 'peru'],
        ('Bolivia', 'Liga Boliviana'): ['bolivar', 'oruro', 'blooming'],
        ('Venezuela', 'Liga Venezolana'): ['venezuela', 'caracas'],
        ('Paraguay', 'Liga Paraguaya'): ['paraguay', 'cerro', 'olimpia'],

        # Asia Pacífico
        ('Tailandia', 'Liga Tailandesa'): ['thailand', 'thai', 'bangkok'],

        # Otros
        ('Chipre', 'Primera División'): ['cyprus', 'chipre', 'anorthosis', 'digenis'],
    }

    for (country, league), pattern_list in patterns.items():
        for pattern in pattern_list:
            if pattern in filename_lower:
                return (country, league)

    return None

def process_csv_file(file_path):
    """Procesa un archivo CSV añadiendo las columnas País y Liga"""
    try:
        # Leer el CSV
        df = pd.read_csv(file_path)

        # Si ya tiene las columnas, no hacer nada
        if 'País' in df.columns and 'Liga' in df.columns:
            return False, "Ya tiene las columnas"

        # MÉTODO 1: Intentar extraer de la URL
        country, league = None, None
        is_international_competition = False
        url_decoded = ""

        if 'url' in df.columns:
            urls = df[df['url'].notna()]['url']
            if len(urls) > 0:
                url = urls.iloc[0]
                url_decoded = unquote(url.lower())
                result = extract_from_url(url)
                if result:
                    country, league = result
                    # Si es una competición internacional (pero NO AFC Champions League), intentar extraer país del equipo
                    if ('Internacional' in country or 'AFC' in league) and 'champions-league' not in url_decoded:
                        is_international_competition = True
                        country = None  # Reset para intentar encontrar del equipo

        # MÉTODO 2: Intentar extraer del nombre del archivo (equipos) - prioridad si es internacional
        if country is None:
            filename = file_path.stem  # Nombre sin extensión
            result = extract_from_teams(filename)
            if result:
                country, league = result

        # MÉTODO 3: Si aún falla, inferir de patrones en el nombre
        if country is None:
            filename = file_path.stem
            result = infer_from_filename(filename)
            if result:
                country, league = result

        # Si aún no se encontró, marcar como desconocido
        if country is None:
            country = 'Desconocido'
            league = 'Desconocida'

        # Añadir las columnas
        df['País'] = country
        df['Liga'] = league

        # Guardar el archivo
        df.to_csv(file_path, index=False)
        return True, f"{country} | {league}"

    except Exception as e:
        return False, str(e)

# ============================================================================
# MAIN
# ============================================================================
data_dir = Path(r'C:\Users\agonz\OneDrive\Documents\Proyectos\Furbo\betfair_scraper\data')
csv_files = list(data_dir.glob('partido_*.csv'))

print(f"[*] Se encontraron {len(csv_files)} archivos CSV\n")

processed = 0
skipped = 0
failed = 0

for csv_file in sorted(csv_files):
    result, message = process_csv_file(csv_file)
    if result:
        print(f"[OK] {csv_file.name[:60]:<60} -> {message}")
        processed += 1
    else:
        if "Ya tiene" in message:
            skipped += 1
        else:
            print(f"[ERROR] {csv_file.name[:60]:<60} -> {message}")
            failed += 1

print(f"\n[RESUMEN]")
print(f"   Procesados: {processed}")
print(f"   Omitidos (ya procesados): {skipped}")
print(f"   Errores: {failed}")
print(f"   Total: {len(csv_files)}")