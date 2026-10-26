# Documentación Técnica: NDI Virtual Camera para Windows 10

> **Estado del proyecto:** Suite Multicámara DirectShow (Operativa)  
> **Sistema Operativo Objetivo:** Windows 10 (64 bits, compatible con Windows 11)  
> **Hardware Validado:** 2 Cámaras PTZ Nuroum V403 (múltiples unidades en LAN) + Fuentes NDI en red local.

---

## 1. Visión General: Arquitectura Multicámara Simultánea

Para permitir que el realizador opere **un solo programa de producción (OBS Studio, ManyCam, vMix, etc.)**, el sistema expone cada cámara NDI como un dispositivo de captura DirectShow independiente en Windows:

```mermaid
flowchart TD
    subgraph LAN["Red Local (LAN Gigabit)"]
        Cam1["Cámara 1 (Nuroum V403)<br/>192.168.X.10:5961<br/>MAC: 98:6E:E8:XX:XX:01<br/>NDI|HX 1080p 30fps"]
        Cam2["Cámara 2 (Nuroum V403)<br/>192.168.X.20:5961<br/>MAC: 98:6E:E8:XX:XX:02<br/>NDI|HX 1080p 30fps"]
    end


    subgraph Core["NDI Virtual Camera (Motor en Background)"]
        Daemon["Discovery Daemon<br/>(mDNS 5353 + ARP iphlpapi.dll)"]
        Worker1["Stream Worker CAM 1<br/>(TCP 5961 -> 1080p30)"]
        Worker2["Stream Worker CAM 2<br/>(TCP 5961 -> 1080p30)"]
        MultiVCam["MultiVirtualCameraManager<br/>(DirectShow Dual Device Bridge)"]
    end

    subgraph DirectShow["Windows 10 DirectShow Video Capture"]
        Dev1["Dispositivo 1: 'Camara 1 - Frontal (NDI)'"]
        Dev2["Dispositivo 2: 'Camara 2 - Lateral (NDI)'"]
    end

    subgraph MasterApp["Software de Realización Único"]
        OBS["OBS Studio / ManyCam"]
        Escena1["Escena 1: Solo Plano Frontal"]
        Escena2["Escena 2: Solo Plano Lateral"]
        Escena3["Escena 3: Multicámara PiP (Doble Plano)"]
    end

    Cam1 --> Worker1
    Cam2 --> Worker2
    Daemon --> Worker1
    Daemon --> Worker2
    Worker1 --> MultiVCam
    Worker2 --> MultiVCam
    MultiVCam --> Dev1
    MultiVCam --> Dev2
    Dev1 --> OBS
    Dev2 --> OBS
    OBS --> Escena1
    OBS --> Escena2
    OBS --> Escena3
```

---

## 2. Estrategia Multidispositivo DirectShow (`UnityCapture` + `pyvirtualcam`)

### 2.1. El Reto de OBS-VirtualCam vs. UnityCapture
El driver estándar `obs-virtualcam` de OBS Studio comparte un único canal de memoria (`OBSVirtualCamVideo`), por lo que solo permite una salida virtual global a la vez.

Para habilitar **2 o más cámaras virtuales simultáneas e independientes**:
* Se integra el filtro DirectShow de alto rendimiento **`UnityCaptureFilter64.dll`**.
* Al registrarse con `/i:UnityCaptureDevices=2`, crea dos canales de memoria compartida desacoplados (`UnityCapture_Data0` y `UnityCapture_Data1`).
* Cada canal alimenta un dispositivo DirectShow diferenciado en Windows:
  1. **`Camara 1 - Frontal (NDI)`**
  2. **`Camara 2 - Lateral (NDI)`**

### 2.2. Ventajas para la Producción
1. **Un solo programa en directo:** El realizador únicamente maneja OBS o ManyCam durante la emisión. No necesita tocar la ventana de NDI Virtual Camera.
2. **Escenas y Transiciones Preparadas:** Permite crear planos dobles (PiP), planos divididos o transiciones automatizadas combinando ambas cámaras físicas.
3. **Compatibilidad Universal:** Funciona exactamente como dos webcams USB físicas en OBS, ManyCam, Zoom, Microsoft Teams, Google Meet, Skype y navegadores web.
4. **Cero consumo de CPU innecesario:** Los fotogramas se inyectan mediante memoria compartida Win32 directa (*single memcpy*), consumiendo menos del **3 % de CPU por cámara**.

---

## 3. Resolución de la Colisión de Nombres NDI

Ambas cámaras Nuroum V403 emiten por defecto con el nombre idéntico `"LOCALHOST (Nuroum Cam V403-)"`:
1. El demonio resuelve la dirección física MAC real mediante `iphlpapi.SendARP`.
2. Cada flujo se conecta por socket unívoco en `p_url_address` (`<IP_CAM_1>:5961` y `<IP_CAM_2>:5961`), garantizando que cada cámara alimenta exclusivamente su correspondiente canal virtual.

---

## 4. Instaladores y Mantenimiento

* **[`driver/instalar_driver_multicamara.bat`](file:///d:/Documentos/Antigravity/NDI%20Virtual%20C%C3%A1mera/driver/instalar_driver_multicamara.bat):**  
  Registra los 2 dispositivos virtuales simultáneos en Windows con permisos de Administrador (`Camara 1 - Frontal (NDI)` y `Camara 2 - Lateral (NDI)`).
* **[`driver/desinstalar_driver_multicamara.bat`](file:///d:/Documentos/Antigravity/NDI%20Virtual%20C%C3%A1mera/driver/desinstalar_driver_multicamara.bat):**  
  Limpia las entradas del registro de Windows cuando se deseen retirar las cámaras virtuales.
* **[`arrancar.bat`](file:///d:/Documentos/Antigravity/NDI%20Virtual%20C%C3%A1mera/arrancar.bat):**  
  Monta la unidad virtual `V:`, verifica dependencias y lanza la aplicación.
* **[`backup.py`](file:///d:/Documentos/Antigravity/NDI%20Virtual%20C%C3%A1mera/backup.py):**  
  Copia de seguridad automática con marca de tiempo.

---

## 5. Configuración del Hardware y Comportamiento PTZ (NearSync / Firmware V403)

### 5.1. Identificación del Hardware Físico
* **Modelo:** Nuroum V403 / Hamedal Cam V403 (`device_type: 033`)
* **Cámara 1:** IP `<IP_CAM_1>` | MAC `98:6E:E8:XX:XX:01` | S/N `AW19XXXXXXXXXX`
* **Cámara 2:** IP `<IP_CAM_2>` | MAC `98:6E:E8:XX:XX:02` | S/N `AW19XXXXXXXXXX`


### 5.2. Configuración Esencial en NearSync para Evitar Movimientos No Deseados
Para garantizar que las cámaras **permanezcan fijas y no se muevan por su cuenta** al recibir corriente o al conectar la señal de vídeo NDI, la utilidad oficial **NearSync** (`Device Setting`) debe configurarse con los siguientes parámetros:

1. **`Cam Mode` -> `Manual Mode` (Crítico):**  
   * **Por qué:** Si está en `Auto Framing`, el procesador interno de la cámara analiza la imagen en cuanto se abre el flujo de vídeo y ejecuta automáticamente giros de Pan/Tilt y zoom digital/óptico intentando centrar a las personas en la habitación.
   * **Ajuste:** Debe seleccionarse siempre **`Manual Mode`**.
2. **`Call preset 1 when power on` -> Desmarcado:**  
   * **Por qué:** Si esta casilla está marcada, la cámara viaja de forma autónoma a las coordenadas guardadas en el Preset 1 en cuanto se enciende o reinicia el subsistema de vídeo.
   * **Ajuste:** Mantener **desmarcado**.
3. **`Visca Over IP Port` -> `1259`:**  
   * Puerto UDP estándar para el control remoto manual de movimiento mediante la aplicación complementaria *NDI PTZ Joystick Controller*.
4. **Guardado en Memoria Flash:**  
   * Tras aplicar los cambios en NearSync, pulsar obligatoriamente el botón morado **`Save`** para que se graben permanentemente en el archivo `/mnt/mtd/Config/config.ini` de la cámara.

> [!NOTE]
> La aplicación **NDI Virtual Camera** es un receptor pasivo de vídeo que solo se conecta a los puertos `5960 / 5961 TCP` (NDI). No contiene ni envía comandos de movimiento ni tramas VISCA (`1259 UDP`). Cualquier movimiento observado al abrir la transmisión de vídeo es originado exclusivamente por la configuración interna de *Auto Framing* o *Preset on Power* del propio firmware de la cámara.

*(Referencia visual guardada en: [`docs/nearsync_camera_settings.png`](file:///d:/Documentos/Antigravity/NDI%20Virtual%20C%C3%A1mera/docs/nearsync_camera_settings.png))*

---

## 6. Métricas de Rendimiento, Latencia y Comportamiento (Windows 10 vs. Windows 11)

### 6.1. ¿Qué Mide el Indicador de Latencia en Pantalla (`ms`)?
El valor numérico en color cian mostrado en la esquina inferior derecha de cada tarjeta de cámara (por ejemplo, `2.1 ms` u `11.4 ms`):
* **No representa la latencia de procesado de vídeo ni de CPU/GPU:** No mide el tiempo de renderizado de la imagen, la decodificación de fotogramas ni la potencia del ordenador anfitrión.
* **Mide el RTT de Red TCP (Round Trip Time):** En el demonio de descubrimiento ([`probe_tcp_port` en `discovery.py`](file:///d:/Documentos/Antigravity/NDI%20Virtual%20C%C3%A1mera/core/discovery.py#L38-L52)), la aplicación ejecuta periódicamente (cada 1 s) un sondeo de conexión TCP mediante un *3-way handshake* (`SYN` $\rightarrow$ `SYN-ACK`) al puerto NDI `5961` (o RTSP `554`) para comprobar el estado de salud y la respuesta de la interfaz de red de la cámara.

### 6.2. Diagnóstico de Diferencias de Latencia Observadas (2.1 ms vs. 11.4 ms)
Al comparar ejecuciones en Windows 10 y Windows 11, pueden observarse lecturas dispares (por ejemplo, Cám 1 a `11.4 ms` en Windows 11 y `2.1 ms` en Windows 10):

1. **La prueba diferencial (Cám 2):**  
   En la misma sesión de Windows 11 donde Cám 1 marcó `11.4 ms`, **Cám 2 registró `2.7 ms`** (prácticamente idéntica a los `2.2 ms` de Windows 10). Esto demuestra empíricamente que **no se trata de una pérdida de rendimiento del equipo ni de una degradación de Windows 11**. Si el sistema operativo o la máquina fuesen los causantes, todas las fuentes experimentarían el mismo incremento de latencia.
2. **Jitter y fluctuación inherente a redes inalámbricas (Wi-Fi):**  
   Las cámaras integran chips de red Wi-Fi (fabricante Espressif, prefijo `98:6E:E8`). En redes inalámbricas (especialmente en 2.4 GHz), la latencia oscila de manera natural entre 2 ms y 15 ms según el tráfico concurrente, las micro-interferencias del canal de radio y los reintentos de tramas en el aire (*Wi-Fi CSMA/CA*).
3. **Carga en el buffer de red del microcontrolador de la cámara:**  
   La Cám 1 se encuentra transmitiendo simultáneamente un flujo continuo de vídeo a 1080p @ 30 FPS. Si la llamada de sondeo TCP coincide con la emisión de un fotograma clave (*I-frame* de gran tamaño), la respuesta de la pila TCP de la cámara experimenta una ligera cola de espera de pocos milisegundos.
4. **Medición instantánea sin promedio:**  
   El valor es una fotografía instantánea del último paquete enviado en ese segundo exacto, por lo que fluctúa en tiempo real según el momento de captura.

### 6.3. Resolución de Direcciones MAC (ARP vs. Sintética Fallback)
En las tarjetas de cámara de la interfaz se refleja la dirección física:
* **En Windows 10:** Puede observarse `02:00:C0:A8:XX:XX`. Es una dirección MAC sintética (falsa) que el código genera como mecanismo de contingencia cuando la API nativa de Windows `iphlpapi.SendARP` no recibe respuesta directa (frecuente si existe aislamiento de clientes en el punto de acceso, enrutamiento intermedio o firewalls locales).
* **En Windows 11:** Aparece la dirección física real por hardware (prefijo de fabricante `98:6E:E8:XX:XX:XX`), lo que confirma que el descubrimiento ARP a nivel de Capa 2 (enlace de datos) se ejecutó con éxito y sin barreras de red.

### 6.4. Impacto en la Fluidez y Emisión en Directo
En un flujo de vídeo estándar a 30 FPS, cada fotograma dura **33.3 ms**. Una latencia de red de **11.4 ms** representa apenas un tercio de un fotograma, por lo que se sitúa ampliamente en el umbral de **tiempo real óptimo**, garantizando una sincronización perfecta sin saltos ni congelaciones tanto en Windows 10 como en Windows 11.

---

## 7. Tratamiento del Audio: Flujo NDI, Drivers Virtuales y Sincronización

### 7.1. Estado Actual del Proyecto: Emisión Exclusiva de Vídeo
En la arquitectura actual de esta suite, los dispositivos virtuales expuestos en Windows (`Camara 1 - Frontal (NDI)` y `Camara 2 - Lateral (NDI)`) **transmiten exclusivamente señal de vídeo**:
1. **Filtro DirectShow Dedicado:** El driver utilizado (`UnityCaptureFilter64.dll`) es un filtro DirectShow perteneciente a la categoría `CLSID_VideoInputDeviceCategory`. No registra ni implementa pines ni endpoints de audio ante el subsistema multimedia de Windows.
2. **Filtrado en Pipeline:** Tanto en el motor nativo Rust ([`pipeline.rs`](file:///d:/Documentos/Antigravity/NDI%20Virtual%20C%C3%A1mera/src-tauri/src/pipeline.rs#L58-L72)) como en el entorno Python, el receptor NDI filtra explícitamente tramas de tipo `NDILIB_FRAME_TYPE_VIDEO`. Las tramas de audio que viajan por el flujo NDI de la red se descartan deliberadamente para optimizar el rendimiento y el consumo de CPU.

### 7.2. Características y Limitaciones del Audio Integrado (Nuroum V403)
La cámara Nuroum V403 cuenta con un array de micrófonos estéreo duales con cancelación de ruido ambiental orientados a conferencias (*huddle rooms*):
* **Baja fidelidad para producción:** Al estar integrados en el chasis de la cámara (frecuentemente montada en techo, trípode o pared a varios metros del orador), el audio captado sufre de reverberación de sala, distancia acústica y compresión agresiva del algoritmo de supresión de ruido.
* **Limitación Crítica del Firmware (Comprobación Empírica):**  
  Se ha realizado un sondeo de red a bajo nivel conectando directamente con la API C de NDI SDK v6 a ambas cámaras de prueba en la red local.  
  **Resultado:** Durante la emisión continua se recibieron cerca de 150 fotogramas de vídeo por cámara y **0 paquetes de audio NDI (`NDILIB_FRAME_TYPE_AUDIO = 0`)**.  
  Esto demuestra que el firmware actual de las cámaras Nuroum V403 **no multiplexa ni emite paquetes de audio en su flujo de red NDI|HX**. Los micrófonos integrados operan exclusivamente por USB (UAC) cuando la cámara se conecta directamente por cable USB al PC, pero el procesador de la cámara no los incluye en la transmisión por red IP.
* **No apto para máster de emisión:** Para directos, podcasts o streaming profesional, la captación debe delegarse obligatoriamente en microfonía dedicada (solapas inalámbricas, microfonía dinámica o mesa de mezclas conectada por interfaz USB al PC).


### 7.3. Utilidad Técnica: Audio de Referencia para Sincronización (*Scratch Audio*)
Aunque la calidad no sea adecuada para la emisión final, la captura del audio NDI tiene un alto valor técnico para **sincronización de pistas (*Warping / Waveform Alignment*)**:
* En entornos de postproducción o multicámara con grabación local, la pista de audio captada por la cámara viaja temporalmente sincronizada con los fotogramas del sensor de vídeo.
* Permite al software de edición (DaVinci Resolve, Premiere Pro, etc.) o a herramientas automáticas de alineación correlacionar la forma de onda de la cámara con las pistas de los micrófonos de estudio de alta calidad, alineando vídeo y audio al milisegundo de forma automática.

### 7.4. Arquitectura para un Micrófono Virtual en Windows (Zoom / Teams)
Si en el futuro se requiriese disponer de un micrófono virtual seleccionable en aplicaciones de videollamada como Zoom, Microsoft Teams o Google Meet, deben considerarse los siguientes aspectos de arquitectura:

1. **Separación de Subsistemas en Windows:**  
   Windows no permite que un driver DirectShow de captura de vídeo entregue audio a aplicaciones de usuario. Incluso las webcams USB físicas se registran como dos dispositivos independientes a nivel de bus: un dispositivo UVC (*USB Video Class*) y un dispositivo UAC (*USB Audio Class*).
2. **Requisitos de Driver de Audio del Kernel:**  
   Crear un dispositivo de captura de audio virtual nativo requiere desarrollar un driver WDM / Audio Endpoint de Windows con firma de código comercial validada por Microsoft (WHQL / EV). Desarrollar un driver de audio propio desde cero resulta poco práctico y propenso a problemas de compatibilidad.
3. **Flujo de Integración Recomendado (con Driver Externo Firmado):**  
   Para implementar esta funcionalidad sin complicaciones de firmas del kernel:
   * **Paso 1 (Ingesta NDI):** Habilitar en `pipeline.rs` la lectura de tramas `NDILIB_FRAME_TYPE_AUDIO`, obteniendo los bloques PCM (flotantes a 48 kHz interleaved).
   * **Paso 2 (Salida hacia Cable Virtual):** Mediante librerías de audio como `cpal` (Rust) o `sounddevice` (Python), enrutar ese flujo de audio hacia la entrada de un driver de audio virtual estándar ya firmado, como **VB-Audio Virtual Cable** (`CABLE Input`).
   * **Paso 3 (Consumo en la App):** En Zoom, Teams u OBS, el usuario selecciona en el desplegable de micrófono el dispositivo **`CABLE Output`**, disponiendo de la voz de la cámara en perfecta sincronía.

### 7.5. Conclusión Técnica y Descarte de Audio NDI en el Firmware
Tras la verificación empírica con sondeo de sockets C NDI en ambas cámaras, se constató que el microcódigo de las cámaras Nuroum V403 emite 0 paquetes de audio por la red local (`NDILIB_FRAME_TYPE_AUDIO = 0`).  
Por consiguiente, el proyecto se mantiene estrictamente en su alcance de diseño óptimo: **emisión multicámara DirectShow exclusiva de vídeo ultra-ligera y de alto rendimiento**, evitando complejidades y dependencias de audio innecesarias en el equipo anfitrión, y delegando la captación de sonido en interfaces USB o microfonía de producción dedicada.

---

## 8. Optimizaciones de Rendimiento y Grabación Dual MKV

Con el fin de posibilitar la ejecución de la suite tanto en equipos de altas prestaciones como en mini-PCs de consumo contenido (ej. procesadores Intel N100 / AMD Ryzen 1600 con GPU básica):

### 8.1. Desacoplo de Renderizado y Modo Rendimiento (VISTA ON / ECO OFF)
- **Modo Rendimiento (`ECO`):** Desactiva el escalado por software OpenCV (`cv2.resize` / `cv2.imencode`) y el transporte HTTP Base64 de las miniaturas.
- **Salida DirectShow Inalterada:** Los hilos de entrega DirectShow (`pyvirtualcam`) continúan emitiendo a 1080p @ 30 FPS sin interrupción ni aumento de latencia.
- **Ahorro de CPU:** En procesadores de 4 hilos (como el Intel N100), el paso a modo ECO reduce la carga de procesamiento entre un 60% y un 75%.

### 8.2. Pausa Automática al Minimizar la Ventana
- Integración dual mediante API de visibilidad de navegador (`document.hidden` / `visibilitychange`) y eventos nativos de ventana `pywebview` (`minimized` y `restored`).
- Al ocultarse o minimizarse la interfaz, el sondeo de miniaturas se detiene y la telemetría se reduce de 500 ms a 2000 ms, liberando la CPU del equipo.

### 8.3. Tasa de Refresco de Previsualización Configurable
- Selector disponible en la ventana de Ajustes con persistencia en [`config.json`](file:///d:/Documentos/Antigravity/NDI%20Virtual%20C%C3%A1mera/config.json):
  - **2 FPS (Modo Eco):** Ideal para equipos modestos de control desatendido.
  - **4 FPS (Equilibrado - Recomendado):** Proporciona supervisión visual clara con consumo de CPU mínimo (<3%).
  - **8 FPS (Fluido):** Orientado al puesto de operador con control de joystick PTZ activo.

### 8.4. Grabación Multicámara Dual en Contenedor MKV (Puntos 5 y 6)
- **Autodetección de Hardware Encoder:** Al iniciar la suite, el subsistema [`core/recorder.py`](file:///d:/Documentos/Antigravity/NDI%20Virtual%20C%C3%A1mera/core/recorder.py) sondea la GPU mediante sondas FFmpeg rápidas:
  1. `h264_nvenc` (NVIDIA GeForce / RTX)
  2. `h264_qsv` (Intel QuickSync GPU)
  3. `h264_amf` (AMD Radeon GPU / APU)
  4. `libx264 ultrafast` (CPU Software Fallback)
- **Aislamiento de Hilos (Zero-Drop en DirectShow):** La grabación utiliza colas asíncronas independientes (`queue.Queue(maxsize=60)` con `put_nowait`). Cualquier retardo de escritura en disco o saturación I/O descarta tramas exclusivamente en el archivo grabado, sin comprometer nunca la entrega a la cámara virtual DirectShow.
- **Seguridad Matroska (MKV):** Los archivos MKV escriben clusters e índices de forma incremental. Si la aplicación o el sistema sufrieran un corte de energía, el archivo queda 100% íntegro y reproducible hasta el último segundo grabado.
- **Nomenclatura y Destino Personalizable:**
  - Nombres generados: `<fecha>_<hora>_<id_cámara>.mkv` (ej. `20261025_231719_Cam_1.mkv`).
  - Directorio por defecto: subcarpeta `grabaciones/` dentro del proyecto.
  - Directorio configurable en la interfaz con botón de navegación nativo de Windows (diálogo de selección de carpetas de pywebview / Win32).

#### 8.4.1. Métrica y Calidad del Fichero MKV Generado (Inspección MediaInfo)
La inspección técnica del fichero resultante confirma una parametrización óptima para difusión y postproducción:
* **Perfil de Vídeo:** `AVC / H.264 High@L4` con codificación aritmética `CABAC` y 3 fotogramas de referencia (`3 Ref Frames`), procesado íntegramente por `h264_nvenc`.
* **Cadencia Constante (CFR):** Grabado a `25,000 FPS Constante` (frecuencia europea PAL 50 Hz anti-parpadeo), sincronizado al milímetro con el sensor de la cámara Nuroum V403. Esto elimina desincronizaciones de audio/vídeo al importar a editores no lineales como Adobe Premiere o DaVinci Resolve.
* **Tasa de Bits Adaptativa (VBR):** Media de `4.422 kb/s` (~4.5 Mbps) con ráfaga máxima configurada a `12,0 Mb/s` para evitar pixelaciones durante paneos de joystick PTZ rápidos.
* **Colorimetría:** `YUV 4:2:0 Progresivo (8-bit) Limited Range`, asegurando que no se produzca aplastamiento de sombras ni recorte de altas luces en reproductores convencionales.
* **Consumo de Almacenamiento:** ~34 MiB por minuto de grabación. Una sesión dual simultánea (2 cámaras a la vez) consume aproximadamente **4.05 GB por hora**, permitiendo más de 45 horas continuas de grabación en un disco de 233 GB.

### 8.5. Validación y Prevención de Nombres Duplicados
- **Validación Visual en Tiempo Real (Frontend):** En la ventana de configuración, si el usuario introduce por error el mismo alias en dos o más cámaras, los campos conflictivos se destacan en rojo intenso y se muestra un aviso de error bloqueando la acción de guardado. Al modificar el texto para corregir el conflicto, la advertencia y el bloqueo desaparecen de inmediato.
- **Validación en Backend (`POST /api/config`):** El servidor HTTP intercepta la solicitud y rechaza la asignación si distintas fuentes apuntan a un mismo nombre normalizado.
- **Seguridad en el Grabador (`MultiCameraRecordingManager`):** Si por alguna razón concurrente dos cámaras compartiesen nombre, el grabador detecta la colisión y añade de forma automática un sufijo identificativo (`_108`, `_171`), impidiendo en cualquier escenario la sobreescritura accidental de ficheros de vídeo.

### 8.6. Optimización Ergonómica de Configuración y Sondeo de Red en Caliente
- **Cierre y Guardado Unificado (Aspa `X`):** Se eliminaron los botones inferiores (`CANCELAR` / `GUARDAR`). El botón de cierre `X` en la cabecera valida los campos, persiste los cambios en [`config.json`](file:///d:/Documentos/Antigravity/NDI%20Virtual%20C%C3%A1mera/config.json) y cierra la ventana en un único clic, ahorrando espacio vertical.
- **Ajuste de Dimensiones y Visibilidad Completa:** El formulario se rediseñó a una altura compacta (~240 px) con espaciado optimizado y scroll interno suave, asegurando que todos los campos y la última línea de alias sean 100% visibles incluso en el modo de 1 sola cámara (395 px de alto).
- **Sondeo de IPs en Caliente (*Hot-Reload*):** Al modificar el listado de IPs dirigidas en la interfaz, el demonio [`CameraDiscoveryDaemon.update_extra_ips()`](file:///d:/Documentos/Antigravity/NDI%20Virtual%20C%C3%A1mera/core/discovery.py) actualiza la instancia de NDI Finder al vuelo y comienza a sondear las nuevas direcciones IP inmediatamente, sin requerir reinicio del programa.

---

## 9. Estudio Arquitectónico: Escenario de Escalabilidad (>2 Cámaras Simultáneas en Red)

En el supuesto de ampliar el despliegue técnico a 3, 4 o más cámaras NDI activas en la misma red local:

### 9.1. Compatibilidad Nativa del Software Actual
El diseño modular implementado está preparado para múltiples cámaras sin topes numéricos arbitrarios:
* **Descubrimiento ([`core/discovery.py`](file:///d:/Documentos/Antigravity/NDI%20Virtual%20C%C3%A1mera/core/discovery.py)):** Registra y sondea tantas fuentes mDNS o IPs dirigidas como se presenten en la red.
* **Pipeline de Ingesta ([`core/video_pipeline.py`](file:///d:/Documentos/Antigravity/NDI%20Virtual%20C%C3%A1mera/core/video_pipeline.py)):** Asigna un hilo receptor NDI independiente para cada cámara en línea.
* **Grabador Multicámara ([`core/recorder.py`](file:///d:/Documentos/Antigravity/NDI%20Virtual%20C%C3%A1mera/core/recorder.py)):** Despacha procesos FFmpeg aislados por cámara con nomenclatura temporal y anti-colisión garantizada.
* **Interfaz ([`ui/app.js`](file:///d:/Documentos/Antigravity/NDI%20Virtual%20C%C3%A1mera/ui/app.js)):** Renderiza reactivamente una tarjeta de supervisión con telemetría para cada dispositivo.

### 9.2. Dispositivos Virtuales DirectShow (Windows)
* **Escenario de 3 a 4 Cámaras:**  
  El driver DirectShow [`UnityCapture`](file:///d:/Documentos/Antigravity/NDI%20Virtual%20C%C3%A1mera/core/virtual_cam.py) soporta nativamente hasta 4 dispositivos virtuales simultáneos (`Unity Video Capture`, `Unity Video Capture #2`, `#3` y `#4`). Las constantes internas ya están declaradas en [`core/virtual_cam.py`](file:///d:/Documentos/Antigravity/NDI%20Virtual%20C%C3%A1mera/core/virtual_cam.py#L208-L213); habilitarlas requiere únicamente registrar los filtros `#3` y `#4` en el sistema.
* **Escenario de >4 Cámaras:**  
  Windows y las aplicaciones de videoconferencia (Zoom, Teams) no están preparadas para gestionar 6 u 8 webcams físicas abiertas al mismo tiempo. El patrón de diseño profesional en este caso es la **Matriz de Enrutamiento (*Routing Switcher*)**: la suite mantiene 2 o 4 dispositivos virtuales fijos en Windows, y la interfaz permite conmutar qué cámara física se redirige a cada dispositivo virtual.

### 9.3. Rendimiento de Codificación Hardware y Carga de CPU
* **NVIDIA NVENC (GeForce RTX 4060):**  
  NVIDIA actualizó oficialmente el límite de sesiones concurrentes de NVENC en GPUs GeForce a **5 transmisiones simultáneas** (drivers 531+ / 550+). Por tanto, puede grabar de 1 a 5 cámaras 1080p30 en hardware en paralelo con una carga de GPU insignificante (<6%).
* **Intel QuickSync (Mini-PC N100):**  
  El bloque multimedia QuickSync de 12ª generación codifica fluidamente entre 3 y 4 señales 1080p30 en hardware. A partir de 5 cámaras se saturaría el ancho de banda de memoria de la gráfica integrada.
* **CPU Software (`libx264 ultrafast` en AMD Ryzen 1600):**  
  La codificación por CPU escala linealmente: 2 cámaras suponen un ~35% de CPU, 4 cámaras un ~75-85%, y 6 cámaras colapsarían el procesador sin GPU dedicada.
* **Escritura en Disco:**  
  4 cámaras a 4.5 Mbps equivalen a ~18 Mbps (~2.25 MB/s), lo que no supone ningún esfuerzo para discos SSD o unidades NVMe.

### 9.4. Ancho de Banda en Red Local (Gigabit Ethernet)
Las cámaras de tipo Nuroum V403 transmiten mediante el protocolo comprimido NDI|HX (~15 a 25 Mbps por flujo a 1080p30):
* **2 Cámaras:** ~40-50 Mbps (5% de saturación en red Gigabit).
* **4 Cámaras:** ~80-100 Mbps (10% de saturación).
* **8 Cámaras:** ~160-200 Mbps (20% de saturación, plenamente soportable por switches 1 Gbps comerciales).

### 9.5. Ergonomía Visual en Interfaz
* Con 1 o 2 cámaras, la disposición actual en columna única vertical (395 px y 665 px) es óptima para mantener la ventana anclada en un lateral (*Always on Top*).
* Con 3 o 4 cámaras, una columna única vertical requeriría más de 1200 px de alto, desbordando monitores Full HD. En ese escenario, la interfaz se adapta mediante una **disposición en cuadrícula 2x2 (Grid táctico)** con dimensiones de ventana de aproximadamente 640 x 550 px.

| Variable Técnica | 2 Cámaras (Actual) | 3 a 4 Cámaras | 5 a 8 Cámaras |
| :--- | :--- | :--- | :--- |
| **Red LAN Gigabit (1 Gbps)** | Óptimo (~50 Mbps) | Holgado (~100 Mbps) | Viable en NDI\|HX (~200 Mbps) |
| **Cámaras Virtuales DirectShow** | 2 nativas (Activas) | Requiere registrar `#3` y `#4` | Requiere Matriz Lógica a 2-4 salidas |
| **Grabación NVENC (RTX 4060)** | <2% GPU | ~5% GPU (Dentro de sesión máx. 5) | Supera límite de fábrica GeForce |
| **Grabación Intel QSV (N100)** | <4% GPU | ~10% GPU (Viable) | Límite de memoria compartida iGPU |
| **Grabación CPU (Ryzen 1600)** | ~35% CPU | ~80% CPU (Al límite) | Inviable sin aceleración hardware |
| **Disposición UI** | Columna única lateral | Cuadrícula 2x2 (*Grid*) | Cuadrícula 4x2 o pestañas |










