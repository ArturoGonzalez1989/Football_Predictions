#!/usr/bin/env python3
"""
extract_iframe_stats.py - Fallback para estadísticas sin Opta
==============================================================
Extrae estadísticas del iframe de visualización de Sportradar cuando
el partido no tiene eventId de Opta (ligas menores, etc.).

Este módulo es un FALLBACK - solo se ejecuta si extract_event_id() falla.
"""

import re
import logging
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

log = logging.getLogger("betfair_scraper.iframe_stats")


def extract_stats_from_iframe(driver, betfair_event_id: str) -> dict:
    """
    Extrae estadísticas del iframe de Sportradar como fallback.

    Args:
        driver: WebDriver de Selenium (ya en la página del partido)
        betfair_event_id: ID del evento en Betfair (ej: "35232966")

    Returns:
        dict: Estadísticas extraídas (mismo formato que stats_api.py)
              Devuelve dict vacío si falla
    """
    stats = {}
    original_url = None

    try:
        # URL del iframe de stats
        iframe_url = (
            f"https://videoplayer.betfair.es/GetPlayer.do"
            f"?eID={betfair_event_id}"
            f"&contentType=viz&contentView=mstats"
        )

        log.info(f"  → Extrayendo stats del iframe (fallback): eID={betfair_event_id}")

        # Guardar URL original para volver después
        original_url = driver.current_url

        # Navegar directamente al iframe
        driver.get(iframe_url)

        # Esperar a que carguen las stats (reducido de 12s a 6s — 2026-03-07)
        wait = WebDriverWait(driver, 6)
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))

        # Esperar a que se cargue al menos un elemento de estadísticas
        try:
            wait.until(EC.presence_of_element_located(
                (By.XPATH, "//*[contains(text(), 'Shots on target') or contains(text(), 'Corner kicks')]")
            ))
            # Dar tiempo adicional para que se rendericen todas las secciones
            import time
            time.sleep(0.5)
        except TimeoutException:
            log.warning("  × Timeout esperando estadísticas básicas")

        # IMPORTANTE: Todas las estadísticas ya están cargadas en el DOM,
        # la paginación solo controla la visibilidad. No necesitamos navegar.

        # Helper: extraer stat dual "X LABEL Y"
        def get_dual_stat(label_text):
            try:
                # Buscar elemento que contiene el label
                label_xpath = f"//*[contains(text(), '{label_text}')]"
                label_elements = driver.find_elements(By.XPATH, label_xpath)

                if not label_elements:
                    log.debug(f"    × '{label_text}' no encontrado en DOM")
                    return None, None

                label_elem = label_elements[0]

                # Buscar el hermano anterior (home value) y posterior (away value)
                try:
                    home_elem = label_elem.find_element(By.XPATH, "./preceding-sibling::*[1]")
                    home_value = home_elem.text.strip()
                except Exception as e:
                    log.debug(f"    × '{label_text}' - no se pudo obtener home value: {e}")
                    home_value = None

                try:
                    away_elem = label_elem.find_element(By.XPATH, "./following-sibling::*[1]")
                    away_value = away_elem.text.strip()
                except Exception as e:
                    log.debug(f"    × '{label_text}' - no se pudo obtener away value: {e}")
                    away_value = None

                # Validar que ambos valores sean números
                if home_value and away_value:
                    # Limpiar valores (remover caracteres no numéricos excepto dígitos)
                    home_clean = ''.join(c for c in home_value if c.isdigit())
                    away_clean = ''.join(c for c in away_value if c.isdigit())

                    if home_clean and away_clean:
                        log.debug(f"    ✓ '{label_text}': {home_clean}-{away_clean}")
                        return home_clean, away_clean
                    else:
                        log.debug(f"    × '{label_text}' - valores no numéricos: '{home_value}' - '{away_value}'")
                else:
                    log.debug(f"    × '{label_text}' - valores vacíos")

            except Exception as e:
                log.debug(f"    × Error extrayendo '{label_text}': {e}")

            return None, None

        # Helper: extraer porcentajes "X% LABEL Y%"
        def get_percentage_stat(label_text):
            try:
                xpath = f"//*[contains(text(), '{label_text}')]"
                elements = driver.find_elements(By.XPATH, xpath)

                if not elements:
                    return None, None

                parent = elements[0].find_element(By.XPATH, "../..")
                text = parent.text

                # Buscar números seguidos de %
                percentages = re.findall(r'(\d+)\s*%', text)

                if len(percentages) >= 2:
                    return percentages[0], percentages[1]

            except Exception:
                pass

            return None, None

        # Extraer SOLO estadísticas usadas por estrategias (optimizado 2026-03-07)
        # Skipped: Free kicks, Offsides, Goal kicks, Saves, Throw-ins,
        #          Substitutions, Injuries — no usadas por ninguna estrategia
        log.debug("  → Extrayendo estadísticas críticas del iframe...")

        # Shots y corners (usados por todas las estrategias)
        home_shots_on, away_shots_on = get_dual_stat("Shots on target")
        home_shots_off, away_shots_off = get_dual_stat("Shots off target")
        home_shots_blocked, away_shots_blocked = get_dual_stat("Shots blocked")
        home_corners, away_corners = get_dual_stat("Corner kicks")

        # Possession y ataques peligrosos
        home_poss, away_poss = get_percentage_stat("Ball possession")
        home_attacks, away_attacks = get_dual_stat("Dangerous Attack")

        # Fouls (para stats output)
        home_fouls, away_fouls = get_dual_stat("Fouls")

        # Construir diccionario (solo campos usados por estrategias)
        stats = {
            "tiros_puerta_local": home_shots_on or "",
            "tiros_puerta_visitante": away_shots_on or "",
            "corners_local": home_corners or "",
            "corners_visitante": away_corners or "",
            "posesion_local": home_poss or "",
            "posesion_visitante": away_poss or "",
            "fouls_conceded_local": home_fouls or "",
            "fouls_conceded_visitante": away_fouls or "",
            "dangerous_attacks_local": home_attacks or "",
            "dangerous_attacks_visitante": away_attacks or "",
            "shots_off_target_local": home_shots_off or "",
            "shots_off_target_visitante": away_shots_off or "",
            "blocked_shots_local": home_shots_blocked or "",
            "blocked_shots_visitante": away_shots_blocked or "",
        }

        # Calcular tiros totales (on + off + blocked)
        try:
            if home_shots_on and home_shots_off and home_shots_blocked:
                total = int(home_shots_on) + int(home_shots_off) + int(home_shots_blocked)
                stats["tiros_local"] = str(total)

            if away_shots_on and away_shots_off and away_shots_blocked:
                total = int(away_shots_on) + int(away_shots_off) + int(away_shots_blocked)
                stats["tiros_visitante"] = str(total)
        except (ValueError, TypeError):
            pass

        # Contar campos capturados
        captured_count = sum(1 for v in stats.values() if v != "")

        if captured_count > 0:
            log.info(f"  ✓ Fallback iframe exitoso: {captured_count} campos capturados")
        else:
            log.warning("  × Fallback iframe no encontró estadísticas")

    except TimeoutException:
        log.warning("  × Timeout esperando iframe de stats (fallback)")
    except Exception as e:
        log.error(f"  × Error en fallback iframe: {e}")
    finally:
        # CRÍTICO: Volver a la URL original
        try:
            if original_url:
                driver.get(original_url)
        except Exception as e:
            log.error(f"  × Error volviendo a URL original: {e}")

    return stats
