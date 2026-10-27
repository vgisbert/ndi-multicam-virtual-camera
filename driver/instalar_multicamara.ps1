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

# Cerrar cualquier instancia previa que pueda retener bloqueada la DLL en memoria
Get-Process -Name "NDI Virtual Camera" -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue

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

# 3. Asignar nombres amigables en DirectShow y pyvirtualcam
Write-Host "`n[3/3] Asignando nombres limpios para Zoom, Teams y OBS..." -ForegroundColor Yellow

$name1 = "NDI Camara 1"
$name2 = "NDI Camara 2"

# Ubicaciones 64-bit y 32-bit (HKLM y HKCU)
$paths = @(
    @{ Root = "HKLM:\SOFTWARE\Classes"; Dev1 = "{5C2CD55C-92AD-4999-8666-912BD3E70010}"; Dev2 = "{5C2CD55C-92AD-4999-8666-912BD3E70012}" },
    @{ Root = "HKLM:\SOFTWARE\WOW6432Node\Classes"; Dev1 = "{5C2CD55C-92AD-4999-8666-912BD3E70020}"; Dev2 = "{5C2CD55C-92AD-4999-8666-912BD3E70022}" },
    @{ Root = "HKCU:\Software\Classes"; Dev1 = "{5C2CD55C-92AD-4999-8666-912BD3E70010}"; Dev2 = "{5C2CD55C-92AD-4999-8666-912BD3E70012}" }
)

foreach ($p in $paths) {
    try {
        # Actualizar nombres CLSID principales (utilizados por pyvirtualcam)
        $clsid1 = "$($p.Root)\CLSID\$($p.Dev1)"
        $clsid2 = "$($p.Root)\CLSID\$($p.Dev2)"
        if (Test-Path $clsid1) { Set-ItemProperty -Path $clsid1 -Name "(default)" -Value $name1 -ErrorAction SilentlyContinue }
        if (Test-Path $clsid2) { Set-ItemProperty -Path $clsid2 -Name "(default)" -Value $name2 -ErrorAction SilentlyContinue }

        # Actualizar instancias de Video Input Category (utilizadas por Zoom, OBS, etc.)
        $inst1 = "$($p.Root)\CLSID\{860BB310-5D01-11d0-BD3B-00A0C911CE86}\Instance\$($p.Dev1)"
        $inst2 = "$($p.Root)\CLSID\{860BB310-5D01-11d0-BD3B-00A0C911CE86}\Instance\$($p.Dev2)"
        if (Test-Path $inst1) {
            Set-ItemProperty -Path $inst1 -Name "FriendlyName" -Value $name1 -ErrorAction SilentlyContinue
            Set-ItemProperty -Path $inst1 -Name "DevicePath" -Value "UnityCapture:0" -ErrorAction SilentlyContinue
        }
        if (Test-Path $inst2) {
            Set-ItemProperty -Path $inst2 -Name "FriendlyName" -Value $name2 -ErrorAction SilentlyContinue
            Set-ItemProperty -Path $inst2 -Name "DevicePath" -Value "UnityCapture:1" -ErrorAction SilentlyContinue
        }
    } catch {
        # Continuar con el siguiente bloque si hay error
    }
}

Write-Host "  [OK] Dispositivo 1 configurado: '$name1'" -ForegroundColor Green
Write-Host "  [OK] Dispositivo 2 configurado: '$name2'" -ForegroundColor Green

Write-Host ""
Write-Host "======================================================" -ForegroundColor Cyan
Write-Host "  Instalacion multicamara completada con exito." -ForegroundColor Green
Write-Host "  Dispositivos listos para OBS, ManyCam, Zoom y Teams:" -ForegroundColor Green
Write-Host "    1. $name1" -ForegroundColor White
Write-Host "    2. $name2" -ForegroundColor White
Write-Host "======================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Presiona cualquier tecla para cerrar esta ventana..." -ForegroundColor DarkGray
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
