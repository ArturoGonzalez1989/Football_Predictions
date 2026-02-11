# -*- coding: utf-8 -*-
"""
Utilidades del Supervisor Agent
"""

import re
import csv
import psutil
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from collections import Counter
import logging


class LogAnalyzer:
    """Analizador de logs del scraper"""

    def __init__(self, config):
        self.config = config
        self.log = logging.getLogger("LogAnalyzer")

    def analyze_recent_logs(self, hours: int = 1) -> Dict:
        """Analizar logs recientes"""
        logs_dir = self.config.LOGS_DIR
        cutoff_time = datetime.now() - timedelta(hours=hours)

        error_count = 0
        warning_count = 0
        capture_count = 0
        errors = []

        # Buscar archivos de log recientes
        log_files = sorted(logs_dir.glob("scraper_*.log"), reverse=True)[:5]

        for log_file in log_files:
            # Verificar si el archivo es reciente
            file_time = datetime.fromtimestamp(log_file.stat().st_mtime)
            if file_time < cutoff_time:
                continue

            try:
                with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                    for line in f:
                        line_lower = line.lower()

                        if 'error' in line_lower:
                            error_count += 1
                            # Extraer mensaje de error
                            match = re.search(r'error[:\s]+(.+?)(?:\n|$)', line, re.IGNORECASE)
                            if match:
                                errors.append(match.group(1).strip())

                        if 'warning' in line_lower:
                            warning_count += 1

                        if 'captura exitosa' in line_lower or 'datos guardados' in line_lower:
                            capture_count += 1

            except Exception as e:
                self.log.error(f"Error al leer log {log_file}: {e}")

        # Contar errores más comunes
        common_errors = Counter(errors).most_common(10)

        return {
            'error_count': error_count,
            'warning_count': warning_count,
            'capture_count': capture_count,
            'common_errors': common_errors,
            'analyzed_files': len(log_files)
        }

    def get_last_capture_time(self) -> Optional[datetime]:
        """Obtener timestamp de la última captura exitosa"""
        logs_dir = self.config.LOGS_DIR
        log_files = sorted(logs_dir.glob("scraper_*.log"), reverse=True)[:3]

        for log_file in log_files:
            try:
                with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                    for line in reversed(list(f)):
                        if 'captura exitosa' in line.lower() or 'datos guardados' in line.lower():
                            # Extraer timestamp
                            match = re.search(r'(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})', line)
                            if match:
                                return datetime.strptime(match.group(1), '%Y-%m-%d %H:%M:%S')
            except Exception:
                continue

        return None


class CSVManager:
    """Gestor de games.csv y archivos de salida"""

    def __init__(self, config):
        self.config = config
        self.log = logging.getLogger("CSVManager")

    def read_games_csv(self) -> List[Dict]:
        """Leer games.csv"""
        games = []

        if not self.config.GAMES_CSV.exists():
            self.log.warning(f"games.csv no encontrado: {self.config.GAMES_CSV}")
            return games

        try:
            with open(self.config.GAMES_CSV, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                games = list(reader)

            return games

        except Exception as e:
            self.log.error(f"Error al leer games.csv: {e}")
            return []

    def write_games_csv(self, games: List[Dict]):
        """Escribir games.csv"""
        if not games:
            return

        try:
            fieldnames = list(games[0].keys())

            with open(self.config.GAMES_CSV, 'w', encoding='utf-8', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(games)

            self.log.info(f"✓ games.csv actualizado ({len(games)} partidos)")

        except Exception as e:
            self.log.error(f"Error al escribir games.csv: {e}")

    def add_missing_matches(self, new_matches: List[Dict]) -> int:
        """Añadir partidos que faltan en games.csv"""
        current_games = self.read_games_csv()
        current_urls = {game.get('url', '') for game in current_games}

        added_count = 0

        for match in new_matches:
            url = match.get('url', '')
            if url and url not in current_urls:
                # Añadir partido
                game_entry = {
                    'Game': match.get('name', 'Unknown'),
                    'url': url,
                    'fecha_hora_inicio': match.get('start_time', '')
                }
                current_games.append(game_entry)
                added_count += 1
                self.log.info(f"➕ Añadido: {game_entry['Game']}")

        if added_count > 0:
            self.write_games_csv(current_games)

        return added_count

    def remove_finished_matches(self, hours_threshold: int = 3) -> int:
        """Eliminar partidos que terminaron hace más de X horas"""
        games = self.read_games_csv()
        now = datetime.now()
        removed_count = 0

        filtered_games = []

        for game in games:
            fecha_str = game.get('fecha_hora_inicio', '').strip()

            if not fecha_str:
                # Sin horario, mantener
                filtered_games.append(game)
                continue

            try:
                # Parsear fecha
                dt = None
                for fmt in ['%Y-%m-%d %H:%M', '%d/%m/%Y %H:%M']:
                    try:
                        dt = datetime.strptime(fecha_str, fmt)
                        break
                    except ValueError:
                        continue

                if dt:
                    # Calcular tiempo desde el inicio
                    elapsed = (now - dt).total_seconds() / 3600

                    if elapsed > hours_threshold:
                        self.log.info(f"🗑️ Removiendo partido finalizado: {game.get('Game')}")
                        removed_count += 1
                    else:
                        filtered_games.append(game)
                else:
                    filtered_games.append(game)

            except Exception:
                filtered_games.append(game)

        if removed_count > 0:
            self.write_games_csv(filtered_games)

        return removed_count

    def clean_invalid_rows(self):
        """Limpiar filas inválidas de CSVs de salida"""
        output_files = list(self.config.BASE_DIR.glob(self.config.OUTPUT_CSV_PATTERN))

        for csv_file in output_files:
            try:
                df = pd.read_csv(csv_file, encoding='utf-8')
                original_len = len(df)

                # Eliminar filas con timestamp inválido
                df = df[pd.to_datetime(df['timestamp'], errors='coerce').notna()]

                cleaned_len = len(df)
                removed = original_len - cleaned_len

                if removed > 0:
                    df.to_csv(csv_file, index=False, encoding='utf-8')
                    self.log.info(f"✓ Limpiadas {removed} filas de {csv_file.name}")

            except Exception as e:
                self.log.error(f"Error al limpiar {csv_file}: {e}")

    def get_latest_output_csv(self) -> Optional[Path]:
        """Obtener el CSV de salida más reciente"""
        output_files = sorted(
            self.config.BASE_DIR.glob(self.config.OUTPUT_CSV_PATTERN),
            key=lambda p: p.stat().st_mtime,
            reverse=True
        )

        return output_files[0] if output_files else None


class PlaywrightMatchFinder:
    """Buscador de partidos usando Playwright"""

    def __init__(self, config):
        self.config = config
        self.log = logging.getLogger("MatchFinder")
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None

    def _init_browser(self):
        """Inicializar navegador Playwright"""
        if self.playwright:
            return

        try:
            from playwright.sync_api import sync_playwright

            self.playwright = sync_playwright().start()
            self.browser = self.playwright.chromium.launch(headless=self.config.HEADLESS_BROWSER)
            self.context = self.browser.new_context(locale='es-ES')
            self.page = self.context.new_page()
            self.page.set_default_timeout(self.config.BROWSER_TIMEOUT)

            self.log.info("✓ Navegador Playwright inicializado")

        except Exception as e:
            self.log.error(f"Error al inicializar Playwright: {e}")
            raise

    def find_live_matches(self) -> List[Dict]:
        """Buscar partidos en vivo en Betfair"""
        self._init_browser()

        matches = []

        try:
            self.log.info(f"Navegando a: {self.config.BETFAIR_INPLAY_URL}")
            self.page.goto(self.config.BETFAIR_INPLAY_URL, wait_until='networkidle')

            # Esperar a que carguen los partidos
            self.page.wait_for_timeout(3000)

            # Buscar elementos de partidos en vivo
            # Estructura típica de Betfair: elementos con clase que contiene "event"
            match_elements = self.page.query_selector_all('[class*="event"]')

            for element in match_elements[:20]:  # Limitar a 20 primeros
                try:
                    # Extraer nombre del partido
                    name_elem = element.query_selector('[class*="team"], [class*="name"]')
                    if not name_elem:
                        continue

                    name = name_elem.inner_text().strip()

                    # Extraer URL
                    link_elem = element.query_selector('a[href*="/market/"]')
                    if not link_elem:
                        continue

                    href = link_elem.get_attribute('href')
                    if not href:
                        continue

                    url = href if href.startswith('http') else f"https://www.betfair.es{href}"

                    # Extraer hora de inicio (si está disponible)
                    time_elem = element.query_selector('[class*="time"], [class*="clock"]')
                    start_time = time_elem.inner_text().strip() if time_elem else "En vivo"

                    matches.append({
                        'name': name,
                        'url': url,
                        'start_time': start_time,
                        'status': 'live'
                    })

                except Exception as e:
                    self.log.debug(f"Error al procesar elemento: {e}")
                    continue

            self.log.info(f"✓ Encontrados {len(matches)} partidos en vivo")

        except Exception as e:
            self.log.error(f"Error al buscar partidos: {e}")

        return matches

    def close(self):
        """Cerrar navegador"""
        try:
            if self.page:
                self.page.close()
            if self.context:
                self.context.close()
            if self.browser:
                self.browser.close()
            if self.playwright:
                self.playwright.stop()

            self.log.info("✓ Navegador Playwright cerrado")

        except Exception as e:
            self.log.error(f"Error al cerrar navegador: {e}")


class DataQualityChecker:
    """Verificador de calidad de datos capturados"""

    def __init__(self, config):
        self.config = config
        self.log = logging.getLogger("QualityChecker")

    def check_all(self) -> Dict:
        """Verificar calidad de todos los aspectos"""
        csv_file = CSVManager(self.config).get_latest_output_csv()

        if not csv_file or not csv_file.exists():
            self.log.warning("No se encontró CSV de salida")
            return {
                'odds_ok': False,
                'stats_ok': False,
                'timestamps_ok': False,
                'stats_coverage': 0.0,
                'total_rows': 0,
                'odds_issues': 0,
                'stats_issues': 0,
                'timestamp_issues': 0
            }

        try:
            df = pd.read_csv(csv_file, encoding='utf-8')

            odds_check = self._check_odds(df)
            stats_check = self._check_stats(df)
            timestamp_check = self._check_timestamps(df)

            return {
                'odds_ok': odds_check['ok'],
                'stats_ok': stats_check['ok'],
                'timestamps_ok': timestamp_check['ok'],
                'stats_coverage': stats_check['coverage'],
                'total_rows': len(df),
                'odds_issues': odds_check['issues'],
                'stats_issues': stats_check['issues'],
                'timestamp_issues': timestamp_check['issues']
            }

        except Exception as e:
            self.log.error(f"Error al verificar calidad: {e}")
            return {}

    def _check_odds(self, df: pd.DataFrame) -> Dict:
        """Verificar calidad de cuotas"""
        issues = 0

        # Columnas de cuotas principales
        odds_cols = ['local_odds', 'draw_odds', 'visitante_odds']

        for col in odds_cols:
            if col in df.columns:
                # Verificar valores nulos
                null_count = df[col].isna().sum()
                if null_count > len(df) * 0.1:  # > 10% nulos
                    issues += 1

                # Verificar valores fuera de rango razonable (1.01 - 1000)
                valid_values = df[col].dropna()
                if len(valid_values) > 0:
                    out_of_range = ((valid_values < 1.01) | (valid_values > 1000)).sum()
                    if out_of_range > 0:
                        issues += out_of_range

        return {
            'ok': issues == 0,
            'issues': issues
        }

    def _check_stats(self, df: pd.DataFrame) -> Dict:
        """Verificar calidad de estadísticas"""
        issues = 0

        # Columnas de stats importantes
        important_stats = [
            'corners_local', 'corners_visitante',
            'tiros_puerta_local', 'tiros_puerta_visitante',
            'posesion_local', 'posesion_visitante'
        ]

        total_stat_cols = 0
        filled_stat_cols = 0

        for col in df.columns:
            # Buscar columnas de estadísticas (terminan en _local o _visitante)
            if col.endswith('_local') or col.endswith('_visitante'):
                total_stat_cols += 1

                # Contar valores no nulos
                non_null = df[col].notna().sum()
                if non_null > len(df) * 0.1:  # Si > 10% tienen datos
                    filled_stat_cols += 1

        # Calcular cobertura
        coverage = (filled_stat_cols / total_stat_cols * 100) if total_stat_cols > 0 else 0

        # Verificar columnas importantes
        for col in important_stats:
            if col in df.columns:
                null_pct = df[col].isna().sum() / len(df) * 100
                if null_pct > self.config.MAX_NULL_PERCENTAGE:
                    issues += 1

        return {
            'ok': coverage >= self.config.MIN_STATS_COVERAGE and issues == 0,
            'coverage': coverage,
            'issues': issues
        }

    def _check_timestamps(self, df: pd.DataFrame) -> Dict:
        """Verificar validez de timestamps"""
        issues = 0

        if 'timestamp' in df.columns:
            # Intentar parsear timestamps
            try:
                timestamps = pd.to_datetime(df['timestamp'], errors='coerce')
                invalid_count = timestamps.isna().sum()
                issues = invalid_count

                # Verificar que timestamps sean recientes (últimos 7 días)
                if len(timestamps.dropna()) > 0:
                    now = pd.Timestamp.now()
                    week_ago = now - pd.Timedelta(days=7)
                    old_timestamps = (timestamps < week_ago).sum()
                    # No contar como issue si son datos históricos

            except Exception:
                issues += len(df)

        return {
            'ok': issues == 0,
            'issues': issues
        }


class ReportGenerator:
    """Generador de informes del supervisor"""

    def __init__(self, config):
        self.config = config
        self.log = logging.getLogger("ReportGenerator")

    def generate_report(self, health_data: Dict, quality_data: Dict, log_analysis: Dict) -> Path:
        """Generar informe completo en formato Markdown"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = self.config.REPORTS_DIR / f"supervisor_report_{timestamp}.md"

        try:
            with open(report_file, 'w', encoding='utf-8') as f:
                f.write(f"# Informe del Supervisor\n\n")
                f.write(f"**Fecha**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                f.write("---\n\n")

                # Sección Health
                f.write("## Estado del Sistema\n\n")
                f.write(f"- **Scraper**: {'🟢 Running' if health_data.get('scraper_running') else '🔴 Stopped'}\n")
                f.write(f"- **CPU**: {health_data.get('cpu_usage', 0):.1f}%\n")
                f.write(f"- **RAM**: {health_data.get('memory_usage', 0):.1f}%\n")
                f.write(f"- **Disco libre**: {health_data.get('disk_space_gb', 0):.1f} GB\n")
                f.write(f"- **Procesos Chrome**: {health_data.get('chrome_processes', 0)}\n")
                f.write(f"- **Última captura**: {health_data.get('last_capture_time', 'N/A')}\n\n")

                # Sección Calidad
                f.write("## Calidad de Datos\n\n")

                # Cuotas
                if quality_data.get('odds_ok'):
                    f.write("- **Cuotas**: ✓ OK\n")
                else:
                    f.write(f"- **Cuotas**: ✗ {quality_data.get('odds_issues', 0)} problemas\n")

                # Estadísticas
                if quality_data.get('stats_ok'):
                    f.write("- **Estadísticas**: ✓ OK\n")
                else:
                    f.write(f"- **Estadísticas**: ✗ {quality_data.get('stats_issues', 0)} problemas\n")

                # Timestamps
                if quality_data.get('timestamps_ok'):
                    f.write("- **Timestamps**: ✓ OK\n")
                else:
                    f.write(f"- **Timestamps**: ✗ {quality_data.get('timestamp_issues', 0)} problemas\n")

                f.write(f"- **Cobertura stats**: {quality_data.get('stats_coverage', 0):.1f}%\n")
                f.write(f"- **Filas totales**: {quality_data.get('total_rows', 0)}\n\n")

                # Sección Logs
                f.write("## Análisis de Logs\n\n")
                f.write(f"- **Errores**: {log_analysis.get('error_count', 0)}\n")
                f.write(f"- **Warnings**: {log_analysis.get('warning_count', 0)}\n")
                f.write(f"- **Capturas exitosas**: {log_analysis.get('capture_count', 0)}\n\n")

                if log_analysis.get('common_errors'):
                    f.write("### Errores Más Comunes\n\n")
                    for i, (error, count) in enumerate(log_analysis['common_errors'][:5], 1):
                        f.write(f"{i}. `{error[:100]}` ({count} veces)\n")
                    f.write("\n")

                f.write("---\n\n")
                f.write("*Generado automáticamente por Supervisor Agent*\n")

            self.log.info(f"✓ Informe generado: {report_file}")
            return report_file

        except Exception as e:
            self.log.error(f"Error al generar informe: {e}")
            return None


class ScraperHealthMonitor:
    """Monitor de salud del scraper"""

    def __init__(self, config):
        self.config = config
        self.log = logging.getLogger("HealthMonitor")

    def check_health(self) -> Dict:
        """Verificar salud completa del sistema"""
        return {
            'scraper_running': self._is_scraper_running(),
            'cpu_usage': psutil.cpu_percent(interval=1),
            'memory_usage': psutil.virtual_memory().percent,
            'disk_space_gb': psutil.disk_usage(str(self.config.BASE_DIR)).free / (1024**3),
            'chrome_processes': self._count_chrome_processes(),
            'last_capture_time': self._get_last_capture_time()
        }

    def _is_scraper_running(self) -> bool:
        """Verificar si el scraper está corriendo"""
        script_name = self.config.SCRAPER_SCRIPT.name

        for proc in psutil.process_iter(['name', 'cmdline']):
            try:
                cmdline = proc.info.get('cmdline', [])
                if cmdline and script_name in ' '.join(cmdline):
                    return True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        return False

    def _count_chrome_processes(self) -> int:
        """Contar procesos Chrome activos"""
        count = 0

        for proc in psutil.process_iter(['name']):
            try:
                if 'chrome' in proc.info['name'].lower():
                    count += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        return count

    def _get_last_capture_time(self) -> str:
        """Obtener hora de la última captura"""
        analyzer = LogAnalyzer(self.config)
        last_time = analyzer.get_last_capture_time()

        if last_time:
            return last_time.strftime('%Y-%m-%d %H:%M:%S')
        else:
            return "N/A"
