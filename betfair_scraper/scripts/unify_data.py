#!/usr/bin/env python3
"""
PASO 7: Unificar todos los CSVs de datos en un único archivo

Combina todos los archivos partido_*.csv de la carpeta data/
en un único unificado.csv manteniendo todas las columnas de todos los archivos.

Función:
- Lee todos los CSVs generados por el scraper
- Combina todas las filas
- Mantiene la unión de todas las columnas (si un CSV tiene columnas que otro no, las incluye)
- Genera unificado.csv que puede usarse para análisis global
- Se ejecuta automáticamente después de cada captura
"""

import pandas as pd
import os
import sys
import io
from pathlib import Path
from datetime import datetime

# Configurar encoding para Windows
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')


def unify_csvs():
    """
    Lee todos los archivos partido_*.csv y los unifica en unificado.csv
    """

    # Obtener ruta de la carpeta data
    script_dir = Path(__file__).parent.parent
    data_dir = script_dir / "data"

    if not data_dir.exists():
        print(f"\n[ERROR] Carpeta data no encontrada: {data_dir}")
        return False

    # Buscar todos los archivos partido_*.csv
    partido_files = sorted(data_dir.glob("partido_*.csv"))

    if not partido_files:
        print(f"\n[ALERTA] No se encontraron archivos partido_*.csv en {data_dir}")
        return False

    print(f"\n[INFO] Encontrados {len(partido_files)} archivos de partidos para unificar")
    print(f"[INFO] Leyendo y combinando archivos...\n")

    # Leer todos los CSVs
    dataframes = []
    filas_total = 0
    archivos_procesados = 0
    errores = []

    for partido_file in partido_files:
        try:
            df = pd.read_csv(partido_file, encoding='utf-8')
            dataframes.append(df)
            filas_total += len(df)
            archivos_procesados += 1

            # Mostrar progreso cada 10 archivos
            if archivos_procesados % 10 == 0:
                print(f"  ✓ Procesados {archivos_procesados}/{len(partido_files)} archivos ({filas_total} filas)")

        except Exception as e:
            error_msg = f"Error leyendo {partido_file.name}: {str(e)}"
            errores.append(error_msg)
            print(f"  [AVISO] {error_msg}")

    if not dataframes:
        print("\n[ERROR] No se pudieron leer ningún archivo CSV")
        return False

    print(f"\n[INFO] Combinando {len(dataframes)} DataFrames...")

    # Combinar todos los DataFrames (mantiene la unión de columnas)
    try:
        df_unificado = pd.concat(dataframes, axis=0, ignore_index=True, sort=False)
    except Exception as e:
        print(f"\n[ERROR] No se pudieron combinar los archivos: {str(e)}")
        return False

    # Reordenar columnas de forma consistente (poner columnas importantes primero)
    columnas_prioridad = [
        'tab_id', 'timestamp_utc', 'evento', 'hora_comienzo',
        'estado_partido', 'minuto', 'goles_local', 'goles_visitante', 'url'
    ]

    columnas_orden = []
    for col in columnas_prioridad:
        if col in df_unificado.columns:
            columnas_orden.append(col)

    # Añadir el resto de columnas en orden alfabético
    columnas_restantes = sorted([col for col in df_unificado.columns if col not in columnas_orden])
    columnas_orden.extend(columnas_restantes)

    df_unificado = df_unificado[columnas_orden]

    # Guardar el archivo unificado
    output_file = data_dir / "unificado.csv"

    try:
        df_unificado.to_csv(output_file, index=False, encoding='utf-8')
    except Exception as e:
        print(f"\n[ERROR] No se pudo guardar {output_file}: {str(e)}")
        return False

    # Estadísticas
    print(f"\n{'='*70}")
    print(f"  UNIFICACIÓN COMPLETADA")
    print(f"{'='*70}")
    print(f"\n[ESTADÍSTICAS]")
    print(f"  Total de archivos procesados: {archivos_procesados}/{len(partido_files)}")
    print(f"  Total de filas combinadas: {len(df_unificado):,}")
    print(f"  Total de columnas: {len(df_unificado.columns)}")
    print(f"  Tamaño del archivo: {output_file.stat().st_size / 1024 / 1024:.2f} MB")
    print(f"  Ubicación: {output_file}")

    if errores:
        print(f"\n[ADVERTENCIAS]")
        for error in errores:
            print(f"  - {error}")

    print(f"\n[OK] unificado.csv actualizado exitosamente")
    print(f"\nÚltimo timestamp: {df_unificado['timestamp_utc'].max() if 'timestamp_utc' in df_unificado.columns else 'N/A'}")

    print(f"\n{'='*70}\n")

    return True


if __name__ == "__main__":
    success = unify_csvs()
    sys.exit(0 if success else 1)
