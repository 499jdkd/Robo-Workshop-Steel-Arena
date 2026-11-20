@echo off
setlocal
cd /d "%~dp0"
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
where uv >nul 2>nul
if not errorlevel 1 (
    uv run python src\main.py
) else (
    .venv\Scripts\python.exe src\main.py
)
if errorlevel 1 pause
endlocal
