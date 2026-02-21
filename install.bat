@echo off
setlocal enabledelayedexpansion
title Screener Scraper - Setup
color 0A

echo.
echo  ============================================
echo   Screener Scraper - First Time Setup
echo  ============================================
echo.

:: ── Check / Install Python ────────────────────────────────────────────────────
python --version >nul 2>&1
if %errorlevel% == 0 (
    for /f "tokens=*" %%i in ('python --version 2^>^&1') do set PYVER=%%i
    echo  [OK] Python already installed: !PYVER!
    goto :install_deps
)

echo  [..] Python not found. Downloading Python 3.12...
powershell -Command "Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.12.4/python-3.12.4-amd64.exe' -OutFile '%TEMP%\python_installer.exe'"

if not exist "%TEMP%\python_installer.exe" (
    echo  [!!] Failed to download Python. Check your internet connection.
    pause & exit /b 1
)

echo  [..] Installing Python - please click YES if Windows asks for permission...
"%TEMP%\python_installer.exe" /quiet InstallAllUsers=0 PrependPath=1 Include_pip=1

:: Refresh PATH
set "PATH=%LOCALAPPDATA%\Programs\Python\Python312;%LOCALAPPDATA%\Programs\Python\Python312\Scripts;%PATH%"

python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo  [!!] Python install failed. Install manually from https://python.org
    echo       Make sure to check "Add Python to PATH"!
    pause & exit /b 1
)
echo  [OK] Python installed!

:install_deps
echo.
echo  [..] Installing required packages...

python -m pip install --upgrade pip --quiet
python -m pip install playwright requests yt-dlp --quiet

echo  [..] Installing browser (one-time download ~150MB)...
python -m playwright install chromium

echo.
echo  ============================================
echo   Setup complete! 
echo   Now double-click RUN.bat to start scraping
echo  ============================================
echo.
pause
