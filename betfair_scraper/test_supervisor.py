# -*- coding: utf-8 -*-
"""
Test de Instalación del Supervisor Agent
"""

import sys
import io
from pathlib import Path

# Configurar encoding para Windows
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

def test_imports():
    """Test de importación de módulos"""
    print("=" * 60)
    print("TEST 1: Importación de Módulos")
    print("=" * 60)

    try:
        import pandas
        print("✓ pandas instalado")
    except ImportError:
        print("✗ pandas NO instalado - ejecuta: pip install pandas")
        return False

    try:
        import psutil
        print("✓ psutil instalado")
    except ImportError:
        print("✗ psutil NO instalado - ejecuta: pip install psutil")
        return False

    try:
        from playwright.sync_api import sync_playwright
        print("✓ playwright instalado")
    except ImportError:
        print("✗ playwright NO instalado - ejecuta: pip install playwright")
        print("  Luego ejecuta: playwright install chromium")
        return False

    print()
    return True


def test_supervisor_files():
    """Test de archivos del supervisor"""
    print("=" * 60)
    print("TEST 2: Archivos del Supervisor")
    print("=" * 60)

    required_files = [
        "supervisor_agent.py",
        "supervisor_config.py",
        "supervisor_utils.py",
        "supervisor_config.json"
    ]

    all_ok = True
    for file_name in required_files:
        file_path = Path(file_name)
        if file_path.exists():
            print(f"✓ {file_name} existe")
        else:
            print(f"✗ {file_name} NO existe")
            all_ok = False

    print()
    return all_ok


def test_configuration():
    """Test de configuración"""
    print("=" * 60)
    print("TEST 3: Configuración")
    print("=" * 60)

    try:
        from supervisor_config import SupervisorConfig

        config = SupervisorConfig.from_file("supervisor_config.json")

        print(f"✓ Configuración cargada correctamente")
        print(f"  BASE_DIR: {config.BASE_DIR}")
        print(f"  SCRAPER_SCRIPT: {config.SCRAPER_SCRIPT}")

        # Verificar que el scraper existe
        if config.SCRAPER_SCRIPT.exists():
            print(f"✓ Scraper script existe: {config.SCRAPER_SCRIPT}")
        else:
            print(f"✗ Scraper script NO existe: {config.SCRAPER_SCRIPT}")
            print(f"  Ajusta la ruta en supervisor_config.json")
            return False

        # Verificar games.csv
        if config.GAMES_CSV.exists():
            print(f"✓ games.csv existe: {config.GAMES_CSV}")
        else:
            print(f"⚠️ games.csv NO existe (se creará automáticamente)")

        # Verificar directorios
        if config.LOGS_DIR.exists():
            print(f"✓ Directorio logs existe: {config.LOGS_DIR}")
        else:
            print(f"⚠️ Directorio logs NO existe (se creará automáticamente)")

        if config.REPORTS_DIR.exists():
            print(f"✓ Directorio reports existe: {config.REPORTS_DIR}")
        else:
            print(f"⚠️ Directorio reports NO existe (se creará automáticamente)")

        print()
        return True

    except Exception as e:
        print(f"✗ Error al cargar configuración: {e}")
        print()
        return False


def test_supervisor_modules():
    """Test de módulos del supervisor"""
    print("=" * 60)
    print("TEST 4: Módulos del Supervisor")
    print("=" * 60)

    try:
        from supervisor_config import SupervisorConfig
        print("✓ supervisor_config importado correctamente")

        from supervisor_utils import (
            LogAnalyzer,
            CSVManager,
            PlaywrightMatchFinder,
            DataQualityChecker,
            ReportGenerator,
            ScraperHealthMonitor
        )
        print("✓ supervisor_utils importado correctamente")
        print("  - LogAnalyzer")
        print("  - CSVManager")
        print("  - PlaywrightMatchFinder")
        print("  - DataQualityChecker")
        print("  - ReportGenerator")
        print("  - ScraperHealthMonitor")

        print()
        return True

    except Exception as e:
        print(f"✗ Error al importar módulos: {e}")
        print()
        return False


def main():
    """Ejecutar todos los tests"""
    print()
    print("=" * 60)
    print("TEST DE INSTALACIÓN - SUPERVISOR AGENT")
    print("=" * 60)
    print()

    results = []

    # Test 1: Importación de módulos
    results.append(test_imports())

    # Test 2: Archivos del supervisor
    results.append(test_supervisor_files())

    # Test 3: Configuración
    results.append(test_configuration())

    # Test 4: Módulos del supervisor
    results.append(test_supervisor_modules())

    # Resultado final
    print("=" * 60)
    print("RESULTADO FINAL")
    print("=" * 60)

    if all(results):
        print("✓ TODOS LOS TESTS PASARON")
        print()
        print("El supervisor está listo para usarse:")
        print("  python supervisor_agent.py")
        print()
        print("=" * 60)
        return 0
    else:
        print("✗ ALGUNOS TESTS FALLARON")
        print()
        print("Por favor, corrige los errores antes de continuar.")
        print("Consulta SUPERVISOR_QUICKSTART.md para más información.")
        print()
        print("=" * 60)
        return 1


if __name__ == "__main__":
    sys.exit(main())
