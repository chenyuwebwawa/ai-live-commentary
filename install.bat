@echo off
rem ============================================================
rem  AI Live Commentary - installer
rem  Creates a local .venv and installs the Python dependencies.
rem  ffmpeg is NOT required: the app falls back to the binary
rem  bundled with the imageio-ffmpeg package.
rem ============================================================
chcp 65001 >nul
set PYTHONUTF8=1
title AI Live Commentary - install
cd /d "%~dp0"

set "BASEPY="
for /f "delims=" %%i in ('where python 2^>nul') do if not defined BASEPY set "BASEPY=%%i"
if not defined BASEPY (
  echo.
  echo   [X] Python not found on PATH. Install Python 3.11+ from https://www.python.org/downloads/
  echo.
  pause
  exit /b 1
)

echo.
echo   Using Python: %BASEPY%
"%BASEPY%" -c "import sys; assert sys.version_info >= (3, 11), sys.version; print('Python', sys.version.split()[0], 'OK')"
if errorlevel 1 (
  echo   [X] Need Python 3.11 or newer.
  pause
  exit /b 1
)

if not exist "%~dp0.venv\Scripts\python.exe" (
  echo   Creating virtual environment .venv ...
  "%BASEPY%" -m venv "%~dp0.venv"
)

echo   Installing dependencies ...
"%~dp0.venv\Scripts\python.exe" -m pip install --upgrade pip
"%~dp0.venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
  echo   [!] Direct install failed, retrying with the Tsinghua mirror ...
  "%~dp0.venv\Scripts\python.exe" -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
)

echo.
echo   Done. Now run start.bat
echo.
pause
