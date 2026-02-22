@echo off
echo Starting Furbo Monitor Dashboard...
echo.

echo Killing old backend process on port 8000 (if any)...
for /f "tokens=5" %%a in ('netstat -aon 2^>nul ^| findstr ":8000 " ^| findstr "LISTENING"') do (
    taskkill /PID %%a /F >nul 2>&1
    echo Killed PID %%a
)
timeout /t 1 /nobreak >nul

echo [1/2] Starting Backend (FastAPI) on port 8000...
start "Furbo Backend" cmd /k "cd /d %~dp0backend && python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000"

timeout /t 2 /nobreak >nul

echo [2/2] Starting Frontend (Vite) on port 5173...
start "Furbo Frontend" cmd /k "cd /d %~dp0frontend && npx vite --host 0.0.0.0 --port 5173"

timeout /t 3 /nobreak >nul

echo.
echo Dashboard ready at http://localhost:5173
echo Backend API at http://localhost:8000/api/health
echo.
start http://localhost:5173
