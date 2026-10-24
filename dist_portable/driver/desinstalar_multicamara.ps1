# NDI Virtual Camera - Desinstalador Multicamara (PowerShell Nativo)

$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "[INFO] Solicitando permisos de Administrador..." -ForegroundColor Yellow
    Start-Process powershell.exe -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`"" -Verb RunAs
    exit
}

Write-Host "======================================================" -ForegroundColor Cyan
Write-Host "   NDI Virtual Camera - Desinstalador Multicamara" -ForegroundColor Cyan
Write-Host "======================================================" -ForegroundColor Cyan
Write-Host ""

$dir = Split-Path -Parent $PSCommandPath
Set-Location $dir

$dll64 = Join-Path $dir "UnityCaptureFilter64.dll"
if (Test-Path $dll64) {
    Write-Host "Desregistrando filtro de 64 bits..." -ForegroundColor Yellow
    Start-Process regsvr32.exe -ArgumentList "/u /s `"$dll64`"" -Wait
    Write-Host "  [OK] Filtro de 64 bits desregistrado." -ForegroundColor Green
}

$dll32 = Join-Path $dir "UnityCaptureFilter32.dll"
if (Test-Path $dll32) {
    Write-Host "Desregistrando filtro de 32 bits..." -ForegroundColor Yellow
    Start-Process regsvr32.exe -ArgumentList "/u /s `"$dll32`"" -Wait
    Write-Host "  [OK] Filtro de 32 bits desregistrado." -ForegroundColor Green
}

Write-Host ""
Write-Host "Dispositivos multicamara retirados del sistema de Windows." -ForegroundColor Green
Write-Host "Presiona cualquier tecla para cerrar esta ventana..." -ForegroundColor DarkGray
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
