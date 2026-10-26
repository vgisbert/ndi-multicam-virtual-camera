"""
Build Script for NDI Virtual Camera Standalone Windows Executable
Packages the complete application into a portable, standalone distribution.
"""

import os
import sys
import shutil
import zipfile
import subprocess

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE_DIR)

VENV_PY = os.path.join(BASE_DIR, "core", "venv", "Scripts", "python.exe")
if not os.path.exists(VENV_PY):
    VENV_PY = sys.executable

print("=" * 65)
print("   NDI VIRTUAL CAMERA - COMPILADOR A EJECUTABLE (.EXE)")
print("   Generando distribucion portable para Windows 10/11")
print("=" * 65)

# 1. Crear el archivo spec optimizado
spec_content = '''# -*- mode: python ; coding: utf-8 -*-
import os
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

datas = [
    ('ui', 'ui'),
]
try:
    datas += collect_data_files('pythonnet')
except Exception:
    pass
try:
    datas += collect_data_files('webview')
except Exception:
    pass

binaries = [
    ('core/lib/Processing.NDI.Lib.x64.dll', 'core/lib'),
    ('core/lib/Processing.NDI.Lib.x64.dll', '.'),
]

hiddenimports = [
    'clr',
    'pythonnet',
    'webview',
    'webview.platforms.winforms',
    'pyvirtualcam._native_windows_unity_capture',
    'pyvirtualcam._native_windows_obs',
    'cv2',
    'numpy',
    'recorder',
    'video_pipeline',
    'discovery',
    'virtual_cam',
    'ndi_wrapper',
    'unicodedata',
    'queue',
]
try:
    hiddenimports += collect_submodules('webview')
except Exception:
    pass
try:
    hiddenimports += collect_submodules('pyvirtualcam')
except Exception:
    pass

a = Analysis(
    ['core/main.py'],
    pathex=['.', 'core'],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'torch', 'torchaudio', 'torchvision', 'transformers', 
        'scipy', 'nltk', 'surya', 'marker', 'bitsandbytes',
        'matplotlib', 'pandas', 'IPython', 'jupyter'
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='NDI Virtual Camera',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    icon='ui/icon.ico',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='NDI Virtual Camera',
)
'''

spec_path = os.path.join(BASE_DIR, "ndi_virtual_camera.spec")
with open(spec_path, "w", encoding="utf-8") as f:
    f.write(spec_content)

print("[1/4] Archivo de especificacion PyInstaller preparado.")

# 2. Ejecutar PyInstaller
print("[2/4] Compilando con PyInstaller (esto puede tardar 1-2 minutos)...")
cmd = [VENV_PY, "-m", "PyInstaller", "--clean", "-y", spec_path]
proc = subprocess.run(cmd, capture_output=True, text=True)

if proc.returncode != 0:
    print("[ERROR] Fallo la compilacion:")
    print(proc.stderr[-2000:] if proc.stderr else proc.stdout[-2000:])
    sys.exit(1)

dist_app_dir = os.path.join(BASE_DIR, "dist", "NDI Virtual Camera")
if not os.path.exists(dist_app_dir):
    print(f"[ERROR] No se encontro el directorio de salida: {dist_app_dir}")
    sys.exit(1)

print("  [OK] Binario compilado exitosamente.")

# 3. Empaquetar driver, config y guia de uso
print("[3/4] Integrando archivos auxiliares (driver, config.json, instrucciones)...")

# Copiar config.json base
shutil.copy2(os.path.join(BASE_DIR, "config.json"), os.path.join(dist_app_dir, "config.json"))

# Copiar ffmpeg.exe para grabacion autonoma en Windows 10
ffmpeg_src = shutil.which("ffmpeg")
if ffmpeg_src and os.path.exists(ffmpeg_src):
    shutil.copy2(ffmpeg_src, os.path.join(dist_app_dir, "ffmpeg.exe"))
    print("  [OK] ffmpeg.exe integrado para grabacion autonoma en Windows 10.")

# Copiar Processing.NDI.Lib.x64.dll al directorio principal
ndi_dll = os.path.join(BASE_DIR, "core", "lib", "Processing.NDI.Lib.x64.dll")
if os.path.exists(ndi_dll):
    shutil.copy2(ndi_dll, os.path.join(dist_app_dir, "Processing.NDI.Lib.x64.dll"))
    print("  [OK] Processing.NDI.Lib.x64.dll integrado.")

# Copiar carpeta driver completa
dist_driver_dir = os.path.join(dist_app_dir, "driver")
if os.path.exists(dist_driver_dir):
    shutil.rmtree(dist_driver_dir)
shutil.copytree(os.path.join(BASE_DIR, "driver"), dist_driver_dir)

# Crear archivo de instrucciones claro para el nuevo equipo
readme_text = """=============================================================================
             NDI VIRTUAL CAMERA - SUITE MULTICAMARA PORTABLE
=============================================================================

INSTRUCCIONES PARA EJECUTAR EN UN NUEVO EQUIPO WINDOWS 10 / 11:
-----------------------------------------------------------------------------

PASO 1 (Solo la primera vez que se use en este ordenador):
  Entra en la carpeta "driver" y haz clic derecho en:
      "instalar_driver_multicamara.bat" -> Ejecutar como Administrador.
  
  Esto registrara en Windows los dos dispositivos virtuales:
    - "Camara 1 - Frontal (NDI)"
    - "Camara 2 - Lateral (NDI)"
  quedando disponibles de inmediato para OBS, Zoom, ManyCam, Teams, etc.

PASO 2:
  Haz doble clic en:
      "NDI Virtual Camera.exe"
  
  La aplicacion abrira la consola tactica en pantalla, detectara las camaras
  en la red local y activara la transmision a los dos dispositivos virtuales.

BOTONES Y FUNCIONES PRINCIPALES:
- BOTON REC: Graba simultaneamente ambas camaras en formato MKV (H.264)
  utilizando automaticamente la tarjeta grafica NVIDIA, Intel QuickSync o CPU.
- BOTON VISTA ON / ECO: Permite pausar la previsualizacion en pantalla para
  reducir el uso de CPU al minimo sin interrumpir la camara virtual ni la grabacion.
- BOTON RUEDA AJUSTES (Aspa X para guardar y salir): Configura IPs de camaras,
  alias/nombres unicos, tasa de refresco (2/4/8 FPS) y carpeta de grabaciones.

NOTAS IMPORTANTES:
- Asegurate de que este equipo este conectado a la misma red local que las
  camaras (ej. IPs 192.168.9.108 y 192.168.9.171). Si las camaras tienen otras IPs,
  puedes cambiarlas en la pantalla de Ajustes o en el archivo "config.json".
- No es necesario tener Python ni NDI Runtime instalado en el equipo.
=============================================================================
"""

with open(os.path.join(dist_app_dir, "LEEME_WINDOWS_10.txt"), "w", encoding="utf-8") as f:
    f.write(readme_text)

print("  [OK] Archivos auxiliares e instrucciones integrados.")

# 4. Crear archivo ZIP portable listo para pendrive y sincronizar dist_portable
print("[4/4] Creando paquete comprimido ZIP para pendrive/red...")
zip_target = os.path.join(BASE_DIR, "dist", "NDI_Virtual_Camera_Portable.zip")
if os.path.exists(zip_target):
    os.remove(zip_target)

with zipfile.ZipFile(zip_target, "w", zipfile.ZIP_DEFLATED) as zipf:
    for root, _, files in os.walk(dist_app_dir):
        for file in files:
            file_path = os.path.join(root, file)
            arcname = os.path.relpath(file_path, os.path.dirname(dist_app_dir))
            zipf.write(file_path, arcname)

zip_size_mb = os.path.getsize(zip_target) / (1024 * 1024)
print(f"  [OK] Paquete ZIP generado: {zip_target} ({zip_size_mb:.1f} MB)")

# Sincronizar tambien con carpeta dist_portable
dist_portable_dir = os.path.join(BASE_DIR, "dist_portable")
os.makedirs(dist_portable_dir, exist_ok=True)
for item in os.listdir(dist_app_dir):
    s = os.path.join(dist_app_dir, item)
    d = os.path.join(dist_portable_dir, item)
    if os.path.isdir(s):
        if os.path.exists(d):
            shutil.rmtree(d)
        shutil.copytree(s, d)
    else:
        shutil.copy2(s, d)

zip_portable_target = os.path.join(dist_portable_dir, "NDI_Virtual_Camera_Portable.zip")
shutil.copy2(zip_target, zip_portable_target)
print(f"  [OK] Sincronizado en dist_portable/ ({zip_portable_target})")

print("\n" + "=" * 65)
print("COMPILACION COMPLETADA CON EXITO!")
print("Carpeta lista para probar:")
print(f"  -> {dist_app_dir}")
print("Archivo ZIP para llevar en pendrive a Windows 10:")
print(f"  -> {zip_target}")
print(f"  -> {zip_portable_target}")
print("=" * 65)
