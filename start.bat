@echo off
chcp 65001 >nul
title TSETMC Watchlist Bot
cd /d "%~dp0"

if not exist "venv\Scripts\python.exe" (
    echo [1/3] Creating virtual environment...
    python -m venv venv || goto :err
)

echo [2/3] Installing dependencies...
"venv\Scripts\python.exe" -m pip install -r requirements.txt --quiet --disable-pip-version-check || goto :err

if "%BOT_TOKEN%"=="" (
    if exist "token.txt" (
        set /p BOT_TOKEN=<token.txt
    )
)

if "%BOT_TOKEN%"=="" (
    echo.
    echo [3/3] Telegram bot token ra vared konid (az @BotFather):
    set /p BOT_TOKEN=Token:
)

REM Proxy for Telegram traffic (v2rayN local SOCKS port). TSETMC goes direct.
if "%BOT_PROXY%"=="" set BOT_PROXY=socks5://127.0.0.1:10808

echo Starting bot...
"venv\Scripts\python.exe" -X utf8 bot.py %BOT_TOKEN%
goto :eof

:err
echo.
echo ERROR: Setup failed. Check that Python 3.10+ is installed.
pause
