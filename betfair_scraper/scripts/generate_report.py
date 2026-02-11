#!/usr/bin/env python3
"""
Script para generar reportes de supervision
Analiza logs, verifica calidad de datos y genera informe final
"""

import csv
import re
import sys
import io
from pathlib import Path
from datetime import datetime
from collections import Counter

# Configurar encoding para Windows
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Configuracion
GAMES_CSV = Path("games.csv")
DATA_DIR = Path("data")
LOGS_DIR = Path("logs")


def get_latest_log():
    """Obtiene el log mas reciente del scraper"""
    if not LOGS_DIR.exists():
        return None

    log_files = sorted(LOGS_DIR.glob("scraper_*.log"), key=lambda x: x.stat().st_mtime, reverse=True)
    return log_files[0] if log_files else None


def analyze_games_csv():
    """Analiza games.csv y retorna estadisticas"""
    stats = {
        "total": 0,
        "activos": 0,
        "futuros": 0,
        "sin_fecha": 0
    }

    if not GAMES_CSV.exists():
        return stats

    try:
        with open(GAMES_CSV, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            games = list(reader)

        now = datetime.now()
        stats["total"] = len(games)

        for game in games:
            fecha_str = game.get("fecha_hora_inicio", "").strip()
            if not fecha_str:
                stats["sin_fecha"] += 1
                stats["activos"] += 1
                continue

            try:
                # Intentar parsear fecha
                for fmt in ["%Y-%m-%d %H:%M", "%d/%m/%Y %H:%M"]:
                    try:
                        game_time = datetime.strptime(fecha_str, fmt)
                        if game_time > now:
                            stats["futuros"] += 1
                        else:
                            stats["activos"] += 1
                        break
                    except ValueError:
                        continue
            except:
                stats["sin_fecha"] += 1

    except Exception as e:
        print(f"[ERROR] Error analizando games.csv: {e}")

    return stats


def analyze_data_files():
    """Analiza archivos de datos capturados"""
    stats = {
        "total_csvs": 0,
        "filas_totales": 0,
        "con_cuotas": 0,
        "con_stats": 0
    }

    if not DATA_DIR.exists():
        return stats

    try:
        csv_files = list(DATA_DIR.glob("partido_*.csv"))
        stats["total_csvs"] = len(csv_files)

        for csv_file in csv_files[:5]:  # Analizar primeros 5
            try:
                with open(csv_file, "r", encoding="utf-8", errors="ignore") as f:
                    reader = csv.DictReader(f)
                    rows = list(reader)
                    stats["filas_totales"] += len(rows)

                    # Verificar cuotas
                    for row in rows:
                        back_home = row.get("back_home", "").strip()
                        if back_home:
                            stats["con_cuotas"] += 1

                        # Verificar stats
                        xg_local = row.get("xg_local", "").strip()
                        opta_points = row.get("opta_points_local", "").strip()
                        if xg_local or opta_points:
                            stats["con_stats"] += 1

            except Exception as e:
                print(f"[DEBUG] Error analizando {csv_file.name}: {e}")

    except Exception as e:
        print(f"[ERROR] Error analizando data files: {e}")

    return stats


def analyze_log():
    """Analiza el log del scraper y extrae metricas"""
    stats = {
        "errores": 0,
        "warnings": 0,
        "capturas_exitosas": 0,
        "duracion_ciclo": 0,
        "ultimo_timestamp": None
    }

    log_file = get_latest_log()
    if not log_file:
        return stats

    try:
        with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()

        # Analizar ultimas 500 lineas
        recent_lines = lines[-500:] if len(lines) > 500 else lines

        for line in recent_lines:
            if "[ERROR]" in line:
                stats["errores"] += 1
            if "[WARNING]" in line:
                stats["warnings"] += 1
            if "Captura exitosa" in line or "exitosas" in line:
                stats["capturas_exitosas"] += 1

        # Extraer timestamp del ultim log
        if lines:
            last_line = lines[-1]
            if len(last_line) > 19:
                try:
                    stats["ultimo_timestamp"] = last_line[:19]
                except:
                    pass

        # Buscar duracion de ciclo
        for line in recent_lines[-20:]:
            match = re.search(r"Ciclo tard[ó|o] ([\d\.]+)s", line)
            if match:
                stats["duracion_ciclo"] = float(match.group(1))
                break

    except Exception as e:
        print(f"[ERROR] Error analizando log: {e}")

    return stats


def generate_report_text(games_stats, data_stats, log_stats):
    """Genera el texto del reporte"""
    report = []

    report.append("")
    report.append("=" * 60)
    report.append("INFORME DE SUPERVISION")
    report.append("=" * 60)
    report.append("")

    # Timestamp
    report.append(f"Hora: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append("")

    # Seccion: Partidos
    report.append("1. PARTIDOS CONFIGURADOS")
    report.append("-" * 40)
    report.append(f"   Total: {games_stats['total']} partidos")
    report.append(f"   Activos: {games_stats['activos']}")
    report.append(f"   Futuros: {games_stats['futuros']}")
    if games_stats['sin_fecha'] > 0:
        report.append(f"   Sin fecha (legacy): {games_stats['sin_fecha']}")
    report.append("")

    # Seccion: Datos Capturados
    if data_stats['total_csvs'] > 0:
        report.append("2. DATOS CAPTURADOS")
        report.append("-" * 40)
        report.append(f"   CSVs de partidos: {data_stats['total_csvs']}")
        report.append(f"   Filas totales: {data_stats['filas_totales']}")

        # Calcular porcentajes
        if data_stats['filas_totales'] > 0:
            pct_cuotas = (data_stats['con_cuotas'] / data_stats['filas_totales']) * 100
            pct_stats = (data_stats['con_stats'] / data_stats['filas_totales']) * 100
            report.append(f"   Filas con cuotas: {pct_cuotas:.1f}%")
            report.append(f"   Filas con stats: {pct_stats:.1f}%")

        report.append("")

    # Seccion: Salud del Scraper
    report.append("3. SALUD DEL SCRAPER")
    report.append("-" * 40)
    report.append(f"   Errores recientes: {log_stats['errores']}")
    report.append(f"   Warnings recientes: {log_stats['warnings']}")
    report.append(f"   Capturas exitosas: {log_stats['capturas_exitosas']}")
    if log_stats['duracion_ciclo'] > 0:
        status_ciclo = "OK" if log_stats['duracion_ciclo'] < 30 else "LENTO"
        report.append(f"   Duracion ciclo: {log_stats['duracion_ciclo']:.1f}s [{status_ciclo}]")
    if log_stats['ultimo_timestamp']:
        report.append(f"   Ultima actividad: {log_stats['ultimo_timestamp']}")
    report.append("")

    # Seccion: Conclusion
    report.append("4. ESTADO GENERAL")
    report.append("-" * 40)

    is_healthy = (
        log_stats['errores'] < 10 and
        games_stats['total'] > 0 and
        data_stats['total_csvs'] > 0
    )

    if is_healthy:
        report.append("   STATUS: [OK] Sistema funcionando correctamente")
        report.append("   - Scraper capturando datos")
        report.append("   - Partidos configurados activamente")
        report.append("   - Calidad de datos aceptable")
    else:
        report.append("   STATUS: [ATENCION] Revisar problemas detectados")
        if games_stats['total'] == 0:
            report.append("   - WARNING: Sin partidos en games.csv")
        if data_stats['total_csvs'] == 0:
            report.append("   - WARNING: Sin datos capturados")
        if log_stats['errores'] > 10:
            report.append(f"   - WARNING: Muchos errores ({log_stats['errores']})")

    report.append("")
    report.append("=" * 60)
    report.append("")

    return "\n".join(report)


def save_report(content):
    """Guarda el reporte en un archivo"""
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = Path("logs") / f"report_{timestamp}.txt"

        report_file.parent.mkdir(parents=True, exist_ok=True)

        with open(report_file, "w", encoding="utf-8") as f:
            f.write(content)

        print(f"[INFO] Reporte guardado: {report_file.name}")
        return report_file

    except Exception as e:
        print(f"[ERROR] Error guardando reporte: {e}")
        return None


def main():
    """Funcion principal"""
    print("\n" + "="*60)
    print("GENERACION DE REPORTES")
    print("="*60)

    # Recopilar estadisticas
    print("[INFO] Analizando partidos...")
    games_stats = analyze_games_csv()

    print("[INFO] Analizando datos capturados...")
    data_stats = analyze_data_files()

    print("[INFO] Analizando logs...")
    log_stats = analyze_log()

    # Generar reporte
    report_text = generate_report_text(games_stats, data_stats, log_stats)

    # Mostrar reporte
    print(report_text)

    # Guardar reporte
    save_report(report_text)

    print("="*60 + "\n")


if __name__ == "__main__":
    main()
