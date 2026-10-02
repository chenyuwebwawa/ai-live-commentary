@echo off
rem ============================================================
rem  AI Live Commentary - one-click start
rem  Finds a usable Python environment and starts the web app.
rem ============================================================
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
title AI Live Commentary
cd /d "%~dp0"

set "PY="
rem 1) project-local venv
if exist "%~dp0.venv\Scripts\python.exe" set "PY=%~dp0.venv\Scripts\python.exe"
rem 2) explicit override
if not defined PY if exist "%LIVECC_PYTHON%" set "PY=%LIVECC_PYTHON%"
rem 3) legacy location used by the first setup on this machine
if not defined PY if exist "D:\AI\live-commentary-venv\Scripts\python.exe" set "PY=D:\AI\live-commentary-venv\Scripts\python.exe"
rem 4) system python
if not defined PY (
  for /f "delims=" %%i in ('where python 2^>nul') do if not defined PY set "PY=%%i"
)

if not defined PY (
  echo.
  echo   [X] Python not found. Run install.bat first.
  echo.
  pause
  exit /b 1
)

echo.
echo   ============================================================
echo     AI Live Commentary Workbench
echo     Python : %PY%
echo     Open in browser:  http://127.0.0.1:8848
echo     Close this window to stop the server.
echo   ============================================================
echo.

"%PY%" -m app.main
pause
