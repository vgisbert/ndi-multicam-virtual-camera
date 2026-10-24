import os
import shutil
import datetime

# Directorio base y de copias de seguridad
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BACKUPS_DIR = os.path.join(BASE_DIR, "backups")

# Lista exhaustiva y categorizada de elementos a respaldar
FILES_TO_BACKUP = [
    # Módulos y código fuente Python
    "driver",
    "core",
    "ui",
    "docs",
    
    # Motor nativo Tauri v2 / Rust
    "src-tauri",
    "frontend",
    
    # Configuración del sistema
    "config.json",
    
    # Lanzadores y mantenimiento
    "arrancar.bat",
    "compilar_y_empaquetar.bat",
    "build_exe.py",
    "backup.py",
    
    # Documentación técnica
    "DOCUMENTACION.md",
    "PLAN_DE_TRABAJO.md",
    "Guia_Inicio_Nuevos_Proyectos.md",
    "GUIA_CONTEXTO_PROBLEMAS_ENTORNO_Y_BACKUP.md",
    "GUIA_COMPILACION_NATIVA_TAURI_RUST.md"
]

def make_backup():
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = os.path.join(BACKUPS_DIR, f"backup_{timestamp}")
    
    print(f"Iniciando copia de seguridad de NDI Virtual Camera en:\n  {backup_path}\n")
    os.makedirs(backup_path, exist_ok=True)
    
    copied_count = 0
    total_bytes = 0

    for rel_path in FILES_TO_BACKUP:
        src = os.path.join(BASE_DIR, rel_path)
        dst = os.path.join(backup_path, rel_path)
        
        if os.path.exists(src):
            if os.path.isdir(src):
                ignore_func = shutil.ignore_patterns("venv", "__pycache__", "*.pyc", ".git", "target", "node_modules")
                shutil.copytree(src, dst, dirs_exist_ok=True, ignore=ignore_func)
                # Calcular tamaño acumulado de la carpeta
                folder_bytes = sum(
                    os.path.getsize(os.path.join(r, f))
                    for r, d, files in os.walk(dst)
                    for f in files
                )
                total_bytes += folder_bytes
                print(f"  [OK] (Carpeta) Copiado: {rel_path} ({folder_bytes:,} bytes)")
            else:
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copy2(src, dst)
                size = os.path.getsize(src)
                total_bytes += size
                print(f"  [OK] Copiado: {rel_path} ({size:,} bytes)")
            copied_count += 1
        else:
            print(f"  [Omitido] No existe: {rel_path}")
            
    mb_total = total_bytes / (1024 * 1024)
    print(f"\n======================================================")
    print(f"Copia de seguridad completada con exito.")
    print(f"Archivos respaldados: {copied_count} elementos (~{mb_total:.2f} MB)")
    print(f"Destino: {backup_path}")
    print(f"======================================================")

if __name__ == "__main__":
    make_backup()
