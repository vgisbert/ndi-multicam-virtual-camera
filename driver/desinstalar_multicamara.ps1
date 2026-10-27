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

# Cerrar cualquier instancia previa que pueda retener bloqueada la DLL en memoria
Get-Process -Name "NDI Virtual Camera" -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue

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

# Limpieza profunda de claves residuales de DirectShow y CLSID
Write-Host "`nLimpiando claves del Registro de Windows..." -ForegroundColor Yellow

$roots = @("HKLM:\SOFTWARE\Classes", "HKLM:\SOFTWARE\WOW6432Node\Classes", "HKCU:\Software\Classes")
$clsids = @(
    "{5C2CD55C-92AD-4999-8666-912BD3E70010}",
    "{5C2CD55C-92AD-4999-8666-912BD3E70012}",
    "{5C2CD55C-92AD-4999-8666-912BD3E70020}",
    "{5C2CD55C-92AD-4999-8666-912BD3E70022}"
)

foreach ($r in $roots) {
    foreach ($c in $clsids) {
        $instKey = "$r\CLSID\{860BB310-5D01-11d0-BD3B-00A0C911CE86}\Instance\$c"
        if (Test-Path $instKey) {
            Remove-Item -Path $instKey -Recurse -Force -ErrorAction SilentlyContinue
        }
        $clsidKey = "$r\CLSID\$c"
        if (Test-Path $clsidKey) {
            Remove-Item -Path $clsidKey -Recurse -Force -ErrorAction SilentlyContinue
        }
    }
}
Write-Host "  [OK] Registro de Windows limpio de dispositivos virtuales anteriores." -ForegroundColor Green

Write-Host ""
Write-Host "Dispositivos multicamara retirados por completo del sistema." -ForegroundColor Green
Write-Host "Presiona cualquier tecla para cerrar esta ventana..." -ForegroundColor DarkGray
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
