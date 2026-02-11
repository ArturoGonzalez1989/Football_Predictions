#!/usr/bin/env python3
"""
Supervisor de Betfair - Ejecuta el agente supervisor de Claude

Uso:
    python supervisor.py
"""

import subprocess
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).parent.parent

def main():
    """Ejecuta el agente supervisor de Claude"""

    print("\n" + "="*50)
    print("   Supervisor de Betfair")
    print("="*50 + "\n")

    # Comando para invocar el agente supervisor
    command = "Inicia al agente @.claude/agents/betfair-supervisor.md"

    try:
        print(f"📍 Directorio: {PROJECT_DIR}")
        print(f"🤖 Ejecutando supervisor...\n")

        # Ejecutar Claude CLI
        result = subprocess.run(
            ["claude", command],
            cwd=PROJECT_DIR,
            text=True,
            encoding="utf-8"
        )

        if result.returncode == 0:
            print("\n✅ Supervisor ejecutado correctamente\n")
        else:
            print(f"\n⚠️  El supervisor finalizó con código: {result.returncode}\n")

        return result.returncode

    except FileNotFoundError:
        print("\n❌ ERROR: No se encuentra el comando 'claude'")
        print("   Verifica que la CLI de Claude esté instalada y en el PATH\n")
        return 1

    except KeyboardInterrupt:
        print("\n\n⚠️  Supervisor interrumpido por el usuario\n")
        return 130

    except Exception as e:
        print(f"\n❌ ERROR: {e}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
