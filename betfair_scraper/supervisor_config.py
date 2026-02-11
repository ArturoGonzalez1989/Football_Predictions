# -*- coding: utf-8 -*-
"""
Configuración del Supervisor Agent
"""

import json
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import List, Optional


@dataclass
class SupervisorConfig:
    """Configuración del agente supervisor"""

    # Directorios y archivos
    BASE_DIR: Path = Path(__file__).parent
    SCRAPER_SCRIPT: Path = Path(__file__).parent / "main.py"
    GAMES_CSV: Path = Path(__file__).parent / "games.csv"
    OUTPUT_CSV_PATTERN: str = "output*.csv"
    LOGS_DIR: Path = Path(__file__).parent / "logs"
    REPORTS_DIR: Path = Path(__file__).parent / "reports"

    # Configuración del scraper
    SCRAPER_VENTANA_ANTES: int = 10
    SCRAPER_VENTANA_DESPUES: int = 150
    SCRAPER_CICLO: int = 60
    SCRAPER_EXTRA_ARGS: List[str] = None

    # Comportamiento del supervisor
    AUTO_START_SCRAPER: bool = True
    STOP_SCRAPER_ON_EXIT: bool = True
    AUTO_DISCOVER_MATCHES: bool = True
    AUTO_CORRECT: bool = True
    CHECK_INTERVAL: int = 300  # 5 minutos
    REPORT_INTERVAL: int = 12  # Generar informe cada 12 ciclos (1 hora)

    # Playwright para descubrimiento
    BETFAIR_BASE_URL: str = "https://www.betfair.es/sport/football"
    BETFAIR_INPLAY_URL: str = "https://www.betfair.es/sport/football/in-play"
    HEADLESS_BROWSER: bool = True
    BROWSER_TIMEOUT: int = 30000

    # Umbrales de calidad
    MIN_STATS_COVERAGE: float = 50.0  # % mínimo de stats capturadas
    MAX_NULL_PERCENTAGE: float = 30.0  # % máximo de valores nulos
    MAX_ERROR_COUNT: int = 50  # Reiniciar si se superan estos errores

    # Debug
    DEBUG: bool = False

    def __post_init__(self):
        """Convertir strings a Path y crear directorios"""
        if not isinstance(self.BASE_DIR, Path):
            self.BASE_DIR = Path(self.BASE_DIR)

        if not isinstance(self.SCRAPER_SCRIPT, Path):
            self.SCRAPER_SCRIPT = Path(self.SCRAPER_SCRIPT)

        if not isinstance(self.GAMES_CSV, Path):
            self.GAMES_CSV = Path(self.GAMES_CSV)

        if not isinstance(self.LOGS_DIR, Path):
            self.LOGS_DIR = Path(self.LOGS_DIR)

        if not isinstance(self.REPORTS_DIR, Path):
            self.REPORTS_DIR = Path(self.REPORTS_DIR)

        # Crear directorios si no existen
        self.LOGS_DIR.mkdir(exist_ok=True)
        self.REPORTS_DIR.mkdir(exist_ok=True)

        # Inicializar lista vacía si es None
        if self.SCRAPER_EXTRA_ARGS is None:
            self.SCRAPER_EXTRA_ARGS = []

    @classmethod
    def from_file(cls, config_path: str = "supervisor_config.json") -> "SupervisorConfig":
        """Cargar configuración desde archivo JSON"""
        config_file = Path(config_path)

        if config_file.exists():
            with open(config_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Convertir paths a strings para evitar problemas de serialización
            if 'BASE_DIR' in data:
                data['BASE_DIR'] = Path(data['BASE_DIR'])
            if 'SCRAPER_SCRIPT' in data:
                data['SCRAPER_SCRIPT'] = Path(data['SCRAPER_SCRIPT'])
            if 'GAMES_CSV' in data:
                data['GAMES_CSV'] = Path(data['GAMES_CSV'])
            if 'LOGS_DIR' in data:
                data['LOGS_DIR'] = Path(data['LOGS_DIR'])
            if 'REPORTS_DIR' in data:
                data['REPORTS_DIR'] = Path(data['REPORTS_DIR'])

            return cls(**data)
        else:
            # Crear configuración por defecto
            config = cls()
            config.save(config_path)
            return config

    def save(self, config_path: str = "supervisor_config.json"):
        """Guardar configuración a archivo JSON"""
        # Convertir a dict y serializar Paths
        data = asdict(self)
        data['BASE_DIR'] = str(data['BASE_DIR'])
        data['SCRAPER_SCRIPT'] = str(data['SCRAPER_SCRIPT'])
        data['GAMES_CSV'] = str(data['GAMES_CSV'])
        data['LOGS_DIR'] = str(data['LOGS_DIR'])
        data['REPORTS_DIR'] = str(data['REPORTS_DIR'])

        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)

    def __repr__(self):
        return f"SupervisorConfig(BASE_DIR={self.BASE_DIR}, SCRAPER_SCRIPT={self.SCRAPER_SCRIPT})"
