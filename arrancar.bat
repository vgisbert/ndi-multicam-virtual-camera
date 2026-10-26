@echo off
title NDI Virtual Camera - Launcher
echo ======================================================
echo    NDI Virtual Camera - Broadcast Suite
echo    Windows 10 DirectShow Virtual Camera ^& NDI Receiver
echo ======================================================
echo.

:: Mapear unidad virtual V: para aislar rutas con espacios o tildes
subst V: /d >nul 2>&1
subst V: "%~dp0." >nul 2>&1

if exist "V:\core" (
    cd /d "V:\"
) else (
    cd /d "%~dp0"
)

echo [1/3] Verificando entorno Python...
where python >nul 2>&1
if errorlevel 1 (
    echo [ERROR] No se encontro Python en el PATH del sistema.
    echo Por favor, instala Python 3.10+ y marca la casilla 'Add Python to PATH'.
    pause
    subst V: /d >nul 2>&1
    exit /b 1
)

:: Gestion inteligente del entorno virtual en core\venv
if not exist "core\venv\Scripts\python.exe" (
    echo [2/3] Creando entorno virtual aislado en core\venv...
    if exist "core\venv" rmdir /s /q "core\venv"
    python -m venv core\venv
    if errorlevel 1 (
        echo [ERROR] No se pudo crear el entorno virtual.
        pause
        subst V: /d >nul 2>&1
        exit /b 1
    )
    echo   [OK] Entorno virtual creado.
    echo   [INFO] Instalando dependencias base...
    core\venv\Scripts\python.exe -m pip install --upgrade pip >nul 2>&1
    if exist "core\requirements.txt" (
        core\venv\Scripts\python.exe -m pip install -r core\requirements.txt
    )
) else (
    echo [2/3] Entorno virtual verificado en core\venv.
)

:: Verificar si el driver DirectShow esta registrado
echo [3/3] Verificando estado del filtro de camara virtual...
reg query "HKCR\CLSID\{860BB310-5D01-11d0-BD3B-00A0C911CE86}\Instance" /s /f "Unity" >nul 2>&1
if errorlevel 1 (
    reg query "HKCR\CLSID\{860BB310-5D01-11d0-BD3B-00A0C911CE86}\Instance" /s /f "Virtual" >nul 2>&1
)
if errorlevel 1 (
    echo   [AVISO] No se detecto el filtro DirectShow registrado en Windows.
    echo   Si es la primera vez que ejecutas el proyecto en este equipo, ejecuta:
    echo     driver\instalar_driver_multicamara.bat (como Administrador)
    echo.
) else (
    echo   [OK] Filtro DirectShow registrado y activo.
)

echo.
echo Iniciando NDI Virtual Camera...
echo ======================================================

:: Liberar puerto 8765 si quedo retenido por alguna sesion previa
for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| findstr ":8765"') do (
    if not "%%a"=="0" taskkill /f /pid %%a >nul 2>&1
)

if exist "core\main.py" (
    core\venv\Scripts\python.exe -u core\main.py
) else (
    echo [INFO] Estructura inicial preparada. Consulta DOCUMENTACION.md y PLAN_DE_TRABAJO.md
    pause
)

:: Limpiar mapeo virtual al salir
cd /d "%~dp0"
subst V: /d >nul 2>&1
exit /b 0
