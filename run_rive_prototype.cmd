@echo off
setlocal
cd /d "%~dp0prototypes\rive_robot\flutter"
if not exist "..\assets\spark.riv" (
    echo First export the Rive asset with: uv run python tools\prepare_rive_prototype.py
    exit /b 1
)
"%USERPROFILE%\flutter\3.44.8\bin\flutter.bat" run -d chrome --profile
