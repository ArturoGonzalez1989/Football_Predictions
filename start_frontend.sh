#!/usr/bin/env bash
# Lanza el frontend de Vite guardando la salida de terminal en logs/
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOGS_DIR="$SCRIPT_DIR/betfair_scraper/logs"
mkdir -p "$LOGS_DIR"

LOG_FILE="$LOGS_DIR/frontend_$(date +%Y%m%d_%H%M%S).log"
echo "[$(date)] Frontend log → $LOG_FILE"

cd "$SCRIPT_DIR/betfair_scraper/dashboard/frontend" || exit 1
npm run dev 2>&1 | tee "$LOG_FILE"
