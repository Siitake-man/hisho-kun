@echo off
cd /d "%~dp0"
echo Starting Neo-Hisho-kun...

if not exist "venv\Scripts\python.exe" (
    echo [ERROR] Python virtual environment not found in venv\
    pause
    exit /b 1
)

if not exist ".env" (
    echo [ERROR] .env file not found. Please create .env from .env.example
    pause
    exit /b 1
)

"venv\Scripts\python.exe" main.py
if errorlevel 1 (
    echo [ERROR] Application exited with error.
    pause
)