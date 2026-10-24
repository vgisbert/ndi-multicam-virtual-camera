@echo off
title NDI Virtual Camera - Instalador Multicamara
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0instalar_multicamara.ps1"
if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Se produjo un error al ejecutar el instalador.
    pause
)
