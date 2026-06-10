@echo off
powershell.exe -ExecutionPolicy Bypass -NoProfile -File "%~dp0StartSession.ps1"
if errorlevel 1 pause
