@echo off
title PlayerSlayer's Sanctuary
cd /d "%~dp0"

set "PYW=%LOCALAPPDATA%\Programs\Python\Python312\pythonw.exe"
if exist "%PYW%" (
    start "" "%PYW%" run_app.py
    exit /b 0
)

set "PY=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
if exist "%PY%" (
    start "" "%PY%" run_app.py
    exit /b 0
)

start "" pythonw run_app.py 2>nul || python run_app.py
