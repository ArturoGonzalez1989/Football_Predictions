# -*- coding: utf-8 -*-
"""
Agente Supervisor Autónomo - Betfair Scraper
==============================================

Agente que monitoriza, gestiona y optimiza el scraper de forma autónoma.

Funcionalidades:
- Iniciar/parar el scraper automáticamente
- Descubrir partidos en vivo usando Playwright
- Gestionar games.csv (añadir/actualizar partidos)
- Verificar calidad de datos (cuotas, stats)
- Analizar logs y detectar errores
- Generar informes automáticos
- Aplicar correcciones sin intervención humana
"""

import sys
import io
import os
import time
import logging
import subprocess
import psutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import json

# Configurar encoding para Windows
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Importar módulos del supervisor
from supervisor_config import SupervisorConfig
from supervisor_utils import (
    LogAnalyzer,
    CSVManager,
    PlaywrightMatchFinder,
    DataQualityChecker,
    ReportGenerator,
    ScraperHealthMonitor
)


class SupervisorAgent:
    """Agente supervisor autónomo para el scraper de Betfair"""

    def __init__(self, config: SupervisorConfig):
        self.config = config
        self.scraper_process = None
        self.running = False

        # Inicializar componentes
        self.log_analyzer = LogAnalyzer(config)
        self.csv_manager = CSVManager(config)
        self.match_finder = PlaywrightMatchFinder(config)
        self.quality_checker = DataQualityChecker(config)
        self.report_generator = ReportGenerator(config)
        self.health_monitor = ScraperHealthMonitor(config)

        # Configurar logging del supervisor
        self.setup_logging()

        self.log.info("=" * 80)
        self.log.info("🤖 SUPERVISOR AGENT INICIADO")
        self.log.info("=" * 80)
        self.log.info(f"Directorio de trabajo: {config.BASE_DIR}")
        self.log.info(f"Script objetivo: {config.SCRAPER_SCRIPT}")
        self.log.info(f"Intervalo de chequeo: {config.CHECK_INTERVAL} segundos")
        self.log.info(f"Auto-descubrimiento: {'✓' if config.AUTO_DISCOVER_MATCHES else '✗'}")
        self.log.info(f"Auto-corrección: {'✓' if config.AUTO_CORRECT else '✗'}")
        self.log.info("=" * 80)

    def setup_logging(self):
        """Configurar sistema de logging del supervisor"""
        log_dir = self.config.BASE_DIR / "logs"
        log_dir.mkdir(exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = log_dir / f"supervisor_{timestamp}.log"

        # Crear logger
        self.log = logging.getLogger("SupervisorAgent")
        self.log.setLevel(logging.DEBUG if self.config.DEBUG else logging.INFO)

        # Handler para archivo
        fh = logging.FileHandler(log_file, encoding='utf-8')
        fh.setLevel(logging.DEBUG)

        # Handler para consola
        ch = logging.StreamHandler(sys.stdout)
        ch.setLevel(logging.INFO)

        # Formato
        formatter = logging.Formatter(
            '%(asctime)s | %(levelname)-8s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        fh.setFormatter(formatter)
        ch.setFormatter(formatter)

        self.log.addHandler(fh)
        self.log.addHandler(ch)

        self.log.info(f"Log del supervisor: {log_file}")

    def start_scraper(self) -> bool:
        """Iniciar el proceso del scraper"""
        if self.is_scraper_running():
            self.log.warning("⚠️ El scraper ya está en ejecución")
            return False

        try:
            self.log.info("🚀 Iniciando scraper...")

            # Construir comando
            cmd = [
                sys.executable,
                str(self.config.SCRAPER_SCRIPT),
                "--ventana-antes", str(self.config.SCRAPER_VENTANA_ANTES),
                "--ventana-despues", str(self.config.SCRAPER_VENTANA_DESPUES),
                "--ciclo", str(self.config.SCRAPER_CICLO),
            ]

            # Añadir argumentos adicionales si existen
            if self.config.SCRAPER_EXTRA_ARGS:
                cmd.extend(self.config.SCRAPER_EXTRA_ARGS)

            self.log.debug(f"Comando: {' '.join(cmd)}")

            # Iniciar proceso
            self.scraper_process = subprocess.Popen(
                cmd,
                cwd=self.config.BASE_DIR,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NEW_CONSOLE if sys.platform == "win32" else 0
            )

            # Esperar un poco para verificar que arrancó correctamente
            time.sleep(5)

            if self.scraper_process.poll() is None:
                self.log.info(f"✓ Scraper iniciado (PID: {self.scraper_process.pid})")
                return True
            else:
                self.log.error("✗ El scraper se cerró inmediatamente después de iniciar")
                return False

        except Exception as e:
            self.log.error(f"✗ Error al iniciar scraper: {e}")
            return False

    def stop_scraper(self) -> bool:
        """Detener el proceso del scraper"""
        if not self.is_scraper_running():
            self.log.warning("⚠️ El scraper no está en ejecución")
            return False

        try:
            self.log.info("🛑 Deteniendo scraper...")

            # Intentar detención suave primero
            if self.scraper_process:
                self.scraper_process.terminate()

                # Esperar hasta 30 segundos para que termine
                for _ in range(30):
                    if self.scraper_process.poll() is not None:
                        self.log.info("✓ Scraper detenido correctamente")
                        self.scraper_process = None
                        return True
                    time.sleep(1)

                # Si no terminó, forzar
                self.log.warning("Forzando detención del scraper...")
                self.scraper_process.kill()
                self.scraper_process = None
                self.log.info("✓ Scraper detenido (forzado)")
                return True

            # Si no tenemos referencia al proceso, buscar por nombre
            return self._kill_scraper_by_name()

        except Exception as e:
            self.log.error(f"✗ Error al detener scraper: {e}")
            return False

    def is_scraper_running(self) -> bool:
        """Verificar si el scraper está en ejecución"""
        # Verificar proceso guardado
        if self.scraper_process and self.scraper_process.poll() is None:
            return True

        # Buscar proceso por nombre
        script_name = self.config.SCRAPER_SCRIPT.name
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                cmdline = proc.info.get('cmdline', [])
                if cmdline and script_name in ' '.join(cmdline):
                    return True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        return False

    def _kill_scraper_by_name(self) -> bool:
        """Terminar proceso del scraper buscando por nombre"""
        script_name = self.config.SCRAPER_SCRIPT.name
        killed = False

        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                cmdline = proc.info.get('cmdline', [])
                if cmdline and script_name in ' '.join(cmdline):
                    self.log.info(f"Terminando proceso PID {proc.pid}")
                    proc.terminate()
                    proc.wait(timeout=10)
                    killed = True
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.TimeoutExpired):
                continue

        return killed

    def discover_live_matches(self) -> List[Dict]:
        """Descubrir partidos en vivo usando Playwright"""
        self.log.info("🔍 Buscando partidos en vivo...")

        try:
            matches = self.match_finder.find_live_matches()

            if matches:
                self.log.info(f"✓ Encontrados {len(matches)} partidos en vivo:")
                for match in matches:
                    self.log.info(f"   - {match['name']} (inicio: {match.get('start_time', 'ahora')})")
            else:
                self.log.info("No se encontraron partidos en vivo")

            return matches

        except Exception as e:
            self.log.error(f"✗ Error al buscar partidos: {e}")
            return []

    def sync_matches_to_csv(self, discovered_matches: List[Dict]) -> int:
        """Sincronizar partidos descubiertos con games.csv"""
        if not discovered_matches:
            return 0

        self.log.info("📝 Sincronizando partidos con games.csv...")

        try:
            added = self.csv_manager.add_missing_matches(discovered_matches)

            if added > 0:
                self.log.info(f"✓ Añadidos {added} partidos nuevos a games.csv")
            else:
                self.log.info("✓ Todos los partidos ya están en games.csv")

            return added

        except Exception as e:
            self.log.error(f"✗ Error al sincronizar CSV: {e}")
            return 0

    def verify_data_quality(self) -> Dict:
        """Verificar calidad de los datos capturados"""
        self.log.info("🔬 Verificando calidad de datos...")

        try:
            report = self.quality_checker.check_all()

            # Log resumen
            self.log.info("=" * 60)
            self.log.info("INFORME DE CALIDAD DE DATOS")
            self.log.info("=" * 60)

            if report['odds_ok']:
                self.log.info("✓ Cuotas: OK")
            else:
                self.log.warning(f"⚠️ Cuotas: {report['odds_issues']} problemas detectados")

            if report['stats_ok']:
                self.log.info("✓ Estadísticas: OK")
            else:
                self.log.warning(f"⚠️ Estadísticas: {report['stats_issues']} problemas detectados")

            if report['timestamps_ok']:
                self.log.info("✓ Timestamps: OK")
            else:
                self.log.warning(f"⚠️ Timestamps: {report['timestamp_issues']} problemas detectados")

            self.log.info(f"Cobertura estadísticas: {report['stats_coverage']:.1f}%")
            self.log.info(f"Filas verificadas: {report['total_rows']}")
            self.log.info("=" * 60)

            return report

        except Exception as e:
            self.log.error(f"✗ Error al verificar calidad: {e}")
            return {}

    def analyze_logs(self) -> Dict:
        """Analizar logs del scraper en busca de errores"""
        self.log.info("📊 Analizando logs del scraper...")

        try:
            analysis = self.log_analyzer.analyze_recent_logs()

            # Log resumen
            self.log.info("=" * 60)
            self.log.info("ANÁLISIS DE LOGS")
            self.log.info("=" * 60)
            self.log.info(f"Errores: {analysis['error_count']}")
            self.log.info(f"Warnings: {analysis['warning_count']}")
            self.log.info(f"Capturas exitosas: {analysis['capture_count']}")

            if analysis['common_errors']:
                self.log.warning("Errores más comunes:")
                for error, count in analysis['common_errors'][:5]:
                    self.log.warning(f"   - {error}: {count} ocurrencias")

            self.log.info("=" * 60)

            return analysis

        except Exception as e:
            self.log.error(f"✗ Error al analizar logs: {e}")
            return {}

    def check_health(self) -> Dict:
        """Verificar salud general del sistema"""
        self.log.info("❤️ Verificando salud del sistema...")

        try:
            health = self.health_monitor.check_health()

            # Log resumen
            self.log.info("=" * 60)
            self.log.info("HEALTH CHECK")
            self.log.info("=" * 60)
            self.log.info(f"Estado scraper: {'🟢 Running' if health['scraper_running'] else '🔴 Stopped'}")
            self.log.info(f"Uso CPU: {health['cpu_usage']:.1f}%")
            self.log.info(f"Uso RAM: {health['memory_usage']:.1f}%")
            self.log.info(f"Espacio disco: {health['disk_space_gb']:.1f} GB disponibles")
            self.log.info(f"Procesos Chrome: {health['chrome_processes']}")
            self.log.info(f"Última captura: {health['last_capture_time']}")
            self.log.info("=" * 60)

            # Alertas
            if health['cpu_usage'] > 80:
                self.log.warning("⚠️ ALERTA: Uso de CPU alto")

            if health['memory_usage'] > 80:
                self.log.warning("⚠️ ALERTA: Uso de RAM alto")

            if health['disk_space_gb'] < 5:
                self.log.warning("⚠️ ALERTA: Espacio en disco bajo")

            return health

        except Exception as e:
            self.log.error(f"✗ Error al verificar salud: {e}")
            return {}

    def apply_corrections(self, quality_report: Dict, log_analysis: Dict) -> bool:
        """Aplicar correcciones automáticas basadas en problemas detectados"""
        if not self.config.AUTO_CORRECT:
            self.log.info("Auto-corrección desactivada")
            return False

        self.log.info("🔧 Aplicando correcciones automáticas...")

        corrections_applied = False

        try:
            # Corrección 1: Reiniciar si hay muchos errores
            if log_analysis.get('error_count', 0) > 50:
                self.log.warning("Detectados muchos errores, reiniciando scraper...")
                self.stop_scraper()
                time.sleep(10)
                self.start_scraper()
                corrections_applied = True

            # Corrección 2: Limpiar procesos Chrome zombies
            chrome_count = psutil.Process(self.scraper_process.pid).num_threads() if self.scraper_process else 0
            if chrome_count > 50:
                self.log.warning("Detectados muchos procesos Chrome, reiniciando...")
                self.stop_scraper()
                self._kill_chrome_processes()
                time.sleep(10)
                self.start_scraper()
                corrections_applied = True

            # Corrección 3: Limpiar CSV de filas corruptas
            if not quality_report.get('timestamps_ok', True):
                self.log.info("Limpiando filas con timestamps inválidos...")
                self.csv_manager.clean_invalid_rows()
                corrections_applied = True

            if corrections_applied:
                self.log.info("✓ Correcciones aplicadas")
            else:
                self.log.info("✓ No se requieren correcciones")

            return corrections_applied

        except Exception as e:
            self.log.error(f"✗ Error al aplicar correcciones: {e}")
            return False

    def _kill_chrome_processes(self):
        """Terminar procesos Chrome zombies"""
        for proc in psutil.process_iter(['name']):
            try:
                if 'chrome' in proc.info['name'].lower():
                    proc.kill()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

    def generate_report(self, health: Dict, quality: Dict, logs: Dict) -> Path:
        """Generar informe completo"""
        self.log.info("📄 Generando informe...")

        try:
            report_path = self.report_generator.generate_report(
                health_data=health,
                quality_data=quality,
                log_analysis=logs
            )

            self.log.info(f"✓ Informe generado: {report_path}")
            return report_path

        except Exception as e:
            self.log.error(f"✗ Error al generar informe: {e}")
            return None

    def run_cycle(self):
        """Ejecutar un ciclo completo de supervisión"""
        self.log.info("")
        self.log.info("=" * 80)
        self.log.info(f"🔄 CICLO DE SUPERVISIÓN - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        self.log.info("=" * 80)

        # 1. Verificar que el scraper esté corriendo
        if not self.is_scraper_running():
            self.log.warning("⚠️ Scraper no está corriendo")
            if self.config.AUTO_START_SCRAPER:
                self.start_scraper()

        # 2. Descubrir partidos en vivo (si está activado)
        if self.config.AUTO_DISCOVER_MATCHES:
            discovered = self.discover_live_matches()
            if discovered:
                added = self.sync_matches_to_csv(discovered)
                if added > 0 and self.is_scraper_running():
                    self.log.info("Reiniciando scraper para cargar nuevos partidos...")
                    self.stop_scraper()
                    time.sleep(5)
                    self.start_scraper()

        # 3. Health check
        health = self.check_health()

        # 4. Verificar calidad de datos
        quality = self.verify_data_quality()

        # 5. Analizar logs
        logs = self.analyze_logs()

        # 6. Aplicar correcciones si es necesario
        self.apply_corrections(quality, logs)

        # 7. Generar informe (cada N ciclos)
        if not hasattr(self, '_cycle_count'):
            self._cycle_count = 0
        self._cycle_count += 1

        if self._cycle_count % self.config.REPORT_INTERVAL == 0:
            self.generate_report(health, quality, logs)

        self.log.info("=" * 80)
        self.log.info(f"✓ Ciclo completado. Próximo ciclo en {self.config.CHECK_INTERVAL} segundos")
        self.log.info("=" * 80)

    def run(self):
        """Loop principal del supervisor"""
        self.running = True

        try:
            # Iniciar scraper si está configurado
            if self.config.AUTO_START_SCRAPER and not self.is_scraper_running():
                self.start_scraper()

            # Loop principal
            while self.running:
                try:
                    self.run_cycle()
                    time.sleep(self.config.CHECK_INTERVAL)

                except KeyboardInterrupt:
                    self.log.info("\n⚠️ Interrupción recibida")
                    break

                except Exception as e:
                    self.log.error(f"✗ Error en ciclo de supervisión: {e}")
                    self.log.error("Esperando antes de reintentar...")
                    time.sleep(60)

        finally:
            self.shutdown()

    def shutdown(self):
        """Apagar supervisor y limpiar recursos"""
        self.log.info("")
        self.log.info("=" * 80)
        self.log.info("🛑 APAGANDO SUPERVISOR")
        self.log.info("=" * 80)

        self.running = False

        # Detener scraper si está configurado
        if self.config.STOP_SCRAPER_ON_EXIT and self.is_scraper_running():
            self.log.info("Deteniendo scraper antes de salir...")
            self.stop_scraper()

        # Cerrar Playwright
        if hasattr(self, 'match_finder'):
            self.match_finder.close()

        self.log.info("✓ Supervisor apagado correctamente")
        self.log.info("=" * 80)


def main():
    """Punto de entrada principal"""
    # Cargar configuración
    config = SupervisorConfig.from_file("supervisor_config.json")

    # Crear y ejecutar supervisor
    supervisor = SupervisorAgent(config)
    supervisor.run()


if __name__ == "__main__":
    main()
