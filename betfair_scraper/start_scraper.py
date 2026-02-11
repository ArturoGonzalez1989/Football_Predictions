#!/usr/bin/env python3
"""
Script para verificar y arrancar el scraper
Verifica si main.py está corriendo, lo arranca si está parado
y reporta su estado de salud
"""

import subprocess
import time
import psutil
import sys
from pathlib import Path
from datetime import datetime

# Configuración
SCRAPER_SCRIPT = Path("main.py")
MIN_ACTIVITY_THRESHOLD = 5 * 60  # 5 minutos en segundos


def check_scraper_running():
    """Verifica si main.py está en ejecución"""
    try:
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                cmdline = proc.info.get('cmdline', [])
                if cmdline and 'main.py' in ' '.join(cmdline):
                    return True, proc.pid
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
    except Exception as e:
        print(f"[ERROR] Error verificando procesos: {e}")

    return False, None


def get_latest_log():
    """Obtiene el log más reciente del scraper"""
    logs_dir = Path("logs")
    if not logs_dir.exists():
        return None

    log_files = sorted(logs_dir.glob("scraper_*.log"), key=lambda x: x.stat().st_mtime, reverse=True)
    return log_files[0] if log_files else None


def get_last_activity_time(log_file):
    """Obtiene el timestamp de la última línea del log"""
    try:
        with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
            if lines:
                last_line = lines[-1]
                # Intenta extraer timestamp del formato: YYYY-MM-DD HH:MM:SS
                if len(last_line) > 19:
                    timestamp_str = last_line[:19]
                    try:
                        last_time = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
                        return last_time
                    except:
                        pass
    except Exception as e:
        print(f"[DEBUG] Error leyendo log: {e}")

    return None


def check_recent_errors(log_file):
    """Verifica si hay errores recientes en el log"""
    try:
        with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
            # Revisar últimas 50 líneas
            recent_lines = lines[-50:] if len(lines) > 50 else lines

            error_count = 0
            for line in recent_lines:
                if "[ERROR]" in line or "[WARNING]" in line:
                    error_count += 1

            return error_count
    except Exception as e:
        print(f"[DEBUG] Error analizando log: {e}")

    return 0


def start_scraper():
    """Inicia el proceso del scraper"""
    try:
        print("[INFO] Arrancando scraper...")

        # Comando para arrancar en background (Windows compatible)
        cmd = [sys.executable, str(SCRAPER_SCRIPT)]

        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NEW_CONSOLE if sys.platform == "win32" else 0
        )

        # Esperar a que se estabilice
        time.sleep(3)

        # Verificar que se inició
        if proc.poll() is None:
            print(f"[OK] Scraper arrancado (PID: {proc.pid})")
            return True
        else:
            print("[ERROR] El scraper se cerró inmediatamente")
            return False

    except Exception as e:
        print(f"[ERROR] Error arrancando scraper: {e}")
        return False


def restart_scraper():
    """Detiene y reinicia el scraper"""
    try:
        print("[WARNING] Reiniciando scraper...")

        # Matar procesos de main.py
        for proc in psutil.process_iter(['pid', 'cmdline']):
            try:
                cmdline = proc.info.get('cmdline', [])
                if cmdline and 'main.py' in ' '.join(cmdline):
                    proc.kill()
                    print(f"[DEBUG] Proceso terminado: {proc.pid}")
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        time.sleep(2)

        # Reiniciar
        return start_scraper()

    except Exception as e:
        print(f"[ERROR] Error reiniciando scraper: {e}")
        return False


def main():
    """Función principal"""
    print("\n" + "="*60)
    print("VERIFICACION Y CONTROL DEL SCRAPER")
    print("="*60)

    # Verificar si está corriendo
    is_running, pid = check_scraper_running()

    if is_running:
        print(f"[OK] Scraper está corriendo (PID: {pid})")

        # Verificar salud
        log_file = get_latest_log()
        if log_file:
            print(f"[INFO] Log: {log_file.name}")

            # Verificar actividad reciente
            last_activity = get_last_activity_time(log_file)
            if last_activity:
                elapsed = (datetime.now() - last_activity).total_seconds()
                print(f"[INFO] Última actividad hace {elapsed:.0f} segundos")

                if elapsed > MIN_ACTIVITY_THRESHOLD:
                    print(f"[WARNING] Scraper lleva {elapsed:.0f}s sin actividad")
                    error_count = check_recent_errors(log_file)
                    if error_count > 5:
                        print(f"[WARNING] Detectados {error_count} errores/warnings recientemente")
                        print("[ACTION] Reiniciando scraper...")
                        if restart_scraper():
                            print("[OK] Scraper reiniciado exitosamente")
                        else:
                            print("[ERROR] Fallo al reiniciar")
                    else:
                        print("[OK] Pocos errores, scraper probablemente congestionado")
                else:
                    print("[OK] Scraper activo")
            else:
                print("[WARNING] No se puede determinar última actividad")
        else:
            print("[WARNING] No se encontró log del scraper")

    else:
        print("[WARNING] Scraper NO está corriendo")
        print("[ACTION] Arrancando scraper...")

        if start_scraper():
            print("[OK] Scraper iniciado")
            time.sleep(5)

            # Verificar que se inició correctamente
            log_file = get_latest_log()
            if log_file:
                log_time = datetime.fromtimestamp(log_file.stat().st_mtime)
                if (datetime.now() - log_time).total_seconds() < 10:
                    print("[OK] Log reciente encontrado - Inicio exitoso")
                else:
                    print("[WARNING] No hay log reciente")
        else:
            print("[ERROR] Fallo al arrancar scraper")

    print("="*60 + "\n")


if __name__ == "__main__":
    main()
