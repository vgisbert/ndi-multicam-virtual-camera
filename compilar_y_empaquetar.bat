@echo off
title NDI Virtual Camera - Compilador Nativo Tauri v2 (Sin Python)
echo ======================================================
echo    Compilando Release Nativo Tauri v2 para Windows 10
echo    (Binario ultra-ligero en Rust, sin dependencias)
echo ======================================================
echo.

set "CARGO_PATH=%USERPROFILE%\.cargo\bin"
set "WINGET_MINGW=%LOCALAPPDATA%\Microsoft\WinGet\Packages\BrechtSanders.WinLibs.POSIX.UCRT_Microsoft.Winget.Source_8wekyb3d8bbwe\mingw64\bin"
set "PATH=%WINGET_MINGW%;%CARGO_PATH%;%PATH%"
set "CARGO_TARGET_DIR=C:\Users\super\.cargo\target_vcam"

subst M: /d >nul 2>&1
subst M: "%~dp0." >nul 2>&1

cd /d "M:\src-tauri"
echo [1/3] Compilando binario nativo optimizado (Release)...
set RUSTFLAGS=-A linker-messages
cargo build --release

if errorlevel 1 (
    echo [ERROR] Error durante la compilacion de Rust.
    cd /d "%~dp0"
    subst M: /d >nul 2>&1
    pause
    exit /b 1
)

cd /d "%~dp0"
subst M: /d >nul 2>&1

echo.
echo [2/3] Empaquetando distribución nativa en 'dist_portable'...
if not exist "dist_portable" mkdir "dist_portable"

copy /Y "C:\Users\super\.cargo\target_vcam\release\ndi-virtual-camera.exe" "dist_portable\NDI-Virtual-Camera.exe" >nul
copy /Y "C:\Users\super\.cargo\target_vcam\release\WebView2Loader.dll" "dist_portable\WebView2Loader.dll" >nul 2>&1
if exist "core\lib\Processing.NDI.Lib.x64.dll" (
    copy /Y "core\lib\Processing.NDI.Lib.x64.dll" "dist_portable\Processing.NDI.Lib.x64.dll" >nul
)
if exist "config.json" (
    copy /Y "config.json" "dist_portable\config.json" >nul
)

:: Copiar driver multicamara
if not exist "dist_portable\driver" mkdir "dist_portable\driver"
xcopy /E /I /Y "driver\*" "dist_portable\driver\" >nul

:: Instrucciones claras
(
echo =============================================================================
echo      NDI VIRTUAL CAMERA - SUITE NATIVA PORTABLE (SIN PYTHON)
echo =============================================================================
echo.
echo INSTRUCCIONES PARA OTRO EQUIPO WINDOWS 10 / 11:
echo.
echo PASO 1 (Solo la primera vez que se use en este ordenador):
echo   Entra en la carpeta "driver" y haz clic derecho en:
echo       "instalar_driver_multicamara.bat" -^> Ejecutar como Administrador.
echo.
echo   Esto registrara los dos canales de camara virtual en Windows:
echo     - "Camara 1 - Frontal (NDI)"
echo     - "Camara 2 - Lateral (NDI)"
echo.
echo PASO 2:
echo   Haz doble clic en:
echo       "NDI-Virtual-Camera.exe"
echo.
echo La aplicacion arranca de forma nativa e instantanea, conectando las camaras
echo a los dos dispositivos virtuales para OBS Studio, Zoom, ManyCam, Teams, etc.
echo.
echo NOTA: No requiere instalar Python ni componentes pesados.
echo =============================================================================
) > "dist_portable\LEEME_WINDOWS_10.txt"

echo.
echo [3/3] Comprimiendo paquete ZIP para pendrive...
powershell -NoProfile -Command "Compress-Archive -Path 'dist_portable\*' -DestinationPath 'dist_portable\NDI_Virtual_Camera_Native_Portable.zip' -Force" >nul 2>&1

echo.
echo ======================================================
echo  [LISTO] Paquete nativo generado con exito en:
echo         %~dp0dist_portable\
echo.
echo  Archivo ZIP listo para pendrive:
echo         %~dp0dist_portable\NDI_Virtual_Camera_Native_Portable.zip
echo ======================================================
echo.
