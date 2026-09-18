@echo off
rem Double-click to package Realmwalker for friends: creates Realmwalker.zip in this folder.
setlocal
cd /d "%~dp0"
title Realmwalker - build for friends

if not exist ".venv\Scripts\python.exe" (
    echo Please double-click Play.bat once first, so everything gets set up.
    pause
    exit /b 1
)

".venv\Scripts\python.exe" tools\build_friends.py
if errorlevel 1 (
    echo.
    echo The build did not finish. Please take a photo of this window and send it along.
    pause
    exit /b 1
)
explorer /select,"%~dp0Realmwalker.zip"
pause
