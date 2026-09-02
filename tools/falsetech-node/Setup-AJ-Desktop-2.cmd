@echo off
set SCRIPT=%~dp0Install-FalseTechNode.ps1
PowerShell.exe -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT%" -DeviceName "AJ-Desktop-2"
pause
