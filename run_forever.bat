@echo off
chcp 65001 >nul
title BorsKade Bot - Always On
cd /d "%~dp0"

REM Telegram proxy (v2rayN local SOCKS). TSETMC goes direct.
if "%BOT_PROXY%"=="" set BOT_PROXY=socks5://127.0.0.1:10808

:loop
echo [%date% %time%] Starting bot...
"venv\Scripts\python.exe" -X utf8 bot.py
echo.
echo [%date% %time%] Bot exited (code %errorlevel%). Restarting in 15 seconds...
timeout /t 15 /nobreak >nul
goto loop
