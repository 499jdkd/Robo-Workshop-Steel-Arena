@echo off
setlocal
pushd "%~dp0" || exit /b 1

set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"

uv run python -u src\main.py
set "CLICKER_RUN_EXIT_CODE=%errorlevel%"
popd
exit /b %CLICKER_RUN_EXIT_CODE%
