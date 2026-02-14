@echo off
cd /d "c:\Users\agonz\OneDrive\Documents\Proyectos\Furbo\betfair_scraper\dashboard\backend"
echo Iniciando backend en puerto 8000...
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
