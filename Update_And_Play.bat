@echo off
rem Double-click to get the newest version of the game and play it.
setlocal
cd /d "%~dp0"
title Realmwalker - getting the newest version

where git >nul 2>nul || goto :nogit
git rev-parse --is-inside-work-tree >nul 2>nul || goto :norepo
git remote get-url origin >nul 2>nul || goto :noremote

echo Looking for a newer version...
git pull --ff-only
if errorlevel 1 goto :pullfailed
echo.
echo Up to date. Starting the game...
goto :play

:play
start "" cmd /c Play.bat
exit /b 0

:nogit
echo Git is not installed, so this cannot fetch updates.
echo You can still play: double-click Play.bat instead.
pause
exit /b 1

:norepo
echo This folder is not a copy of the Realmwalker repository, so there is nothing to update.
echo You can still play: double-click Play.bat instead.
pause
exit /b 1

:noremote
echo This copy is not linked to GitHub yet, so there is nothing to fetch.
echo You can still play: double-click Play.bat instead.
pause
exit /b 1

:pullfailed
echo.
echo Could not fetch the newest version. You may be offline, or this copy has changes
echo of its own that would be overwritten. Nothing has been changed or lost.
echo You can still play the version you have: double-click Play.bat.
pause
exit /b 1
