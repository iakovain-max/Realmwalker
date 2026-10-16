@echo off
rem Realmwalker: tells the building session to finish its step, save its work and stop (docs/expansions/RELAY.md).
if not exist "%~dp0build" mkdir "%~dp0build"
echo %date% %time% > "%~dp0build\STOP"
echo.
echo STOP written. The session that is building will finish its current step, save its work and stop.
echo The safety net stops itself at its next check. Press "Realmwalker: START" in the Claude app to start again.
echo.
pause
