#!/usr/bin/env python3
"""Fix SD/core references in system-auditor.md"""
import re

with open('.claude/agents/system-auditor.md', 'r', encoding='utf-8') as f:
    content = f.read()

original_len = len(content)

# FIX 1: Remove "core" from GR8 pattern description (line 31)
content = content.replace(
    'Cada core strategy tiene un helper',
    'Cada estrategia tiene un helper'
)

# FIX 2: Remove legacy file table rows and replace strategy listing
old_files_and_strats = (
    '| `betfair_scraper/dashboard/backend/utils/sd_strategies.py` | SD configs aprobadas | Paso 1 |\n'
    '| `auxiliar/sd_generators.py` | Generadores BT de SD strategies (~1800 líneas) | Paso 2e |\n'
    '\n'
    '### Estrategias\n'
    '\n'
    '- **7 Core** (con helper GR8): `draw`, `xg`, `drift`, `clustering`, `pressure`, `tarde_asia`, `momentum_xg`\n'
    '- **9 SD con LIVE**: `sd_over25_2goal`, `sd_under35_late`, `sd_longshot`, `sd_cs_close`, `sd_cs_one_goal`, `sd_ud_leading`, `sd_home_fav_leading`, `sd_cs_20`, `sd_cs_big_lead` — usan código **inline** en `detect_betting_signals()`, NO helpers compartidos\n'
    '- **10 SD solo BT** (sin LIVE): el resto de configs en `sd_strategies.py`'
)
new_files_and_strats = (
    '\n'
    '### Estrategias\n'
    '\n'
    '- **32 estrategias** independientes e iguales. Todas tienen helper `_detect_<name>_trigger(rows, curr_idx, cfg)` en csv_reader.py. BT y LIVE ejecutan el mismo código vía estos helpers.\n'
    '- Lista completa: leer `scripts/bt_optimizer.py:SINGLE_STRATEGIES` o `betfair_scraper/cartera_config.json`.'
)
if old_files_and_strats in content:
    content = content.replace(old_files_and_strats, new_files_and_strats)
    print("FIX 2 applied (files table + strategy listing)")
else:
    print("FIX 2 NOT FOUND")

# FIX 3: Replace Paso 1 Python script (core+SD split → unified)
# Find the block between "```bash" and "```" in Paso 1 section
paso1_marker = "### PASO 1 — Config Coverage (Notebook → Config)"
paso3_marker = "### PASO 2 — Live Fidelity"

pos1 = content.find(paso1_marker)
pos2 = content.find(paso3_marker)
if pos1 >= 0 and pos2 >= 0:
    paso1_section = content[pos1:pos2]
    # Replace the python script block inside it
    old_script_start = "```bash\npython3 << 'PYEOF'\nimport json, sys, io\nsys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')\n\nwith open('betfair_scraper/cartera_config.json'"
    old_script_end = "PYEOF\n```\n\n---\n\n### PASO 2"

    start_idx = content.find(old_script_start, pos1)
    end_idx = content.find(old_script_end, pos1)

    if start_idx >= 0 and end_idx >= 0 and start_idx < pos2:
        new_script = (
            "```bash\n"
            "python3 << 'PYEOF'\n"
            "import json, sys, io\n"
            "sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')\n\n"
            "with open('betfair_scraper/cartera_config.json', encoding='utf-8') as f:\n"
            "    config = json.load(f)\n\n"
            "strategies = config.get('strategies', {})\n"
            "min_dur = config.get('min_duration', {})\n\n"
            "print('=== CONFIG COVERAGE (todas las estrategias) ===\\n')\n\n"
            "missing_mindur = []\n"
            "for s in sorted(strategies.keys()):\n"
            "    in_mindur = s in min_dur\n"
            "    enabled = strategies[s].get('enabled', False) if isinstance(strategies[s], dict) else False\n"
            "    status = 'OK' if in_mindur else 'MISSING'\n"
            "    if not in_mindur: missing_mindur.append(s)\n"
            "    print(f'  {s:<30} min_dur={\"Y\" if in_mindur else \"N\"}  enabled={enabled}  {status}')\n\n"
            "if missing_mindur:\n"
            "    print(f'\\nALERTA: {len(missing_mindur)} estrategias sin min_duration: {missing_mindur}')\n"
            "else:\n"
            "    print(f'\\nOK: Las {len(strategies)} estrategias tienen config + min_duration')\n"
            "PYEOF\n"
            "```\n\n"
            "---\n\n"
            "### PASO 2"
        )
        content = content[:start_idx] + new_script + content[end_idx + len(old_script_end):]
        print("FIX 3 applied (Paso 1 script unified)")
    else:
        print(f"FIX 3: script block not found (start={start_idx}, end={end_idx})")
else:
    print(f"FIX 3: markers not found (pos1={pos1}, pos2={pos2})")

# FIX 4: Replace section 2c (SD LIVE detection check) with general check
old_2c = (
    "#### 2c. SD con enabled: true — ¿tienen detección LIVE?\n"
    "\n"
    "Para cada SD con `enabled: true` en config, buscar si `detect_betting_signals()` tiene\n"
    "código que la evalúe. Si no lo tiene, es **CRITICO**: el config dice que está activa pero\n"
    "LIVE no la ejecuta → apuestas perdidas.\n"
    "\n"
    "```bash\n"
    "python3 << 'PYEOF'\n"
    "import json, sys, io\n"
    "sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')\n"
    "\n"
    "with open('betfair_scraper/cartera_config.json', encoding='utf-8') as f:\n"
    "    config = json.load(f)\n"
    "\n"
    "with open('betfair_scraper/dashboard/backend/utils/csv_reader.py', encoding='utf-8') as f:\n"
    "    code = f.read()\n"
    "\n"
    "detect_start = code.find('def detect_betting_signals')\n"
    "live_body = code[detect_start:] if detect_start > 0 else \"\"\n"
    "\n"
    "core = {'draw', 'xg', 'drift', 'clustering', 'pressure', 'tarde_asia', 'momentum_xg'}\n"
    "strategies = config.get('strategies', {})\n"
    "\n"
    "print(\"=== SD LIVE DETECTION CHECK ===\\n\")\n"
    "sd_enabled_no_live = []\n"
    "for strat, cfg in sorted(strategies.items()):\n"
    "    if strat in core:\n"
    "        continue\n"
    "    if not isinstance(cfg, dict) or not cfg.get('enabled', False):\n"
    "        continue\n"
    "    has_detection = strat in live_body or f\"'{strat}'\" in live_body or f'\"{strat}\"' in live_body\n"
    "    if has_detection:\n"
    "        print(f\"  {strat:<25} LIVE detection: YES\")\n"
    "    else:\n"
    "        sd_enabled_no_live.append(strat)\n"
    "        print(f\"  {strat:<25} LIVE detection: NO  ← CRITICO: enabled pero no se ejecuta\")\n"
    "\n"
    "if sd_enabled_no_live:\n"
    "    print(f\"\\nCRITICO: {len(sd_enabled_no_live)} SD con enabled=true pero SIN detección LIVE:\")\n"
    "    for s in sd_enabled_no_live:\n"
    "        print(f\"  - {s}\")\n"
    "    print(\"\\nEstas estrategias están 'encendidas' en config pero LIVE las ignora.\")\n"
    "else:\n"
    "    print(\"\\nOK: Ninguna SD enabled sin detección\")\n"
    "PYEOF\n"
    "```"
)
new_2c = (
    "#### 2c. Estrategias con enabled: true — ¿tienen helper `_detect_*_trigger` en csv_reader.py?\n"
    "\n"
    "Para cada estrategia con `enabled: true`, verificar que `csv_reader.py` define su helper\n"
    "`_detect_<name>_trigger`. Si no lo tiene, es **CRITICO**: config dice activa pero LIVE no la ejecuta.\n"
    "\n"
    "```bash\n"
    "python3 << 'PYEOF'\n"
    "import json, sys, io\n"
    "sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')\n"
    "\n"
    "with open('betfair_scraper/cartera_config.json', encoding='utf-8') as f:\n"
    "    config = json.load(f)\n"
    "with open('betfair_scraper/dashboard/backend/utils/csv_reader.py', encoding='utf-8') as f:\n"
    "    code = f.read()\n"
    "\n"
    "strategies = config.get('strategies', {})\n"
    "print('=== LIVE HELPER CHECK (todas las estrategias) ===\\n')\n"
    "no_helper = []\n"
    "for strat, cfg in sorted(strategies.items()):\n"
    "    if not isinstance(cfg, dict) or not cfg.get('enabled', False):\n"
    "        continue\n"
    "    # All strategies should have _detect_<name>_trigger in csv_reader.py\n"
    "    helper = f'_detect_{strat}_trigger'\n"
    "    has_helper = f'def {helper}(' in code\n"
    "    in_live = helper in code[code.find('def detect_betting_signals'):] if 'def detect_betting_signals' in code else False\n"
    "    if has_helper and in_live:\n"
    "        print(f'  {strat:<30} helper=YES  live_call=YES')\n"
    "    else:\n"
    "        no_helper.append(strat)\n"
    "        print(f'  {strat:<30} helper={\"YES\" if has_helper else \"NO\"}  live_call={\"YES\" if in_live else \"NO\"}  <- CRITICO')\n"
    "\n"
    "if no_helper:\n"
    "    print(f'\\nCRITICO: {len(no_helper)} estrategias enabled sin helper/llamada LIVE: {no_helper}')\n"
    "else:\n"
    "    print('\\nOK: Todas las estrategias enabled tienen helper y llamada LIVE')\n"
    "PYEOF\n"
    "```"
)
if old_2c in content:
    content = content.replace(old_2c, new_2c)
    print("FIX 4 applied (section 2c)")
else:
    print("FIX 4 NOT FOUND (section 2c)")

# FIX 5: Remove sections 2e, 2g, 2h, 2i (all reference legacy sd_generators/sd_filters)
# Section 2e starts at "#### 2e. SD Logic Parity" and ends just before "#### 2f."
old_2e_start = "\n#### 2e. SD Logic Parity — ¿La lógica inline de LIVE es idéntica al generador BT? ⭐ NUEVO\n"
old_2e_end = "\n#### 2f. Compatibilidad temporal"

pos_2e = content.find(old_2e_start)
pos_2f = content.find(old_2e_end)
if pos_2e >= 0 and pos_2f >= 0 and pos_2e < pos_2f:
    content = content[:pos_2e] + "\n" + content[pos_2f:]
    print("FIX 5a applied (removed section 2e)")
else:
    print(f"FIX 5a NOT FOUND (2e={pos_2e}, 2f={pos_2f})")

# Section 2g starts at "#### 2g." and ends just before "---\n\n#### 2h."
old_2g_start = "\n#### 2g. Semántica m_max"
old_2g_end = "\n---\n\n#### 2h. Pre-match odds lookup"
pos_2g = content.find(old_2g_start)
pos_2h = content.find(old_2g_end)
if pos_2g >= 0 and pos_2h >= 0 and pos_2g < pos_2h:
    content = content[:pos_2g] + content[pos_2h:]
    print("FIX 5b applied (removed section 2g)")
else:
    print(f"FIX 5b NOT FOUND (2g={pos_2g}, 2h={pos_2h})")

# Section 2h starts at "#### 2h." and ends just before "---\n\n#### 2i."
old_2h_start = "\n#### 2h. Pre-match odds lookup window"
old_2h_end = "\n---\n\n#### 2i. Params de BT"
pos_2h2 = content.find(old_2h_start)
pos_2i = content.find(old_2h_end)
if pos_2h2 >= 0 and pos_2i >= 0 and pos_2h2 < pos_2i:
    content = content[:pos_2h2] + content[pos_2i:]
    print("FIX 5c applied (removed section 2h)")
else:
    print(f"FIX 5c NOT FOUND (2h={pos_2h2}, 2i={pos_2i})")

# Section 2i starts at "#### 2i." and ends just before "---\n\n#### 2d."
old_2i_start = "\n#### 2i. Params de BT (_apply_sd_*)"
old_2i_end = "\n---\n\n#### 2d. Post-filtros"
pos_2i2 = content.find(old_2i_start)
pos_2d = content.find(old_2i_end)
if pos_2i2 >= 0 and pos_2d >= 0 and pos_2i2 < pos_2d:
    content = content[:pos_2i2] + content[pos_2d:]
    print("FIX 5d applied (removed section 2i)")
else:
    print(f"FIX 5d NOT FOUND (2i={pos_2i2}, 2d={pos_2d})")

# FIX 6: Update EXPECTED_HELPERS in Paso 3 GR8 to use actual trigger names
old_helpers = (
    "EXPECTED_HELPERS = [\n"
    "    '_detect_draw_trigger', '_detect_draw_filters',\n"
    "    '_detect_xg_trigger', '_detect_drift_trigger',\n"
    "    '_detect_clustering_trigger', '_detect_pressure_trigger',\n"
    "    '_detect_momentum_trigger', '_detect_tardesia_trigger',\n"
    "]"
)
new_helpers = (
    "# Leer SINGLE_STRATEGIES de bt_optimizer.py para la lista completa\n"
    "# Aquí verificamos un subconjunto representativo de helpers\n"
    "EXPECTED_HELPERS = [\n"
    "    '_detect_back_draw_00_trigger', '_detect_xg_underperformance_trigger',\n"
    "    '_detect_odds_drift_trigger', '_detect_goal_clustering_trigger',\n"
    "    '_detect_pressure_cooker_trigger', '_detect_momentum_xg_trigger',\n"
    "    '_detect_tardesia_trigger', '_detect_under35_late_trigger',\n"
    "    '_detect_longshot_trigger', '_detect_ud_leading_trigger',\n"
    "]"
)
if old_helpers in content:
    content = content.replace(old_helpers, new_helpers)
    print("FIX 6 applied (EXPECTED_HELPERS)")
else:
    print("FIX 6 NOT FOUND")

# FIX 7: Update report template - remove Core/SD refs
old_report = (
    "## 1. Config Coverage\n"
    "- Core: X/7 con config + min_duration\n"
    "- SD: X/Y aprobadas presentes\n"
    "- Gaps: <lista si hay>"
)
new_report = (
    "## 1. Config Coverage\n"
    "- Estrategias: X/32 con config + min_duration\n"
    "- Gaps: <lista si hay>"
)
if old_report in content:
    content = content.replace(old_report, new_report)
    print("FIX 7 applied (report template)")
else:
    print("FIX 7 NOT FOUND")

# FIX 7b: Remove "SD enabled sin detección LIVE" from Live Fidelity report section
old_live_fidelity = (
    "- Config params → versions dict: X/Y pasados\n"
    "- Params que NO llegan a LIVE: <lista con valor y estrategia>\n"
    "- SD enabled sin detección LIVE: X (CRITICO si > 0)\n"
    "- Post-filtros: OK/FAIL"
)
new_live_fidelity = (
    "- Config params → versions dict: X/Y pasados\n"
    "- Params que NO llegan a LIVE: <lista con valor y estrategia>\n"
    "- Estrategias enabled sin helper LIVE: X (CRITICO si > 0)\n"
    "- Post-filtros: OK/FAIL"
)
if old_live_fidelity in content:
    content = content.replace(old_live_fidelity, new_live_fidelity)
    print("FIX 7b applied (live fidelity report)")
else:
    print("FIX 7b NOT FOUND")

# FIX 8: Remove "SD sin detección LIVE" from fixes table
old_sd_fix_row = "| SD sin detección LIVE | **🚨 STOP — avisar** (problema conocido, requiere crear helper) | — |\n"
if old_sd_fix_row in content:
    content = content.replace(old_sd_fix_row, "")
    print("FIX 8 applied (removed SD fix table row)")
else:
    print("FIX 8 NOT FOUND")

# FIX 9: Remove historical cases 2, 3, 4 (all about SD-specific bugs now fixed)
old_cases_234 = (
    "### Caso 2 (2026-03-10): m_max inclusivo vs exclusivo — apuestas fuera de rango validado\n"
)
pos_case2 = content.find(old_cases_234)
# Find end of Case 4
old_case4_end = "**CHECK AÑADIDO**: Paso 2i — extrae todos los `cfg.get('param', default)` de `_apply_sd_*` en sd_filters.py y verifica que cada param exista en cartera_config.json.\n\n---\n\n## REGLAS"
pos_rules = content.find(old_case4_end)
if pos_case2 >= 0 and pos_rules >= 0 and pos_case2 < pos_rules:
    replacement = (
        "### Casos 2-4 (2026-03-10): Bugs de alineamiento BT↔LIVE (RESUELTOS)\n"
        "Los bugs históricos de m_max semántico, pre-match odds lookup, y params hardcodeados en\n"
        "sd_filters.py fueron resueltos en 2026-03-10/11 al unificar BT y LIVE en helpers compartidos.\n"
        "Todos los triggers usan ahora `_detect_<name>_trigger(rows, curr_idx, cfg)` — la misma\n"
        "función exacta en BT y LIVE. No aplican checks 2g/2h/2i para el sistema actual.\n\n"
        "---\n\n"
        "## REGLAS"
    )
    content = content[:pos_case2] + replacement + content[pos_rules + len(old_case4_end):]
    print("FIX 9 applied (historical cases 2-4 summary)")
else:
    print(f"FIX 9 NOT FOUND (case2={pos_case2}, rules={pos_rules})")

# FIX 10: Update rules section to remove SD-specific rules
# Rule 9: references step 2e..2i
old_rule9 = "9. **El paso 2 es tu razón de existir** — dedícale el mayor esfuerzo y detalle. Ejecuta TODOS los sub-pasos: 2a, 2b, 2c, 2d, 2e, 2f, 2g, 2h, 2i."
new_rule9 = "9. **El paso 2 es tu razón de existir** — dedícale el mayor esfuerzo y detalle. Ejecuta TODOS los sub-pasos: 2a, 2b, 2c, 2d, 2f."
content = content.replace(old_rule9, new_rule9)
print("FIX 10 applied (rule 9)")

# Rule 12: None passthrough for SD
old_rule12 = "12. **Antipatrón None passthrough** — en LIVE, `(x is None or x <= max)` acepta None silenciosamente. El BT genera bets con `if x is None: continue`. Si ves este patrón en LIVE para una SD strategy, es ALTO — el edge del BT no aplica a casos sin datos."
new_rule12 = "12. **Antipatrón None passthrough** — en LIVE, `(x is None or x <= max)` acepta None silenciosamente. El BT genera bets con `if x is None: continue`. Si ves este patrón en LIVE para alguna estrategia, es ALTO — el edge del BT no aplica a casos sin datos."
content = content.replace(old_rule12, new_rule12)
print("FIX 10b applied (rule 12)")

# Rule 13: references 2g/2h/2i
old_rule13 = "13. **Conectividad ≠ Semántica** — que el cable esté enchufado no significa que transporte la señal correcta. Tres tipos de bug semántico siempre presentes: (a) operador incorrecto (`<` vs `<=`), (b) ventana de datos diferente (`rows[0]` vs `rows[:5]`), (c) param hardcodeado en BT no expuesto al config. Los pasos 2g, 2h, 2i detectan estos tres tipos automáticamente."
new_rule13 = "13. **Conectividad ≠ Semántica** — que el cable esté enchufado no significa que transporte la señal correcta. Tipos de bug semántico: (a) operador incorrecto (`<` vs `<=`), (b) ventana de datos diferente (`rows[0]` vs `rows[:5]`), (c) param hardcodeado en helper no expuesto al config. Verificar siempre la semántica de condiciones en helpers nuevos."
content = content.replace(old_rule13, new_rule13)
print("FIX 10c applied (rule 13)")

# Rule 14: References sd_filters.py
old_rule14 = "14. **Auditar desde la fuente BT, no desde el config** — el config solo contiene lo que el usuario decidió exponer. Los defaults hardcodeados en `sd_filters.py` son parte del contrato BT aunque no estén en el config. El Paso 2i garantiza que todo param BT tenga su correspondiente en config y llegue a LIVE."
new_rule14 = "14. **Auditar desde la fuente BT, no desde el config** — el config solo contiene lo que el usuario decidió exponer. Los defaults hardcodeados en helpers `_detect_*_trigger()` son parte del contrato BT aunque no estén en el config. Verificar que todo param usado en un helper exista en cartera_config.json y llegue a LIVE."
content = content.replace(old_rule14, new_rule14)
print("FIX 10d applied (rule 14)")

# INFO rule: remove "SD sin LIVE (problema conocido)"
old_info_rule = "   - INFO: SD sin LIVE (problema conocido y documentado)"
if old_info_rule in content:
    content = content.replace(old_info_rule + "\n", "")
    print("FIX 11 applied (removed INFO SD rule)")
else:
    print("FIX 11 NOT FOUND")

# Save
with open('.claude/agents/system-auditor.md', 'w', encoding='utf-8') as f:
    f.write(content)

new_len = len(content)
print(f"\nDone. Original: {original_len} chars, New: {new_len} chars, Removed: {original_len - new_len} chars")
