@echo off
rem Double-click to play Realmwalker. The first run sets everything up automatically.
setlocal
cd /d "%~dp0"
title Realmwalker

if not exist ".venv\Scripts\python.exe" (
    echo Setting up Realmwalker for the first time. This takes a minute or two...
    call :find_python || goto :fail
    "%PY312%" -m venv .venv || goto :fail
)

rem Install or update the game's building blocks whenever the list changes.
fc /b requirements.txt ".venv\requirements.installed" >nul 2>nul
if errorlevel 1 (
    echo Installing game components...
    ".venv\Scripts\python.exe" -m pip install --upgrade pip --quiet
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt --quiet || goto :fail
    copy /y requirements.txt ".venv\requirements.installed" >nul
)

start "" ".venv\Scripts\pythonw.exe" main.py
exit /b 0

:find_python
set "PY312=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
if exist "%PY312%" exit /b 0
for /f "delims=" %%i in ('py -3.12 -c "import sys; print(sys.executable)" 2^>nul') do set "PY312=%%i"
if exist "%PY312%" exit /b 0
echo Installing Python 3.12 (free, from python.org via Windows' own installer)...
winget install -e --id Python.Python.3.12 --scope user --silent --accept-package-agreements --accept-source-agreements
set "PY312=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
if exist "%PY312%" exit /b 0
echo Could not install Python 3.12 automatically.
exit /b 1

:fail
echo.
echo Something went wrong while setting up. Please take a photo of this window and send it along.
pause
exit /b 1
