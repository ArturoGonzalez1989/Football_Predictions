#!/usr/bin/env python3
"""
Analiza la calidad de datos de los partidos capturados.
Determina qué porcentaje es 'salvable' para análisis de trends.

Criterios de salvabilidad:
- Mínimo 5 capturas (necesario para ver trends)
- Campos críticos presentes: timestamp, xG, corners, shots
- Sin datos corruptos (valores NaN, timestamps inválidos)
- Cobertura estadística >50% (al menos la mitad de los campos con datos)
"""

import csv
import os
from pathlib import Path
from datetime import datetime
from collections import defaultdict

# Configuración
DATA_DIR = Path(__file__).parent.parent / "data"
MIN_CAPTURES = 5
MIN_COVERAGE = 0.5  # 50% de campos con datos

# Campos críticos que DEBEN estar presentes
CRITICAL_FIELDS = [
    'timestamp_utc',
    'xg_local',
    'xg_visitante',
    'corners_local',
    'corners_visitante',
    'tiros_local',
    'tiros_visitante'
]

# Campos estadísticos para calcular cobertura
STAT_FIELDS = [
    'xg_local', 'xg_visitante',
    'corners_local', 'corners_visitante',
    'tiros_local', 'tiros_visitante',
    'tiros_puerta_local', 'tiros_puerta_visitante',
    'posesion_local', 'posesion_visitante',
    'fouls_conceded_local', 'fouls_conceded_visitante',
    'big_chances_local', 'big_chances_visitante',
    'attacks_local', 'attacks_visitante',
    'dangerous_attacks_local', 'dangerous_attacks_visitante',
    'tackles_local', 'tackles_visitante',
    'saves_local', 'saves_visitante'
]


def analyze_csv(csv_path):
    """Analiza un CSV y retorna métricas de calidad"""
    result = {
        'path': csv_path,
        'name': csv_path.stem.replace('partido_', ''),
        'captures': 0,
        'critical_fields_ok': False,
        'coverage': 0.0,
        'has_corrupted_data': False,
        'salvable': False,
        'issues': []
    }

    try:
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        if not rows:
            result['issues'].append("CSV vacío")
            return result

        result['captures'] = len(rows)

        # Verificar campos críticos
        first_row = rows[0]
        missing_critical = [f for f in CRITICAL_FIELDS if f not in first_row]
        if not missing_critical:
            result['critical_fields_ok'] = True
        else:
            result['issues'].append(f"Faltan campos críticos: {', '.join(missing_critical)}")

        # Calcular cobertura de datos (% de campos estadísticos con datos)
        total_coverage = 0
        for row in rows:
            filled = sum(1 for field in STAT_FIELDS if field in row and row[field].strip() and row[field] not in ['', 'N/A', 'None'])
            coverage = filled / len(STAT_FIELDS) if STAT_FIELDS else 0
            total_coverage += coverage

        result['coverage'] = total_coverage / len(rows) if rows else 0

        # Detectar datos corruptos
        for i, row in enumerate(rows):
            # Verificar timestamp válido
            ts = row.get('timestamp_utc', '')
            if ts:
                try:
                    datetime.fromisoformat(ts.replace('Z', '+00:00'))
                except:
                    result['has_corrupted_data'] = True
                    result['issues'].append(f"Timestamp invalido en fila {i+2}")
                    break

            # Verificar valores numéricos en campos críticos
            for field in ['xg_local', 'xg_visitante']:
                val = row.get(field, '')
                if val and val not in ['', 'N/A', 'None']:
                    try:
                        float_val = float(val)
                        if float_val < 0 or float_val > 20:  # xG razonable entre 0-20
                            result['has_corrupted_data'] = True
                            result['issues'].append(f"Valor xG anómalo en fila {i+2}: {float_val}")
                            break
                    except:
                        result['has_corrupted_data'] = True
                        result['issues'].append(f"Valor xG no numérico en fila {i+2}: {val}")
                        break

        # Determinar si es salvable
        result['salvable'] = (
            result['captures'] >= MIN_CAPTURES and
            result['critical_fields_ok'] and
            result['coverage'] >= MIN_COVERAGE and
            not result['has_corrupted_data']
        )

        if not result['salvable']:
            if result['captures'] < MIN_CAPTURES:
                result['issues'].append(f"Pocas capturas: {result['captures']} < {MIN_CAPTURES}")
            if result['coverage'] < MIN_COVERAGE:
                result['issues'].append(f"Baja cobertura: {result['coverage']:.1%} < {MIN_COVERAGE:.1%}")

    except Exception as e:
        result['issues'].append(f"Error leyendo CSV: {str(e)}")

    return result


def generate_report(results):
    """Genera reporte consolidado"""
    print("\n" + "="*80)
    print("ANÁLISIS DE CALIDAD DE DATOS - PARTIDOS CAPTURADOS")
    print("="*80)

    total = len(results)
    salvable = [r for r in results if r['salvable']]
    not_salvable = [r for r in results if not r['salvable']]

    print(f"\n[RESUMEN GENERAL]")
    print(f"   Total partidos analizados: {total}")
    print(f"   Partidos SALVABLES: {len(salvable)} ({len(salvable)/total*100:.1f}%)")
    print(f"   Partidos NO salvables: {len(not_salvable)} ({len(not_salvable)/total*100:.1f}%)")

    # Estadísticas de capturas
    captures_stats = [r['captures'] for r in results]
    avg_captures = sum(captures_stats) / len(captures_stats) if captures_stats else 0

    print(f"\n[ESTADÍSTICAS DE CAPTURAS]")
    print(f"   Promedio capturas/partido: {avg_captures:.1f}")
    print(f"   Mínimo: {min(captures_stats)}, Máximo: {max(captures_stats)}")

    # Cobertura de datos
    avg_coverage = sum(r['coverage'] for r in results) / len(results) if results else 0
    print(f"\n[COBERTURA DE DATOS]")
    print(f"   Cobertura promedio: {avg_coverage:.1%}")

    # Top 10 partidos salvables (más capturas)
    if salvable:
        print(f"\n[TOP 10 PARTIDOS SALVABLES]")
        salvable_sorted = sorted(salvable, key=lambda x: x['captures'], reverse=True)[:10]
        for i, r in enumerate(salvable_sorted, 1):
            print(f"   {i}. {r['name'][:60]}")
            print(f"      Capturas: {r['captures']}, Cobertura: {r['coverage']:.1%}")

    # Razones de rechazo
    if not_salvable:
        print(f"\n[RAZONES DE RECHAZO - NO SALVABLES]")
        issue_counts = defaultdict(int)
        for r in not_salvable:
            for issue in r['issues']:
                # Agrupar issues similares
                if 'Pocas capturas' in issue:
                    issue_counts['Pocas capturas (< 5)'] += 1
                elif 'Baja cobertura' in issue:
                    issue_counts['Baja cobertura estadística (< 50%)'] += 1
                elif 'Faltan campos críticos' in issue:
                    issue_counts['Campos críticos faltantes'] += 1
                elif 'corruptos' in issue.lower():
                    issue_counts['Datos corruptos/inválidos'] += 1

        for issue, count in sorted(issue_counts.items(), key=lambda x: x[1], reverse=True):
            print(f"   - {issue}: {count} partidos ({count/len(not_salvable)*100:.1f}%)")

    # Partidos con problemas graves
    corrupted = [r for r in results if r['has_corrupted_data']]
    if corrupted:
        print(f"\n[PARTIDOS CON DATOS CORRUPTOS]")
        for r in corrupted[:5]:
            print(f"   - {r['name'][:60]}")
            print(f"     Issues: {'; '.join(r['issues'])}")

    print("\n" + "="*80)
    print(f"\n[RECOMENDACION]")
    if len(salvable) / total >= 0.6:
        print(f"   [OK] BUENA calidad general ({len(salvable)/total*100:.1f}% salvable)")
        print(f"   Puedes proceder con analisis de trends en los {len(salvable)} partidos salvables")
    elif len(salvable) / total >= 0.4:
        print(f"   [WARNING] Calidad MEDIA ({len(salvable)/total*100:.1f}% salvable)")
        print(f"   Considera recapturar partidos con pocas capturas si aun estan activos")
    else:
        print(f"   [ERROR] Calidad BAJA ({len(salvable)/total*100:.1f}% salvable)")
        print(f"   Recomendado: Iniciar captura limpia con scraper actualizado")

    # Guardar lista de salvables
    salvable_file = Path(__file__).parent.parent / "data" / "partidos_salvables.txt"
    with open(salvable_file, 'w', encoding='utf-8') as f:
        f.write(f"# Partidos salvables para análisis ({len(salvable)} de {total})\n")
        f.write(f"# Generado: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        for r in sorted(salvable, key=lambda x: x['captures'], reverse=True):
            f.write(f"{r['path'].name}\t{r['captures']} capturas\t{r['coverage']:.1%} cobertura\n")

    print(f"\n   Lista guardada en: {salvable_file}")
    print("="*80 + "\n")

    return {
        'total': total,
        'salvable': len(salvable),
        'not_salvable': len(not_salvable),
        'percentage': len(salvable) / total * 100 if total > 0 else 0
    }


def main():
    """Función principal"""
    if not DATA_DIR.exists():
        print(f"[ERROR] Directorio {DATA_DIR} no existe")
        return

    # Obtener todos los CSVs (excepto unificado.csv)
    csv_files = [f for f in DATA_DIR.glob("partido_*.csv")]

    if not csv_files:
        print(f"[ERROR] No se encontraron CSVs en {DATA_DIR}")
        return

    print(f"[INFO] Analizando {len(csv_files)} partidos...")

    # Analizar cada CSV
    results = []
    for csv_file in csv_files:
        result = analyze_csv(csv_file)
        results.append(result)

    # Generar reporte
    summary = generate_report(results)

    return summary


if __name__ == "__main__":
    main()
