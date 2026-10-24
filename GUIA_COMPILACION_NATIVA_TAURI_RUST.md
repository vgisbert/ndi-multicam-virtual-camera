# Guía Maestra: Sistema de Compilación Nativo Portable con Tauri v2 y Rust

> **Propósito:** Esta guía proporciona una plantilla universal, paso a paso y comprobada para empaquetar aplicaciones de escritorio nativas en **Windows 10 y 11** utilizando **Tauri v2 + Rust**, logrando ejecutables ultraligeros (**~3 MB**), arranque instantáneo, consumo mínimo de RAM (<25 MB) y **cero dependencia de Python o Node.js** en el equipo de destino.

---

## 1. Por qué este Sistema supera a PyInstaller / Python

| Factor | Empaquetado Tradicional (PyInstaller) | **Sistema Nativo (Tauri v2 + Rust)** |
| :--- | :--- | :--- |
| **Tamaño en disco** | 80 – 150 MB (con carpetas `_internal`) | **~3 a 4 MB (un solo archivo `.exe`)** |
| **Tiempo de arranque** | 2 a 4 segundos (descompresión en `%TEMP%`) | **Instantáneo (0.05 s)** |
| **Consumo de memoria** | 150 – 250 MB RAM | **15 – 30 MB RAM** |
| **Icono en barra de tareas**| Propenso a mostrar el icono de Python o fallar | **100 % nativo embebido en el ejecutable PE** |
| **Falsos positivos AV** | Muy frecuentes por empaquetado de scripts | **Prácticamente nulos (código binario estándar)** |

---

## 2. Requisitos Previos en el Entorno de Desarrollo

Para compilar en cualquier equipo de desarrollo se requieren únicamente dos herramientas:

1. **Rust y Cargo (x86_64-pc-windows-gnu o msvc):**
   - Instalable desde [rustup.rs](https://rustup.rs).
   - Comando de verificación: `cargo --version`
2. **Compilador C / MinGW-w64 (si se usa la toolchain GNU):**
   - Se puede instalar en Windows con WinGet:
     ```cmd
     winget install BrechtSanders.WinLibs.POSIX.UCRT
     ```
   - O utilizar la toolchain oficial de Microsoft C++ Build Tools (`msvc`).

---

## 3. Estructura de Directorios Estándar

Cualquier proyecto que utilice este sistema debe estructurarse de la siguiente manera:

```text
MiProyecto/
├── arrancar.bat                   <-- Script de desarrollo y recarga en 1 clic
├── compilar_y_empaquetar.bat      <-- Script de compilación release portable automática
├── backup.py                      <-- Script de copia de seguridad integral
├── dist_portable/                 <-- Carpeta final lista para distribuir / pendrive
│   ├── MiApp.exe                  <-- Ejecutable nativo final (~3 MB)
│   ├── WebView2Loader.dll         <-- Conector oficial de Microsoft Edge WebView2
│   ├── config.json                <-- Ajustes del usuario (opcional)
│   └── LEEME_WINDOWS_10.txt       <-- Instrucciones de uso para el usuario final
├── frontend/                      <-- Interfaz de usuario (HTML5, Tailwind, JS)
│   ├── index.html                 <-- Vista principal
│   ├── app.js                     <-- Lógica e interactividad del cliente
│   └── i18n.js                    <-- Internacionalización (opcional)
└── src-tauri/                     <-- Motor backend en Rust
    ├── build.rs                   <-- Script de enlace de recursos Windows (con parche anti-tildes)
    ├── Cargo.toml                 <-- Configuración de dependencias y optimización LTO
    ├── tauri.conf.json            <-- Propiedades de ventanas, títulos e identificadores
    ├── icons/                     <-- Iconos (icon.ico, 32x32.png, 128x128.png)
    └── src/
        ├── main.rs                <-- Punto de entrada de Windows (sin consola negra)
        ├── lib.rs                 <-- Registro de comandos y ciclo de vida de Tauri
        ├── commands.rs            <-- Funciones que el frontend invoca por IPC
        └── models.rs              <-- Estructuras de datos compartidas (JSON)
```

---

## 4. Archivos Clave y Plantillas de Configuración

### 4.1. `src-tauri/Cargo.toml` (Optimizado para Tamaño Mínimo)

Este archivo activa la optimización LTO (*Link-Time Optimization*), strip de símbolos de depuración y abort en pánico para reducir el ejecutable al mínimo tamaño posible:

```toml
[package]
name = "mi-app"
version = "1.0.0"
description = "Aplicación Nativa de Alto Rendimiento"
edition = "2021"

[lib]
name = "mi_app_lib"
crate-type = ["staticlib", "rlib"]

[build-dependencies]
tauri-build = { version = "2.0", features = [] }

[dependencies]
tauri = { version = "2.0", features = ["tray-icon", "custom-protocol"] }
tauri-plugin-opener = "2.0"
serde = { version = "1.0", features = ["derive"] }
serde_json = "1.0"
tokio = { version = "1", features = ["full"] }

[profile.release]
panic = "abort"      # Elimina el árbol de desenrollado de excepciones (-1.5 MB)
codegen-units = 1    # Permite optimización de código cruzada entre módulos
lto = true           # Link-Time Optimization global (-2 MB)
opt-level = "z"      # Optimiza agresivamente por tamaño de binario
strip = true         # Elimina metadatos y símbolos debug (-4 MB)
```

---

### 4.2. `src-tauri/tauri.conf.json`

Define la ventana principal, dimensiones y la ruta relativa a la carpeta `frontend`:

```json
{
  "$schema": "https://raw.githubusercontent.com/tauri-apps/tauri/dev/crates/tauri-cli/schema.json",
  "productName": "MiApp",
  "version": "1.0.0",
  "identifier": "com.antigravity.miapp",
  "build": {
    "frontendDist": "../frontend"
  },
  "app": {
    "withGlobalTauri": true,
    "windows": [
      {
        "title": "Mi Aplicación Nativa",
        "url": "index.html",
        "width": 1050,
        "height": 720,
        "minWidth": 800,
        "minHeight": 600,
        "resizable": true,
        "decorations": true,
        "transparent": false,
        "alwaysOnTop": false,
        "center": true,
        "label": "main"
      }
    ],
    "security": {
      "csp": null
    }
  },
  "bundle": {
    "active": false
  }
}
```

---

### 4.3. `src-tauri/build.rs` (Solución Crítica al Bug de Tildes en Windows)

> [!WARNING]
> **Bug Conocido de Windows / MinGW:** Si la ruta del proyecto contiene tildes o caracteres especiales (por ejemplo: `Cámera`, `música`, `año`, `diseño`), el compilador de recursos GNU `windres.exe` fallará con el error `Invalid argument` al intentar abrir el icono.

En compilaciones limpias estándar basta con:
```rust
fn main() {
    tauri_build::build()
}
```

Si el proyecto se encuentra alojado en carpetas con caracteres no-ASCII o tildes, `build.rs` puede copiar el icono a una ruta temporal garantizada en ASCII antes de invocar a `tauri_build`:

```rust
fn main() {
    let mut windows = tauri_build::WindowsAttributes::new();
    
    // Copiar el icono a una ruta temporal libre de tildes para evitar errores de windres
    let temp_ico = std::path::PathBuf::from(r"C:\Users\super\.cargo\app_icon_temp.ico");
    if std::path::Path::new("icons/icon.ico").exists() {
        let _ = std::fs::copy("icons/icon.ico", &temp_ico);
        windows = windows.window_icon_path(&temp_ico);
    }

    let attrs = tauri_build::Attributes::new().windows_attributes(windows);
    tauri_build::try_build(attrs).expect("Fallo al ejecutar tauri-build");
}
```

---

### 4.4. `src-tauri/src/main.rs` (Ocultar Consola Negra de Windows)

La directiva `#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]` indica al enlazador de Windows que genere un binario con subsistema GUI, impidiendo que aparezca la ventana negra de consola al hacer doble clic:

```rust
// Impide la consola negra en modo Release
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

fn main() {
    mi_app_lib::run();
}
```

---

### 4.5. Comunicación Frontend <-> Rust (`frontend/app.js`)

En el frontend no es necesario utilizar frameworks pesados ni empaquetadores complejos si no se desean. Se puede usar JavaScript estándar con la API nativa de Tauri:

```javascript
// Llamar a una función de Rust por memoria IPC directa
async function obtenerEstado() {
  if (window.__TAURI__ && window.__TAURI__.core) {
    try {
      // 'get_status' es el comando registrado en Rust con #[tauri::command]
      const data = await window.__TAURI__.core.invoke('get_status');
      console.log("Datos recibidos de Rust:", data);
      actualizarInterfaz(data);
    } catch (err) {
      console.error("Error al invocar Rust:", err);
    }
  } else {
    // Modo de prueba o mock para desarrollo en navegador
    console.warn("Entorno Web puro: usando Mock");
    actualizarInterfaz({ nominal: true, items: [] });
  }
}
```

Y en Rust (`src-tauri/src/commands.rs`):

```rust
#[tauri::command]
pub fn get_status() -> Result<MiEstado, String> {
    Ok(MiEstado {
        nominal: true,
        items: vec!["item1".into(), "item2".into()],
    })
}
```

---

## 5. El Script Universal de Compilación: `compilar_y_empaquetar.bat`

Copia este script en la raíz de cualquier proyecto. Se encarga de:
1. Localizar y priorizar las herramientas del sistema (Cargo, MinGW/WinLibs).
2. Mapear una unidad virtual (`M:`) para aislar el compilador de espacios y caracteres especiales en las rutas.
3. Compilar en modo Release con optimizaciones LTO agresivas.
4. Generar la carpeta portable `dist_portable` con el binario (`MiApp.exe`), librerías auxiliares (`WebView2Loader.dll`) y empaquetar un archivo `.zip` listo para pendrive.

```bat
@echo off
title Compilador Nativo Tauri v2 Portable (Sin Dependencias)
echo ======================================================
echo    Compilando Release Nativo para Windows 10 / 11
echo ======================================================
echo.

:: 1. Localizar herramientas en el sistema
set "CARGO_PATH=%USERPROFILE%\.cargo\bin"
set "WINGET_MINGW=%LOCALAPPDATA%\Microsoft\WinGet\Packages\BrechtSanders.WinLibs.POSIX.UCRT_Microsoft.Winget.Source_8wekyb3d8bbwe\mingw64\bin"

if exist "%WINGET_MINGW%" (
    set "PATH=%WINGET_MINGW%;%PATH%"
)
if exist "%CARGO_PATH%" (
    set "PATH=%CARGO_PATH%;%PATH%"
)

where cargo >nul 2>&1
if errorlevel 1 (
    echo [ERROR] No se encontro Cargo/Rust en el sistema.
    pause
    exit /b 1
)

:: 2. Directorio de compilación fuera de rutas con caracteres no-ASCII
set "CARGO_TARGET_DIR=C:\Users\super\.cargo\target_build_temp"

:: 3. Mapear unidad virtual temporal M: (Inmunidad contra espacios y tildes)
subst M: /d >nul 2>&1
subst M: "%~dp0." >nul 2>&1

cd /d "M:\src-tauri"
echo [1/3] Compilando binario optimizado con Cargo (Release)...
set RUSTFLAGS=-A linker-messages
cargo build --release

if errorlevel 1 (
    echo [ERROR] Fallo la compilacion de Rust.
    cd /d "%~dp0"
    subst M: /d >nul 2>&1
    pause
    exit /b 1
)

cd /d "%~dp0"
subst M: /d >nul 2>&1

echo.
echo [2/3] Creando carpeta de distribucion portable 'dist_portable'...
if not exist "dist_portable" mkdir "dist_portable"

:: 4. Copiar archivos necesarios
copy /Y "C:\Users\super\.cargo\target_build_temp\release\mi-app.exe" "dist_portable\MiApp.exe" >nul
copy /Y "C:\Users\super\.cargo\target_build_temp\release\WebView2Loader.dll" "dist_portable\WebView2Loader.dll" >nul 2>&1
if exist "config.json" copy /Y "config.json" "dist_portable\config.json" >nul

:: 5. Generar archivo de instrucciones para el usuario final
(
echo =============================================================================
echo                       INSTRUCCIONES DE USO PORTABLE
echo =============================================================================
echo.
echo Para ejecutar en cualquier ordenador Windows 10 o Windows 11:
echo   1. Copia esta carpeta en el ordenador destino (o ejecutala desde un pendrive).
echo   2. Haz doble clic en "MiApp.exe".
echo.
echo NOTA: No requiere instalar Python, Node.js ni configurar variables de entorno.
echo =============================================================================
) > "dist_portable\LEEME_WINDOWS_10.txt"

echo.
echo [3/3] Comprimiendo paquete ZIP para distribucion...
powershell -NoProfile -Command "Compress-Archive -Path 'dist_portable\*' -DestinationPath 'dist_portable\Mi_App_Portable.zip' -Force" >nul 2>&1

echo.
echo ======================================================
echo  [LISTO] Paquete portable generado con exito:
echo         %~dp0dist_portable\
echo.
echo  Archivo ZIP listo para compartir:
echo         %~dp0dist_portable\Mi_App_Portable.zip
echo ======================================================
echo.
pause
```

---

## 6. Lista de Verificación (Checklist) para Nuevos Proyectos

Al iniciar un nuevo proyecto con este sistema, sigue estos pasos:

- [ ] **1.** Crea la carpeta `frontend/` y coloca allí tu `index.html`, `app.js` y hojas de estilo.
- [ ] **2.** Crea la carpeta `src-tauri/` con `Cargo.toml`, `build.rs` y `tauri.conf.json`.
- [ ] **3.** Coloca los iconos en `src-tauri/icons/` (`icon.ico`, `icon.png`, `32x32.png`, `128x128.png`).
- [ ] **4.** En `frontend/app.js`, utiliza `window.__TAURI__.core.invoke('nombre_comando')` para solicitar datos al backend.
- [ ] **5.** En `src-tauri/src/commands.rs`, implementa los comandos con la anotación `#[tauri::command]`.
- [ ] **6.** Ejecuta `compilar_y_empaquetar.bat`: el proceso generará automáticamente en segundos la carpeta `dist_portable` y el archivo `.zip` de ~3-5 MB listo para llevar en pendrive.
