@echo off
setlocal
pushd "%~dp0" || exit /b 1

set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "CLICKER_BUILD_NUMBER=%~1"
if not defined CLICKER_BUILD_NUMBER set "CLICKER_BUILD_NUMBER=16"

uv sync
if errorlevel 1 goto failed

set "CLICKER_FLUTTER_VERSION="
for /f "delims=" %%V in ('.venv\Scripts\python.exe -c "import flet.version; print(flet.version.flutter_version)"') do set "CLICKER_FLUTTER_VERSION=%%V"
if not defined CLICKER_FLUTTER_VERSION goto failed

set "CLICKER_FLUTTER_BIN=%USERPROFILE%\flutter\%CLICKER_FLUTTER_VERSION%\bin"
if exist "%CLICKER_FLUTTER_BIN%\flutter.bat" set "PATH=%CLICKER_FLUTTER_BIN%;%PATH%"
if exist "%USERPROFILE%\java\17.0.13+11\bin\javac.exe" set "JAVA_HOME=%USERPROFILE%\java\17.0.13+11"

call .venv\Scripts\flet.exe build apk --output build/apk-fixed --build-number "%CLICKER_BUILD_NUMBER%" -v
set "CLICKER_BUILD_EXIT_CODE=%errorlevel%"
popd
exit /b %CLICKER_BUILD_EXIT_CODE%

:failed
popd
exit /b 1
