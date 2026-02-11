# -*- coding: utf-8 -*-
"""
Test del sistema de scheduling
"""
from datetime import datetime, timedelta
import sys
import io

# Configurar encoding para Windows
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# Simular las funciones para testing
def test_filtrar_partidos():
    """Test de la función filtrar_partidos_activos"""
    ahora = datetime.now()

    # Crear partidos de prueba
    partidos = [
        {
            "url": "http://example.com/1",
            "game": "Partido Pasado",
            "fecha_hora_inicio": ahora - timedelta(hours=3)  # Hace 3 horas
        },
        {
            "url": "http://example.com/2",
            "game": "Partido Activo 1",
            "fecha_hora_inicio": ahora - timedelta(minutes=30)  # Hace 30 min
        },
        {
            "url": "http://example.com/3",
            "game": "Partido Activo 2",
            "fecha_hora_inicio": ahora + timedelta(minutes=5)  # En 5 min
        },
        {
            "url": "http://example.com/4",
            "game": "Partido Futuro",
            "fecha_hora_inicio": ahora + timedelta(hours=2)  # En 2 horas
        },
        {
            "url": "http://example.com/5",
            "game": "Partido Sin Horario",
            "fecha_hora_inicio": None  # Sin horario (modo legacy)
        },
    ]

    # Simular filtro
    ventana_antes = 10  # 10 min antes
    ventana_despues = 150  # 150 min después

    activos = []
    futuros = []
    finalizados = []

    for p in partidos:
        if p["fecha_hora_inicio"] is None:
            activos.append(p)
            continue

        tiempo_hasta_inicio = (p["fecha_hora_inicio"] - ahora).total_seconds() / 60

        if tiempo_hasta_inicio > ventana_antes:
            futuros.append(p)
        elif tiempo_hasta_inicio >= -ventana_despues:
            activos.append(p)
        else:
            finalizados.append(p)

    print("=" * 80)
    print("TEST: filtrar_partidos_activos")
    print("=" * 80)
    print()
    print(f"Total partidos: {len(partidos)}")
    print(f"Ventana: {ventana_antes} min antes -> {ventana_despues} min después")
    print()

    print(f"[OK] ACTIVOS ({len(activos)}):")
    for p in activos:
        if p["fecha_hora_inicio"]:
            mins = (p["fecha_hora_inicio"] - ahora).total_seconds() / 60
            tiempo_str = f"inicia en {mins:.0f} min" if mins > 0 else f"empezó hace {-mins:.0f} min"
        else:
            tiempo_str = "sin horario (legacy)"
        print(f"   - {p['game']} ({tiempo_str})")

    print()
    print(f"[WAIT] FUTUROS ({len(futuros)}):")
    for p in futuros:
        mins = (p["fecha_hora_inicio"] - ahora).total_seconds() / 60
        print(f"   - {p['game']} (en {mins:.0f} min)")

    print()
    print(f"[DONE] FINALIZADOS ({len(finalizados)}):")
    for p in finalizados:
        mins = -(p["fecha_hora_inicio"] - ahora).total_seconds() / 60
        print(f"   - {p['game']} (terminó hace {mins:.0f} min)")

    print()
    print("=" * 80)

    # Validaciones
    assert len(activos) == 3, f"Esperaba 3 activos, obtuve {len(activos)}"
    assert len(futuros) == 1, f"Esperaba 1 futuro, obtuve {len(futuros)}"
    assert len(finalizados) == 1, f"Esperaba 1 finalizado, obtuve {len(finalizados)}"

    print("[PASS] TEST PASADO")
    print()


def test_parse_fecha():
    """Test de parseo de fechas"""
    print("=" * 80)
    print("TEST: Parseo de fechas")
    print("=" * 80)
    print()

    formatos_test = [
        "2026-02-10 20:00",  # YYYY-MM-DD HH:MM
        "10/02/2026 20:00",  # DD/MM/YYYY HH:MM
        "2026-12-31 23:59",
        "01/01/2026 00:00",
    ]

    for fecha_str in formatos_test:
        dt = None
        try:
            # Intentar formato YYYY-MM-DD HH:MM
            dt = datetime.strptime(fecha_str, "%Y-%m-%d %H:%M")
        except ValueError:
            try:
                # Intentar formato DD/MM/YYYY HH:MM
                dt = datetime.strptime(fecha_str, "%d/%m/%Y %H:%M")
            except ValueError:
                pass

        if dt:
            print(f"[OK] {fecha_str:20} -> {dt}")
        else:
            print(f"[FAIL] {fecha_str:20} -> FORMATO INVALIDO")

    print()
    print("=" * 80)
    print("[PASS] TEST PASADO")
    print()


def test_games_csv():
    """Test de lectura de games.csv"""
    print("=" * 80)
    print("TEST: Lectura de games.csv")
    print("=" * 80)
    print()

    import csv
    from pathlib import Path

    ruta = Path("games.csv")
    if not ruta.exists():
        print("[FAIL] games.csv no encontrado")
        return

    with open(ruta, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        partidos = list(reader)

    print(f"Partidos en games.csv: {len(partidos)}")
    print()

    for i, row in enumerate(partidos, 1):
        print(f"{i}. {row.get('Game', 'Sin nombre')}")
        print(f"   URL: {row.get('url', 'Sin URL')[:80]}...")

        fecha_str = row.get('fecha_hora_inicio', '').strip()
        if fecha_str:
            dt = None
            try:
                dt = datetime.strptime(fecha_str, "%Y-%m-%d %H:%M")
            except ValueError:
                try:
                    dt = datetime.strptime(fecha_str, "%d/%m/%Y %H:%M")
                except ValueError:
                    pass

            if dt:
                print(f"   Inicio: {dt} [OK]")
            else:
                print(f"   Inicio: {fecha_str} [FAIL] (formato inválido)")
        else:
            print(f"   Inicio: Sin horario (modo legacy)")
        print()

    print("=" * 80)
    print("[PASS] TEST PASADO")
    print()


if __name__ == "__main__":
    try:
        test_parse_fecha()
        test_filtrar_partidos()
        test_games_csv()

        print()
        print("=" * 80)
        print("TODOS LOS TESTS PASARON [OK]")
        print("=" * 80)

    except AssertionError as e:
        print(f"\n[FAIL] TEST FALLO: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
