@echo off
title NDI Virtual Camera - Desinstalador Multicamara
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0desinstalar_multicamara.ps1"
if %errorlevel% neq 0 pause
