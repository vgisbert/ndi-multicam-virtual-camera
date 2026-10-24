# Guía de Requerimientos y Buenas Prácticas para Nuevos Proyectos

Esta documentación establece las normas fundamentales que deben aplicarse al iniciar cualquier nuevo proyecto de software dentro del espacio de trabajo de Antigravity. El objetivo es garantizar la mantenibilidad, estabilidad y portabilidad de todas las aplicaciones.

## 1. Aislamiento y Entornos Virtuales

Cada proyecto de Python **debe estar completamente aislado** del sistema operativo y de otros proyectos.

*   **Uso estricto de `venv`:** Todo proyecto debe contar con su propio entorno virtual. Nunca instales dependencias del proyecto de forma global en Windows.
*   **Archivos ignorados:** La carpeta `venv` (y otras cachés como `__pycache__`) nunca deben versionarse, copiarse entre ordenadores ni incluirse en copias de seguridad de código fuente limpio (pesan mucho y están atadas a la máquina que las creó).

## 2. Control Inflexible de Dependencias

Para evitar el problema clásico de "ayer funcionaba y hoy, tras una actualización, se ha roto", las dependencias deben estar completamente selladas.

*   **Fijar versiones siempre (Pinning):** El archivo `requirements.txt` **no** debe contener nombres de librerías sueltas (ej. `fastapi`). Debe incluir las versiones exactas comprobadas usando el operador `==` (ej. `fastapi==0.136.1`).
*   **Procedimiento de sellado:** Una vez que un proyecto esté desarrollado y funcionando correctamente, activa su entorno virtual y ejecuta:
    ```bash
    pip freeze > requirements.txt
    ```
    Esto capturará la versión exacta de tu librería principal y de todas sus sub-dependencias.

## 3. Scripts de Arranque Inteligentes (Archivos .bat)

Todo proyecto debe ser "Auto-Configurable". La persona (o el propio desarrollador en el futuro) no debería tener que abrir una terminal y ejecutar comandos manuales para que el proyecto arranque por primera vez.

*   **Crear un `start.bat` o `arrancar.bat`:** El archivo de arranque debe hacer el trabajo pesado.
*   **Flujo obligatorio del script de arranque:**
    1.  Verificar si la carpeta `venv` existe.
    2.  Si no existe, crear el entorno virtual automáticamente (`python -m venv venv`).
    3.  Activar el entorno virtual (`call venv\Scripts\activate.bat`).
    4.  Instalar o validar las dependencias (`venv\Scripts\python.exe -m pip install -r requirements.txt`).
    5.  Arrancar la aplicación (ej. `python main.py` o `uvicorn...`).

*Este flujo garantiza que, si algo se corrompe, la solución para el usuario sea tan sencilla como borrar la carpeta `venv` y hacer doble clic en el `.bat` para regenerar la aplicación como si fuera nueva.*

## 4. Estructura de Directorios Estandarizada

Para mantener el orden cuando los proyectos crezcan y abarquen múltiples tecnologías, en el espacio de trabajo de Antigravity se establecen dos modelos arquitectónicos estandarizados:

### Modelo A: Herramientas y Servicios Basados en Python (IA / Procesamiento)
```text
/Nombre_Del_Proyecto
│
├── /backend                 # Todo el código Python, IA y lógica de servidor
│   ├── /venv                # Entorno virtual (generado automáticamente, no copiar)
│   ├── requirements.txt     # Dependencias fijadas con ==
│   └── main.py              # Punto de entrada
│
├── /frontend                # Código de la interfaz web (Vite, React, HTML/JS)
│   ├── /node_modules        # Dependencias de JS (generado automáticamente)
│   └── package.json         # Dependencias de frontend
│
├── arrancar.bat             # Script de arranque inteligente raíz
└── DOCUMENTACION.md         # Documentación específica de qué hace este proyecto
```

### Modelo B: Aplicaciones Nativas de Alto Rendimiento (Tauri v2 + Rust)
*Arquitectura recomendada para aplicaciones de escritorio ultraligeras, reactivas y sin dependencias de runtime:*
```text
/Nombre_Del_Proyecto
│
├── /src-tauri               # Núcleo de alto rendimiento en Rust (sin dependencias pesadas)
│   ├── Cargo.toml           # Dependencias y optimización Release (LTO, opt-level="z", strip)
│   ├── tauri.conf.json      # Ventanas, propiedades y permisos nativos
│   └── src/                 # Lógica de bajo nivel, comandos IPC, sockets UDP/TCP
│
├── /frontend                # Interfaz de usuario táctica (HTML5, Tailwind/CSS, JS reactivo)
│   ├── index.html           # Vista principal
│   └── app.js               # Conector IPC con Rust
│
├── arrancar.bat             # Script de desarrollo con recarga inmediata
├── compilar_y_empaquetar.bat# Compilación release portable a 'dist_portable' (~3 MB)
├── backup.py                # Copia de seguridad integral y trazable
└── DOCUMENTACION.md         # Memoria técnica del sistema
```

## 5. Protocolo de Resolución de Problemas Comunes

*   **Problema:** Al arrancar el `.bat` aparece `El sistema no puede encontrar la ruta especificada` en referencia a Python.
    *   *Causa:* La versión base de Python instalada en Windows se actualizó o borró, dejando huérfano al `venv`.
    *   *Solución:* Eliminar manualmente la carpeta `venv` y ejecutar de nuevo el `.bat`.
*   **Problema:** Error de incompatibilidad de librerías al intentar añadir una función nueva.
    *   *Solución:* Comprobar que estás instalando el nuevo paquete con el entorno virtual activado. Si funciona, no olvides volver a hacer `pip freeze > requirements.txt` para proteger la nueva librería.

## 6. Interfaces Gráficas (GUI) de Escritorio

*   **Para scripts y utilidades locales simples en Python:** Se debe utilizar siempre **`customtkinter`** (tomando como referencia el diseño del proyecto `Compresión MP3`), con tema oscuro y estética moderna. Se debe evitar `tkinter` estándar.
*   **Para aplicaciones de alto rendimiento, baja latencia o distribución portable sin dependencias:** La arquitectura recomendada y prioritaria es **Tauri v2 + Rust** (consultar `GUIA_COMPILACION_NATIVA_TAURI_RUST.md`). Ofrece ejecutables de ~3 MB, consumo mínimo de RAM y cero dependencias de runtimes externos en la máquina del usuario.

## 7. Manejo de APIs Externas y Refresco de UI

Para asegurar la robustez de las aplicaciones frente a problemas externos (red, caídas de servidores de terceros) y mantener una experiencia de usuario fluida:

*   **Caché Local de Datos de API:** Cuando una aplicación dependa de listas de opciones que raramente cambian pero que provienen de APIs externas (ej. lista de voces de Edge TTS), **siempre** se debe crear un archivo de caché local (ej. `voices.json`). El backend debe intentar leer de este archivo primero o usarlo como _fallback_ en caso de que la petición de red falle. Esto evita que el frontend se rompa si el proveedor cambia su API o bloquea la red.
*   **Control de Foco y Scroll (React):** Cuando se abran o cierren ventanas modales o paneles laterales que redimensionen los editores de texto (`textarea`), se debe implementar lógica con `useEffect` para forzar al navegador a mantener la posición del cursor a la vista (por ejemplo, reasignando el `selectionRange` y el `focus()`). Esto evita que los saltos de diseño (reflow) oculten la línea en la que el usuario estaba trabajando.

## 8. Gestión de Artefactos de Salida y Regla Anti-Duplicados en Git

En proyectos que generan ejecutables, paquetes portables o instaladores para distribución final, se debe aplicar una separación estricta entre el **código fuente original** y los **productos derivados de compilación**:

*   **Principio de Fuente Única de la Verdad:**  
    Cualquier recurso auxiliar (drivers, bibliotecas `.dll`, plantillas de configuración o scripts de instalación) debe residir en un único directorio maestro del código fuente (ej. `/driver`). Nunca dupliques manualmente estos archivos en otras ramas del proyecto.
*   **Aislar Paquetes y Distribuciones en `.gitignore`:**  
    Cuando un script de empaquetado (como `compilar_y_empaquetar.bat` o `build_exe.py`) copie recursos originales hacia carpetas de salida preparadas para llevar en pendrive o distribuir (ej. `dist_portable/driver/`, `dist/`, `build/`), dichas carpetas de salida deben estar **expresamente ignoradas en `.gitignore`**.  
    Esto evita inflar el historial de Git con binarios idénticos, evita conflictos de sincronización y previene el error crítico de editar por accidente la copia generada en vez del archivo fuente original.
*   **Procedimiento para Desindexar Duplicados en Git:**  
    Si un producto derivado o carpeta de salida ya fue rastreado por Git en commits anteriores, debe retirarse del seguimiento del repositorio sin destruir el archivo local:
    ```bash
    git rm -r --cached ruta/a/carpeta_duplicada/
    ```
    Añade la ruta correspondiente a `.gitignore` y realiza el *commit* de limpieza.

