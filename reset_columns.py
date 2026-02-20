import pandas as pd
from pathlib import Path

data_dir = Path(r'C:\Users\agonz\OneDrive\Documents\Proyectos\Furbo\betfair_scraper\data')

# Archivos que quedaron como Desconocido (tenemos una muestra)
files_to_reset = [
    'partido_al-ahli-al-ahli-uae-apuestas-35269087.csv',
    'partido_al-gharafa-tractor-sazi-fc-apuestas-35277632.csv',
    'partido_al-hilal-al-wahda-abu-dhabi-apuestas-35269089.csv',
    'partido_al-hussein-sc-esteghlal-fc-apuestas-35277998.csv',
    'partido_al-sadd-al-ittihad-apuestas-35273530.csv',
    'partido_al-sharjah-nasaf-apuestas-35269093.csv',
]

for filename in files_to_reset:
    file_path = data_dir / filename
    if file_path.exists():
        df = pd.read_csv(file_path)
        if 'País' in df.columns and 'Liga' in df.columns:
            df = df.drop(['País', 'Liga'], axis=1)
            df.to_csv(file_path, index=False)
            print(f"Reset: {filename}")
    else:
        print(f"No encontrado: {filename}")

print("Listo!")
