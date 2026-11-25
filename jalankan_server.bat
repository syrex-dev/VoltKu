@echo off
title Monitor Listrik Pintar - Server Backend
echo ================================================================
echo    MENJALANKAN SERVER MONITOR LISTRIK PINTAR (PORT 8000)
echo ================================================================
echo.
echo Buka di browser: http://localhost:8000
echo.
cd /d %~dp0
set PYTHONPATH=%~dp0.venv\Lib\site-packages;%~dp0backend
python -m uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port 8000
pause
