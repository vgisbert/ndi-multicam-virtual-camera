# Guía de Contexto Técnico: Diagnóstico y Resolución de Entornos Virtuales y Respaldos en Proyectos Híbridos (Windows / Python + Node.js)

> **Propósito de este documento:**  
> Servir como referencia técnica reutilizable e inyectable en hilos de conversación, documentación de repositorios o prompts para agentes de IA en proyectos con arquitectura similar (FastAPI / Python + Electron / Tauri / Frontend sobre Windows).
>
> 💡 **Nota de aplicación:**  
> En proyectos que implementan motores nativos en **Rust y Tauri v2**, se evita por diseño la fragilidad de runtimes y entornos virtuales de Python para la lógica de bajo nivel. No obstante, este documento se adopta transversalmente en el ecosistema Antigravity por dos motivos clave:  
> 1. **Fundamentación de `backup.py`:** Las secciones 2 y 3.2 explican y definen la arquitectura universal del script de resguardo `backup.py`.  
> 2. **Base de conocimiento Windows:** Diagnóstico de cabecera para dependencias, enlaces simbólicos, codificación batch y preservación de entornos.

---

## 1. Problema de Entornos Virtuales de Python y Scripts Lanzadores (.bat)

### 1.1. Causa Raíz: La naturaleza de `venv` en Windows
Un entorno virtual de Python (`venv`) creado en Windows **no es una instalación autónoma de Python**.
- Solo contiene scripts de activación, copias de lanzadores mínimos y un archivo `pyvenv.cfg`.
- El archivo `pyvenv.cfg` contiene una ruta fija hacia el ejecutable base de Python instalado en el sistema operativo (por ejemplo: `C:\Users\<usuario>\AppData\Local\Python\pythoncore-3.12-64\python.exe` o `C:\Users\<usuario>\AppData\Local\Programs\Python\Python312\python.exe`).
- **Qué ocurre al desinstalar o reinstalar Python:** Si el usuario desinstala Python para limpiar espacio o reinstala una versión en otra ruta:
  1. El `venv` existente queda **huérfano/roto**.
  2. Al invocar cualquier comando de Python dentro del venv, se produce el error:
     ```text
     No Python at '"C:\Users\...\python.exe"'
     ```
  3. Si el usuario intenta borrar manualmente la carpeta `backend\venv` y la deja vacía o a medio borrar, el script lanzador falla en cascada.

---

### 1.2. El Fallo de Lógica Clásico en los Scripts `.bat`
Muchos proyectos utilizan un lanzador por lotes con una comprobación superficial como esta:

```bat
:: COMPROBACIÓN DEFECTUOSA / INSUFICIENTE:
if not exist "backend\venv" (
    echo Creando entorno virtual...
    python -m venv backend\venv
) else (
    echo Entorno virtual ya existe.
)
call backend\venv\Scripts\activate.bat
```

**Por qué falla:**
1. Si la carpeta `backend\venv` existe pero está vacía (porque se interrumpió un borrado), el script cree que el entorno ya existe.
2. Si el entorno existe pero apunta a un Python previo desinstalado, el script salta la creación e intenta llamar a `activate.bat` o a `backend\venv\Scripts\python.exe`.
3. Esto genera los errores:
   ```text
   El sistema no puede encontrar la ruta especificada.
   ERROR: Error al instalar las dependencias de Python.
   ```

---

### 1.3. La Trampa de Codificación en CMD de Windows (UTF-8 vs ANSI/ASCII)
Al crear scripts `.bat` que contienen caracteres especiales o acentuados (`á`, `é`, `í`, `ó`, `ú`, `¡`) guardados en UTF-8 sin BOM con saltos de línea LF (estilo Linux/Unix):
- El intérprete `cmd.exe` de Windows se desalinea en los saltos de byte dentro de bloques de paréntesis `(...)`.
- Esto provoca errores sintácticos absurdos como:
  ```text
  "enerando" no se reconoce como un comando interno o externo...
  "alizar" no se reconoce como un comando interno o externo...
  ```
- **Regla de oro para scripts `.bat` en Windows:** Utilizar caracteres **ASCII puro** (sin tildes ni caracteres especiales) y saltos de línea **CRLF (`\r\n`)**.

---

### 1.4. Solución Defensiva: Lanzador Auto-Reparable

En lugar de verificar si la carpeta existe, el script debe **verificar si el ejecutable de Python del venv realmente responde y funciona**:

```bat
:: VERIFICACIÓN ROBUSTA Y AUTO-REPARABLE:
echo [1/3] Configurando entorno virtual de Python...
set RECREAR_VENV=0
if not exist "backend\venv\Scripts\activate.bat" (
    set RECREAR_VENV=1
) else (
    backend\venv\Scripts\python -c "import sys" >nul 2>&1
    if errorlevel 1 set RECREAR_VENV=1
)

if "%RECREAR_VENV%"=="1" (
    echo Creando o reparando entorno virtual en backend\venv...
    if exist "backend\venv" rmdir /s /q "backend\venv" >nul 2>&1
    python -m venv backend\venv
    if errorlevel 1 (
        echo ERROR: No se pudo crear el entorno virtual. Asegurate de tener Python instalado y en el PATH.
        pause
        exit /b 1
    )
) else (
    echo Entorno virtual valido detectado.
)

call backend\venv\Scripts\activate.bat
```

---

### 1.5. Script Independiente de Diagnóstico y Reparación: `revisar_e_instalar_dependencias.bat`
Para desacoplar el arranque diario de las tareas de reparación e instalación pesada, es recomendable disponer de un script autónomo de diagnóstico que:
1. Compruebe si `python` está en el `PATH` del sistema.
2. Evalúe la salud del `venv` y lo regenere limpiamente si está dañado.
3. Actualice `pip` e instale `requirements.txt`.
4. Ejecute un test de importación de librerías críticas para dar confirmación visual al usuario.

---

### 1.6. Peligros de Actualización Masiva de Módulos de Python (`pip upgrade`)

En entornos híbridos que combinan inteligencia artificial local (Whisper / CTranslate2), aceleración por hardware (CUDA / cuDNN) y captura física de audio en Windows, **actualizar dependencias de forma masiva o indiscriminada (`pip install --upgrade ...`) provocará roturas críticas del sistema**.

Las versiones de `backend/requirements.txt` se encuentran deliberadamente ancladas con versiones exactas (`==`) por los siguientes motivos:

1. **`numpy==1.26.4` (Punto Crítico Inquebrantable):**
   - **Riesgo:** La rama NumPy 2.x introdujo cambios incompatibles en su C-API / ABI.
   - **Efecto:** Módulos precompilados de deep learning como `ctranslate2` y `faster-whisper` fallarán de inmediato al arrancar con el error:  
     `A module that was compiled using NumPy 1.x cannot be run in NumPy 2.x`.
   - **Regla:** Mantener estrictamente fijado `numpy==1.26.4`.

2. **Librerías CUDA (`nvidia-cublas-cu12`, `nvidia-cudnn-cu12`) y `faster-whisper`:**
   - **Riesgo:** El motor de transcripción local por GPU depende de la sincronización binaria exacta entre CTranslate2 y las bibliotecas dinámicas de NVIDIA (`.dll` en Windows).
   - **Efecto:** Una actualización desalineada provocará errores de DLL no encontrada (`cudnn_ops_infer64_8.dll not found`, `cublasLt64_12.dll not found`), anulando la aceleración por tarjeta gráfica o abortando el servidor.

3. **`pyaudio==0.2.14` y `pyaudiowpatch==0.2.12.8` (Captura WASAPI Loopback):**
   - **Riesgo:** Para grabar el audio interno del ordenador (altavoces/reuniones), Windows requiere binarios precompilados especiales (*wheels*) de PortAudio con parches para el bucle de retorno (*loopback*).
   - **Efecto:** Al actualizar a ciegas, pip no suele encontrar wheels precompilados para Windows e intenta compilar código C/C++, requiriendo Microsoft Visual C++ Build Tools. Si se reemplaza por `pyaudio` estándar, la grabación del sonido del sistema dejará de funcionar.

4. **`google-generativeai==0.7.0` (API de Gemini):**
   - **Riesgo:** Google reestructuró su SDK migrando hacia la nueva librería unificada `google-genai`. Actualizar `google-generativeai` puede acarrear deprecaciones de métodos, cambios de firma en parámetros o alteraciones en la serialización de respuestas.

> **Regla de Oro:** Si el entorno funciona, no actualizar paquetes masivamente. Cualquier actualización debe ser unitaria, aislada y validada con `revisar_e_instalar_dependencias.bat`.

---

### 1.7. "Botón de Pánico": Restaurador Total con 1 Clic (`restaurar_entorno.bat`)
Si por error o por un script externo se produce una actualización indeseada (`pip upgrade`) o el entorno virtual queda inconsistente:
1. **Detección e Instalación Automática de Python Base:**
   - Comprueba si existe Python en el sistema y valida si su versión es compatible (Python 3.11 o 3.12, imprescindibles para los módulos de IA y audio).
   - Si no se encuentra en el `PATH`, busca automáticamente en las rutas de instalación estándar (`%LOCALAPPDATA%\Programs\Python` y `%ProgramFiles%\Python`).
   - Si no existe ninguna versión válida o la instalada es incompatible (ej. Python 3.13+), **descarga automáticamente el instalador oficial de Python 3.12.10 (64-bit) desde python.org** y lo instala en modo silencioso.
   - **Inclusión en el PATH:** Configura el `PATH` para la sesión actual y lo inyecta de forma permanente y segura en el registro de Windows (`HKCU\Environment\Path`) mediante la API nativa `winreg` de Python, evitando truncamientos o fallos de longitud.
2. **Archivo de Congelado de Respaldo (`backend/requirements-lock.txt`):** Contiene el árbol completo y exacto de todas las dependencias y subdependencias actualmente verificadas y funcionando.
3. **Recreación Limpia de Entorno Virtual:** Elimina por completo la carpeta `backend\venv`, la recrea limpia desde cero usando el ejecutable de Python validado e instala automáticamente las versiones exactas de `backend/requirements-lock.txt`.
4. Esto garantiza que ante cualquier desastre, formateo o corrupción de librerías, el sistema vuelve al 100% de operatividad en 2 minutos de forma totalmente desatendida.

---

## 2. Problemas Detectados en Scripts de Respaldo (`backup.py`)

### 2.1. Lista de Archivos Rígida e Incompleta
En aplicaciones que evolucionan, el script `backup.py` suele quedarse desactualizado si mantiene una lista fija de archivos (`FILES_TO_BACKUP`). Entre las omisiones más comunes se encuentran:
1. **El propio script `backup.py`:** No incluirse en su propia copia de seguridad.
2. **Scripts auxiliares de backend:** Scripts como detectores de hardware (`check_gpu.py`), scripts de prueba (`test_cuda.py`, `test_gemini_api.py`) o scripts de migración de base de datos.
3. **Scripts de automatización del sistema:** Los archivos `.bat` de arranque y mantenimiento (`arrancar.bat`, `revisar_e_instalar_dependencias.bat`).
4. **Fijación de dependencias de frontend:** Omitir `package-lock.json`, impidiendo reproducir las versiones exactas de Electron y Node.js.
5. **Documentación viva:** Memorias técnicas, manuales de usuario actualizados y esquemas de diseño.

---

### 2.2. Incompatibilidad de `shutil.copy2` con Carpetas
El método estándar `shutil.copy2(src, dst)` está diseñado estrictamente para archivos:
- Si en `FILES_TO_BACKUP` se añade una ruta que resulta ser una carpeta (por ejemplo modelos de lenguaje locales, diccionarios o recursos estáticos como `backend/tessdata`), el script lanza una excepción (`PermissionError: [Errno 13] Permission denied` o `IsADirectoryError`) y detiene la copia de seguridad por completo.
- **Solución:** Comprobar si la ruta es archivo (`shutil.copy2`) o directorio (`shutil.copytree(..., dirs_exist_ok=True)`).

---

### 2.3. Ausencia de Métricas y Trazabilidad
Un buen script de respaldo debe proporcionar al usuario:
- Confirmación visual archivo por archivo con su tamaño en bytes.
- Omisión limpia (sin crashear) si algún archivo opcional no existe.
- Resumen final del número total de elementos y peso acumulado en MB.
- Ruta absoluta clara del directorio generado (`backups/backup_YYYYMMDD_HHMMSS`).

---

## 3. Plantillas de Código Listas para Inyección en Nuevos Proyectos

### 3.1. Plantilla `revisar_e_instalar_dependencias.bat`
*(Nota: Escrito estrictamente en ASCII puro y formato CRLF para máxima compatibilidad en Windows)*

```bat
@echo off
title Revisor e Instalador de Dependencias de Python
echo ======================================================
echo    Revisor e Instalador de Dependencias - Python
echo ======================================================
echo.

echo [1/4] Comprobando instalacion de Python en Windows...
where python >nul 2>&1
if errorlevel 1 (
    echo [ERROR] No se encontro Python en el sistema o no esta en el PATH.
    echo Asegurate de tener Python instalado con la opcion Add to PATH marcada.
    goto :fin_error
)

for /f "tokens=*" %%i in ('python --version 2^>^&1') do set PYTHON_SYS_VER=%%i
echo Python detectado en el sistema: %PYTHON_SYS_VER%
echo.

echo [2/4] Verificando estado del entorno virtual (backend\venv)...
set RECREAR_VENV=0

if not exist "backend\venv\Scripts\activate.bat" (
    set RECREAR_VENV=1
) else (
    backend\venv\Scripts\python.exe -c "import sys" >nul 2>&1
    if errorlevel 1 (
        set RECREAR_VENV=1
    )
)

if "%RECREAR_VENV%"=="1" (
    echo El entorno virtual no existe, esta danado o apunta a un Python previo.
    echo Recreando entorno virtual desde cero...
    if exist "backend\venv" (
        echo Eliminando carpeta backend\venv antigua...
        rmdir /s /q "backend\venv"
    )
    echo Generando nuevo entorno virtual...
    python -m venv backend\venv
    if errorlevel 1 (
        echo [ERROR] Fallo la creacion del entorno virtual.
        goto :fin_error
    )
    echo Entorno virtual creado correctamente.
) else (
    echo Entorno virtual valido y funcional.
)

echo.
echo [3/4] Instalando / Actualizando dependencias de backend\requirements.txt...
backend\venv\Scripts\python.exe -m pip install --upgrade pip

if not exist "backend\requirements.txt" (
    echo [ERROR] No se encontro backend\requirements.txt.
    goto :fin_error
)

echo Instalando dependencias (este paso puede tardar varios minutos)...
backend\venv\Scripts\python.exe -m pip install -r backend\requirements.txt
if errorlevel 1 (
    echo [ERROR] Fallo la instalacion de dependencias.
    goto :fin_error
)

echo.
echo [4/4] Comprobando modulos instalados...
backend\venv\Scripts\python.exe -c "import fastapi, uvicorn; print(' [OK] Servidor Web (FastAPI/Uvicorn)')"
backend\venv\Scripts\python.exe -c "import faster_whisper; print(' [OK] Transcripcion (Faster-Whisper)')"
backend\venv\Scripts\python.exe -c "import pyaudio; print(' [OK] Captura de Audio (PyAudio)')"

echo.
echo ======================================================
echo    Configuracion completada con exito!
echo ======================================================
echo Ya puedes iniciar la aplicacion ejecutando arrancar.bat.
echo.
pause
exit /b 0

:fin_error
echo.
echo ======================================================
echo    ERROR: La configuracion no se pudo completar.
echo ======================================================
echo.
pause
exit /b 1
```

---

### 3.2. Plantilla `backup.py` Robusta y Extensible

Copia este script en la raíz de cualquier proyecto para disponer de un sistema de copias de seguridad instantáneas, versionadas por fecha y hora, y completamente trazables (adaptando `FILES_TO_BACKUP` a la estructura del proyecto):

```python
import os
import shutil
import datetime

# Directorio base y de copias de seguridad
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BACKUPS_DIR = os.path.join(BASE_DIR, "backups")

# Lista exhaustiva y categorizada de elementos a respaldar
FILES_TO_BACKUP = [
    # Configuración raíz y control de versiones
    ".gitignore",
    "config.json",
    "LICENSE",
    "README.md",
    
    # Frontend y recursos de interfaz
    "frontend",
    
    # Backend / Motor nativo (según arquitectura: backend/ o src-tauri/)
    "backend",
    "src-tauri",
    
    # Lanzadores y mantenimiento
    "arrancar.bat",
    "compilar_y_empaquetar.bat",
    "backup.py",
    
    # Documentación técnica, guías y especificaciones
    "DOCUMENTACION.md",
    "PLAN_DE_TRABAJO.md",
    "GUIA_COMPILACION_NATIVA_TAURI_RUST.md",
    "GUIA_CONTEXTO_PROBLEMAS_ENTORNO_Y_BACKUP.md",
    "Guia_Inicio_Nuevos_Proyectos.md"
]

def make_backup():
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = os.path.join(BACKUPS_DIR, f"backup_{timestamp}")
    
    print(f"Iniciando copia de seguridad en:\n  {backup_path}\n")
    os.makedirs(backup_path, exist_ok=True)
    
    copied_count = 0
    total_bytes = 0

    for rel_path in FILES_TO_BACKUP:
        src = os.path.join(BASE_DIR, rel_path)
        dst = os.path.join(backup_path, rel_path)
        
        if os.path.exists(src):
            if os.path.isdir(src):
                shutil.copytree(src, dst, dirs_exist_ok=True)
                print(f"  [OK] (Carpeta) Copiado: {rel_path}")
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
```

---

## 4. Checklist Rápido para Nuevos Hilos / Proyectos

Al iniciar o depurar un proyecto similar en otro hilo de chat o asistente de IA, verificar lo siguiente:

- [ ] **Comprobar si el venv es funcional, no solo si la carpeta existe:** Nunca confiar en `if not exist "venv"`.
- [ ] **Eliminar carpetas venv corruptas antes de recrear:** Si `python.exe -c "import sys"` falla, hacer `rmdir /s /q venv` antes de invocar `python -m venv venv`.
- [ ] **Scripts .bat siempre en ASCII puro:** Evitar caracteres acentuados dentro de scripts batch de Windows para prevenir fallos en el parser de CMD.
- [ ] **`backup.py` debe copiarse a sí mismo:** Asegurar que `backup.py` esté en su propia lista de copia.
- [ ] **Manejar tanto archivos como carpetas en scripts de copia:** Usar `os.path.isdir()` con `shutil.copytree(..., dirs_exist_ok=True)` junto a `shutil.copy2()`.
- [ ] **Respaldar archivos de bloqueo (`package-lock.json` / `poetry.lock` / `Pipfile.lock`):** Evitan sorpresas de versiones rotas en el futuro.
