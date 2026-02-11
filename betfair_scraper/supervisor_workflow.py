#!/usr/bin/env python3
"""
Workflow del Supervisor - Orquesta los 6 PASOS automáticamente

PASO 1: start_scraper.py      → Verifica/arranca scraper
PASO 2: find_matches.py       → Busca nuevos partidos en Betfair
PASO 3: clean_games.py        → Elimina partidos terminados
PASO 4: check_urls.py         → Verifica errores 404
PASO 5: generate_report.py    → Genera informe completo
PASO 6: validate_stats.py     → Valida estadísticas capturadas
"""

import subprocess
import sys
import io
from pathlib import Path
from datetime import datetime

# Configurar encoding para Windows
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')


def print_section(title):
    """Imprime un separador de sección"""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70 + "\n")


def execute_step(step_num, script_name, description):
    """Ejecuta un paso y retorna True si fue exitoso"""
    print_section(f"PASO {step_num}: {description}")
    print(f"[EJECUTANDO] {script_name}...\n")

    try:
        result = subprocess.run(
            [sys.executable, script_name],
            capture_output=False,
            timeout=300  # 5 minutos timeout
        )

        if result.returncode == 0:
            print(f"\n[OK] {script_name} completado exitosamente")
            return True
        else:
            print(f"\n[ERROR] {script_name} falló con código {result.returncode}")
            return False

    except subprocess.TimeoutExpired:
        print(f"\n[ERROR] {script_name} tardó más de 5 minutos (timeout)")
        return False
    except Exception as e:
        print(f"\n[ERROR] Error ejecutando {script_name}: {e}")
        return False


def check_stats_gap_in_output(script_output_text):
    """Verifica si la salida de validate_stats contiene 'Brecha de datos'"""
    if not script_output_text:
        return False
    return "Brecha de datos detectada" in script_output_text


def main():
    """Ejecuta los 6 PASOS del supervisor"""
    print("\n" + "=" * 70)
    print("  WORKFLOW DEL SUPERVISOR - ORQUESTACIÓN DE 6 PASOS")
    print("=" * 70)
    print(f"\nInicio: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Verificar que estamos en el directorio correcto
    if not Path("games.csv").exists():
        print("\n[ERROR] No se encontró games.csv")
        print("Por favor ejecuta este script desde betfair_scraper/")
        sys.exit(1)

    results = {
        "paso_1": False,
        "paso_2": False,
        "paso_3": False,
        "paso_4": False,
        "paso_5": False,
        "paso_6": False,
        "stats_gap": False
    }

    # PASO 1: Verificar scraper
    results["paso_1"] = execute_step(
        1,
        "scripts/start_scraper.py",
        "Verificar y arrancar scraper"
    )
    if not results["paso_1"]:
        print("\n[ALERTA] Paso 1 falló - El scraper puede no estar funcionando")

    # PASO 2: Buscar partidos
    results["paso_2"] = execute_step(
        2,
        "scripts/find_matches.py",
        "Buscar nuevos partidos en Betfair"
    )
    if not results["paso_2"]:
        print("\n[ALERTA] Paso 2 falló - No se pudieron buscar nuevos partidos")

    # PASO 3: Limpiar partidos viejos
    results["paso_3"] = execute_step(
        3,
        "scripts/clean_games.py",
        "Limpiar partidos terminados"
    )
    if not results["paso_3"]:
        print("\n[ALERTA] Paso 3 falló - Los partidos terminados no se limpiaron")

    # PASO 4: Verificar URLs
    results["paso_4"] = execute_step(
        4,
        "scripts/check_urls.py",
        "Verificar URLs y eliminar 404s"
    )
    if not results["paso_4"]:
        print("\n[ALERTA] Paso 4 falló - No se verificaron URLs")

    # PASO 5: Generar reporte
    results["paso_5"] = execute_step(
        5,
        "scripts/generate_report.py",
        "Generar reporte de supervisión"
    )
    if not results["paso_5"]:
        print("\n[ALERTA] Paso 5 falló - No se generó reporte")

    # PASO 6: Validar estadísticas (CRÍTICO)
    results["paso_6"] = execute_step(
        6,
        "scripts/validate_stats.py",
        "Validar estadísticas capturadas (OBLIGATORIO)"
    )
    if not results["paso_6"]:
        print("\n[ALERTA] Paso 6 falló - No se validaron estadísticas")

    # =========================================================================
    # RESUMEN FINAL
    # =========================================================================
    print_section("RESUMEN FINAL DE EJECUCIÓN")

    print("PASOS EJECUTADOS:")
    print(f"  PASO 1 (start_scraper.py):    {'[OK]' if results['paso_1'] else '[ERROR]'}")
    print(f"  PASO 2 (find_matches.py):     {'[OK]' if results['paso_2'] else '[ERROR]'}")
    print(f"  PASO 3 (clean_games.py):      {'[OK]' if results['paso_3'] else '[ERROR]'}")
    print(f"  PASO 4 (check_urls.py):       {'[OK]' if results['paso_4'] else '[ERROR]'}")
    print(f"  PASO 5 (generate_report.py):  {'[OK]' if results['paso_5'] else '[ERROR]'}")
    print(f"  PASO 6 (validate_stats.py):   {'[OK]' if results['paso_6'] else '[ERROR]'} [OBLIGATORIO]")

    print(f"\nFin: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Estado general
    all_critical_passed = results["paso_1"] and results["paso_6"]

    if all_critical_passed:
        print("\n[OK] Workflow completado - Sistema funcionando")
    else:
        print("\n[ALERTA] Workflow completado con problemas")
        if not results["paso_1"]:
            print("  - PASO 1: Scraper puede no estar corriendo")
        if not results["paso_6"]:
            print("  - PASO 6: Validación de estadísticas falló")

    print("\n" + "=" * 70 + "\n")


if __name__ == "__main__":
    main()
