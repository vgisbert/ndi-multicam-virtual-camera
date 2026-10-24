# NDI Virtual Camera - Instalador DirectShow Multicamara (PowerShell Nativo)
# Permite registrar 2 camaras virtuales simultaneas en Windows

$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "[INFO] Solicitando permisos de Administrador..." -ForegroundColor Yellow
    Start-Process powershell.exe -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`"" -Verb RunAs
    exit
}

Write-Host "======================================================" -ForegroundColor Cyan
Write-Host "   NDI Virtual Camera - Instalador Multicamara" -ForegroundColor Cyan
Write-Host "   (2 Dispositivos Virtuales Simultaneos en Windows)" -ForegroundColor Cyan
Write-Host "======================================================" -ForegroundColor Cyan
Write-Host ""

$dir = Split-Path -Parent $PSCommandPath
Set-Location $dir

# 1. Registrar DLL de 64 bits
$dll64 = Join-Path $dir "UnityCaptureFilter64.dll"
Write-Host "[1/3] Registrando dispositivos en 64 bits con UnityCaptureFilter64.dll..." -ForegroundColor Yellow
if (Test-Path $dll64) {
    $proc = Start-Process regsvr32.exe -ArgumentList "/s /i:UnityCaptureDevices=2 `"$dll64`"" -Wait -PassThru
    if ($proc.ExitCode -eq 0) {
        Write-Host "  [OK] Filtro de 64 bits registrado exitosamente." -ForegroundColor Green
    } else {
        Write-Host "  [ERROR] Fallo al registrar filtro de 64 bits (Codigo: $($proc.ExitCode))." -ForegroundColor Red
    }
} else {
    Write-Host "  [ERROR] No se encontro UnityCaptureFilter64.dll en: $dir" -ForegroundColor Red
}

# 2. Registrar DLL de 32 bits (opcional)
$dll32 = Join-Path $dir "UnityCaptureFilter32.dll"
if (Test-Path $dll32) {
    Write-Host "`n[2/3] Registrando compatibilidad de 32 bits..." -ForegroundColor Yellow
    $proc32 = Start-Process regsvr32.exe -ArgumentList "/s /i:UnityCaptureDevices=2 `"$dll32`"" -Wait -PassThru
    if ($proc32.ExitCode -eq 0) {
        Write-Host "  [OK] Filtro de 32 bits registrado." -ForegroundColor Green
    }
} else {
    Write-Host "`n[2/3] Filtro de 32 bits omitido (opcional)." -ForegroundColor DarkGray
}

# 3. Asignar nombres amigables en DirectShow
Write-Host "`n[3/3] Asignando nombres amigables en DirectShow..." -ForegroundColor Yellow
$instKey = "HKLM:\SOFTWARE\Classes\CLSID\{860BB310-5D01-11d0-BD3B-00A0C911CE86}\Instance"

try {
    $keys = Get-ChildItem $instKey -ErrorAction SilentlyContinue

    $k1 = $keys | Where-Object { 
        $fn = (Get-ItemProperty $_.PSPath).FriendlyName
        $fn -like "*Unity Video Capture*" -and $fn -notlike "*#2*" -or $fn -like "*Camara 1*"
    }
    $k2 = $keys | Where-Object { 
        $fn = (Get-ItemProperty $_.PSPath).FriendlyName
        $fn -like "*Unity Video Capture #2*" -or $fn -like "*#2*" -or $fn -like "*Camara 2*"
    }

    if ($k1) {
        Set-ItemProperty -Path $k1[0].PSPath -Name "FriendlyName" -Value "Camara 1 - Frontal (NDI)"
        Write-Host "  [OK] Dispositivo 1 configurado: 'Camara 1 - Frontal (NDI)'" -ForegroundColor Green
    }

    if ($k2) {
        Set-ItemProperty -Path $k2[0].PSPath -Name "FriendlyName" -Value "Camara 2 - Lateral (NDI)"
        Write-Host "  [OK] Dispositivo 2 configurado: 'Camara 2 - Lateral (NDI)'" -ForegroundColor Green
    }
} catch {
    Write-Host "  [AVISO] No se pudo renombrar en registro: $($_.Exception.Message)" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "======================================================" -ForegroundColor Cyan
Write-Host "  Instalacion multicamara completada con exito." -ForegroundColor Green
Write-Host "  Dispositivos listos para OBS, ManyCam, Zoom y Teams:" -ForegroundColor Green
Write-Host "    1. Camara 1 - Frontal (NDI)" -ForegroundColor White
Write-Host "    2. Camara 2 - Lateral (NDI)" -ForegroundColor White
Write-Host "======================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Presiona cualquier tecla para cerrar esta ventana..." -ForegroundColor DarkGray
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
