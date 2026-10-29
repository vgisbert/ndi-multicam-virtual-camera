"""
Script de Copia de Seguridad Automatizada - NDI Virtual Camera Suite
Arquitectura conforme a GUIA_CONTEXTO_PROBLEMAS_ENTORNO_Y_BACKUP.md
Genera resguardo timestamped en carpeta y archivo .zip en backups/
"""

import os
import shutil
import datetime
import zipfile

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BACKUPS_DIR = os.path.join(BASE_DIR, "backups")

# Lista exhaustiva y categorizada de elementos clave a respaldar
FILES_TO_BACKUP = [
    # Control de versiones y configuración
    ".gitignore",
    "config.json",
    "README.md",
    
    # Documentación técnica y especificaciones
    "DOCUMENTACION.md",
    "PLAN_DE_TRABAJO.md",
    "GUIA_COMPILACION_NATIVA_TAURI_RUST.md",
    "GUIA_CONTEXTO_PROBLEMAS_ENTORNO_Y_BACKUP.md",
    "Guia_Inicio_Nuevos_Proyectos.md",
    "LEEME_WINDOWS_10.txt",
    
    # Scripts de arranque, compilación y resguardo
    "arrancar.bat",
    "compilar_y_empaquetar.bat",
    "build_exe.py",
    "backup.py",
    
    # Código fuente de Frontend y UI
    "ui",
    "frontend",
    "docs",
    
    # Código fuente de Backend Python (se excluyen venv y caches en la copia)
    "core",
    
    # Motor nativo Rust / Tauri (se excluyen targets binarios)
    "src-tauri",
]

# Patrones globales a ignorar en directorios
IGNORE_PATTERNS = shutil.ignore_patterns(
    "venv", ".venv", "__pycache__", "*.pyc", "*.pyo", "*.pyd",
    "target", "*.log", "*.tmp", "*.old", "*.mkv", "*.mp4", "*.avi"
)

def make_backup():
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"backup_{timestamp}"
    backup_path = os.path.join(BACKUPS_DIR, backup_name)
    
    print("=" * 65)
    print("   NDI VIRTUAL CAMERA - SISTEMA DE COPIA DE SEGURIDAD")
    print(f"   Destino: backups/{backup_name}")
    print("=" * 65)
    
    os.makedirs(backup_path, exist_ok=True)
    
    copied_count = 0
    total_bytes = 0

    for rel_path in FILES_TO_BACKUP:
        src = os.path.join(BASE_DIR, rel_path)
        dst = os.path.join(backup_path, rel_path)
        
        if os.path.exists(src):
            if os.path.isdir(src):
                shutil.copytree(src, dst, dirs_exist_ok=True, ignore=IGNORE_PATTERNS)
                # Calcular tamaño del directorio copiado
                dir_size = sum(os.path.getsize(os.path.join(r, f)) for r, _, fs in os.walk(dst) for f in fs)
                total_bytes += dir_size
                print(f"  [OK] (Directorio) {rel_path} (~{dir_size / (1024 * 1024):.2f} MB)")
            else:
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copy2(src, dst)
                size = os.path.getsize(src)
                total_bytes += size
                print(f"  [OK] (Archivo)    {rel_path} ({size:,} bytes)")
            copied_count += 1
        else:
            print(f"  [Omitido]         {rel_path} (No existe en origen)")
            
    # Generar también archivo comprimido ZIP
    zip_path = os.path.join(BACKUPS_DIR, f"{backup_name}.zip")
    print(f"\nGenerando archivo comprimido .zip en:\n  {zip_path}...")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, _, files in os.walk(backup_path):
            for file in files:
                abs_file = os.path.join(root, file)
                rel_zip = os.path.relpath(abs_file, backup_path)
                zf.write(abs_file, rel_zip)
    
    zip_size_mb = os.path.getsize(zip_path) / (1024 * 1024)
    mb_total = total_bytes / (1024 * 1024)
    
    print("\n" + "=" * 65)
    print("COPIA DE SEGURIDAD COMPLETADA CON ÉXITO")
    print(f"Elementos respaldados : {copied_count} entradas")
    print(f"Tamaño sin comprimir  : ~{mb_total:.2f} MB")
    print(f"Tamaño archivo .zip   : ~{zip_size_mb:.2f} MB")
    print(f"Carpeta resguardo     : {backup_path}")
    print(f"Archivo empaquetado   : {zip_path}")
    print("=" * 65)

if __name__ == "__main__":
    make_backup()
