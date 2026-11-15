@echo off
setlocal
pushd "%~dp0" || exit /b 1
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "CLICKER_PLAY_BUILD_NUMBER=%~1"
if not defined CLICKER_PLAY_BUILD_NUMBER set "CLICKER_PLAY_BUILD_NUMBER=17"
call .venv\Scripts\python.exe tools\build_google_play.py --build-number "%CLICKER_PLAY_BUILD_NUMBER%"
set "CLICKER_PLAY_EXIT_CODE=%errorlevel%"
popd
exit /b %CLICKER_PLAY_EXIT_CODE%
