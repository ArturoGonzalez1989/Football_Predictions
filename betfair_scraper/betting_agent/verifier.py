"""LLM visual verification via LM Studio (OpenAI-compatible API).

Sends screenshots to a local multimodal model and gets structured verification
of market state, betslip contents, and bet confirmation.
"""

import base64
import json
import logging
import urllib.request
from pathlib import Path

_log = logging.getLogger(__name__)

DEFAULT_LM_STUDIO_URL = "http://127.0.0.1:1234"
DEFAULT_MODEL = "qwen/qwen3.5-9b:2"

SYSTEM_PROMPT = (
    "Eres un agente de verificacion de apuestas en Betfair Exchange. "
    "Analizas capturas de pantalla de la web de Betfair y respondes SOLO en JSON valido. "
    "Nunca incluyas texto fuera del JSON."
)


def _call_llm(image_path: str | Path, user_prompt: str, *,
              url: str = DEFAULT_LM_STUDIO_URL,
              model: str = DEFAULT_MODEL,
              max_tokens: int = 400,
              temperature: float = 0.2) -> dict | None:
    """Send image + prompt to LM Studio and return parsed JSON response."""
    try:
        with open(image_path, "rb") as f:
            img_b64 = base64.b64encode(f.read()).decode()

        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": user_prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_b64}"}},
                    ],
                },
            ],
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        req = urllib.request.Request(
            f"{url}/v1/chat/completions",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
        )
        resp = urllib.request.urlopen(req, timeout=60)
        result = json.loads(resp.read())
        content = result["choices"][0]["message"]["content"]

        # Try to parse JSON from response
        content = content.strip()
        if content.startswith("```"):
            # Strip markdown code fences
            lines = content.split("\n")
            content = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
        return json.loads(content)
    except json.JSONDecodeError:
        _log.warning("LLM response was not valid JSON: %s", content[:200] if 'content' in dir() else "N/A")
        return {"raw_response": content if 'content' in dir() else "parse_error", "ok": False}
    except Exception as e:
        _log.error("LLM call failed: %s", e)
        return None


def verify_market(screenshot_path: str | Path, expected_market: str,
                  expected_match: str, **kwargs) -> dict:
    """Verify we're on the correct market page.

    Returns: {"ok": bool, "market": str, "match": str, "details": str}
    """
    prompt = (
        f"Verifica esta captura de Betfair Exchange. Necesito confirmar:\n"
        f"1. Estoy en el partido correcto: '{expected_match}'?\n"
        f"2. Estoy en el mercado correcto: '{expected_market}'?\n"
        f"3. El mercado esta abierto para apostar?\n\n"
        f"Responde en JSON: {{\"ok\": true/false, \"match_found\": \"...\", "
        f"\"market_found\": \"...\", \"is_open\": true/false, \"details\": \"...\"}}"
    )
    result = _call_llm(screenshot_path, prompt, **kwargs)
    if result is None:
        return {"ok": False, "details": "LLM unavailable"}
    return result


def verify_betslip(screenshot_path: str | Path, expected_selection: str,
                   expected_odds: float, expected_stake: float, **kwargs) -> dict:
    """Verify betslip shows correct selection, odds, and stake.

    Returns: {"ok": bool, "selection": str, "odds": float, "stake": float, "profit": float, "details": str}
    """
    prompt = (
        f"Verifica el betslip (hoja de apuestas) en esta captura de Betfair.\n"
        f"Esperado: seleccion='{expected_selection}', odds~{expected_odds}, stake={expected_stake}EUR\n\n"
        f"Responde en JSON: {{\"ok\": true/false, \"selection_found\": \"...\", "
        f"\"odds_found\": 0.0, \"stake_found\": 0.0, \"profit_found\": 0.0, "
        f"\"type\": \"back/lay\", \"details\": \"...\"}}"
    )
    result = _call_llm(screenshot_path, prompt, **kwargs)
    if result is None:
        return {"ok": False, "details": "LLM unavailable"}
    return result


def verify_confirmation(screenshot_path: str | Path, **kwargs) -> dict:
    """Verify bet was placed successfully after clicking Apostar.

    Returns: {"ok": bool, "confirmed": bool, "details": str}
    """
    prompt = (
        "Verifica si la apuesta se coloco correctamente en Betfair.\n"
        "Busca mensajes de confirmacion, errores, o el estado del betslip.\n\n"
        "Responde en JSON: {\"ok\": true/false, \"confirmed\": true/false, "
        "\"error_message\": null o \"...\", \"details\": \"...\"}"
    )
    result = _call_llm(screenshot_path, prompt, **kwargs)
    if result is None:
        return {"ok": False, "confirmed": False, "details": "LLM unavailable"}
    return result
