"""
Furbo Monitor - Dashboard Backend
FastAPI server para monitorear el scraper de Betfair.
"""

import sys
from pathlib import Path

# Asegurar que el directorio backend está en sys.path
_backend_dir = Path(__file__).resolve().parent
if str(_backend_dir) not in sys.path:
    sys.path.insert(0, str(_backend_dir))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.matches import router as matches_router
from api.system import router as system_router

app = FastAPI(title="Furbo Monitor API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(matches_router)
app.include_router(system_router)


@app.get("/api/health")
def health_check():
    return {"status": "ok"}
