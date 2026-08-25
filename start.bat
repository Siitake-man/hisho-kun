@echo off
REM ネオ秘書くん 起動スクリプト
cd /d "%~dp0"
echo ネオ秘書くん を起動します...
echo.
if not exist "venv\Scripts\python.exe" (
    echo 仮想環境が見つかりません。
    echo python -m venv venv を実行してから再度試してください。
    pause
    exit /b 1
)
if not exist ".env" (
    echo .env が見つかりません。
    echo .env.example を .env にコピーし、APIキーを設定してください。
    pause
    exit /b 1
)
"venv\Scripts\python.exe" main.py
pause