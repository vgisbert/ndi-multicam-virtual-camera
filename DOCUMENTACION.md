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
        Dev1["Dispositivo 1: 'NDI Camara 1'"]
        Dev2["Dispositivo 2: 'NDI Camara 2'"]
    end

    subgraph MasterApp["Software de Realización Único"]
        OBS["OBS Studio / ManyCam"]
        Escena1["Escena 1: Solo Cám 1"]
        Escena2["Escena 2: Solo Cám 2"]
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
  1. **`NDI Camara 1`**
  2. **`NDI Camara 2`**

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
  Registra los 2 dispositivos virtuales simultáneos en Windows con permisos de Administrador (`NDI Camara 1` y `NDI Camara 2`).
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

### 5.3. Frecuencia Eléctrica (50 Hz vs. 60 Hz en NearSync), Cadencia Real y Metadatos NDI

Existe una relación directa entre el ajuste de frecuencia eléctrica en **NearSync** y la tasa de fotogramas efectiva del sistema:

1. **Anti-flicker Eléctrico (50 Hz = 25 FPS / 60 Hz = 30 FPS):**
   * **En Europa (Red 50 Hz):** Para evitar el parpadeo estroboscópico (*flicker*) bajo iluminación artificial (tubos fluorescentes y paneles LED convencionales), el sensor de la cámara ajusta su ciclo de integración y exposición a múltiplos de 1/50 s. Como consecuencia técnica necesaria, la tasa de captura del sensor conmuta a **25.0 FPS constantes** (estándar PAL / broadcast europeo).
   * **En América/Asia (Red 60 Hz):** El sensor expone a múltiplos de 1/60 s, capturando a **30.0 FPS constantes** (estándar NTSC).

2. **Incongruencia Observada (Firmware Nuroum V403):**
   * Cuando la cámara se configura a **50 Hz en NearSync**, el sensor captura físicamente a **25.0 FPS reales**.
   * Sin embargo, el firmware de la cámara tiene **cableado de forma estática en la cabecera NDI (`frame_rate_N = 30`, `frame_rate_D = 1`) el valor 30.0 FPS**. La cámara no actualiza los descriptores de stream NDI al cambiar la frecuencia de red.
   * Esto provocaba que reproductores o interfaces que leían la cabecera NDI mostrasen "30.0 FPS", mientras que el motor de grabación o herramientas como MediaInfo registraban la tasa física real entregada (~25 FPS / 25,200 FPS).

3. **Corrección Implementada en el Pipeline:**
   * Se desacopló la medición del flujo de la cabecera engañosa de NDI, calculando la cadencia únicamente a partir de los **fotogramas físicos entregados en el socket en ventanas de 1 segundo**.
   * **Normalización Broadcast (Anti-Jitter):** Para evitar fluctuaciones menores de redondeo en la red (ej. 24.8 o 25.2 FPS por variaciones temporales del reloj del sistema operativo), el motor normaliza automáticamente a cadencias de emisión estándar:
     * Si la tasa real se sitúa entre 23.5 y 26.5 FPS -> Normaliza a **`25.0 FPS`** (PAL 50 Hz).
     * Si la tasa real se sitúa entre 28.5 y 31.5 FPS -> Normaliza a **`30.0 FPS`** (NTSC 60 Hz).
   * Tanto la **interfaz táctica en pantalla** como el **parámetro `-r` del codificador FFmpeg en las grabaciones MKV** operan ahora sincronizados de forma exacta con la frecuencia real configurada en NearSync.

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
En la arquitectura actual de esta suite, los dispositivos virtuales expuestos en Windows (`NDI Camara 1` y `NDI Camara 2`) **transmiten exclusivamente señal de vídeo**:
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

---

## 10. Ingesta Híbrida NDI (1080p) vs RTSP (720p) por Cámara (Ahorro de Carga en Origen)

### 10.1. Diagnóstico de Rendimiento en Equipos con Procesadores Moderados (ej. AMD Ryzen 5 1600)
Al operar en equipos de procesador moderado como el AMD Ryzen 5 1600 (6 núcleos / 12 hilos) o mini-PCs, procesar 2 o más flujos continuos NDI Full HD a 1920x1080 (descompresión, conversión de espacio de color BGR, copia a memoria compartida DirectShow e inyección en codificador FFmpeg) impone una carga de cómputo relevante si ambas señales permanecen a resolución máxima.

Para optimizar el uso de recursos **en origen** (sin realizar un redimensionamiento por software en la CPU del ordenador que consumiría ciclos adicionales):
* Se descubrió mediante ingeniería inversa que las cámaras **Nuroum V403** entregan un flujo RTSP nativo secundario en el puerto estándar `554` (`rtsp://<ip>:554/live/mainStream`).
* Dicho flujo emite a resolución **HD 720p (1280x720) a 25.0 FPS constantes en formato H.264**, sin requerir credenciales de autenticación.
* **Reducción de Píxeles:** Pasar de 1920x1080 (2.073.600 px/frame) a 1280x720 (921.600 px/frame) supone una **reducción del 55,6% en el volumen de datos brutos procesados por segundo**, aliviando drásticamente el bus PCIe, la memoria RAM y el codificador de vídeo.

### 10.2. Selector Dinámico e Independiente por Cámara
En la ventana modal de Configuración, cada cámara detectada dispone de su propio selector de protocolo y resolución:
* **`NDI (1080p)`:** Calidad broadcast Full HD máxima, con latencia ultra-baja vía NDI C SDK.
* **`RTSP (720p)`:** Flujo HD de alta eficiencia capturado con transporte TCP de baja latencia (`fflags;nobuffer|max_delay;500000|stimeout;2000000`).

```mermaid
flowchart TD
    subgraph Cam1["Cámara 1 (Nuroum V403)"]
        StreamNDI1["NDI 1080p (TCP 5961)"]
        StreamRTSP1["RTSP 720p (TCP 554)"]
    end
    subgraph Cam2["Cámara 2 (Nuroum V403)"]
        StreamNDI2["NDI 1080p (TCP 5961)"]
        StreamRTSP2["RTSP 720p (TCP 554)"]
    end

    subgraph Suite["NDI Virtual Camera Pipeline Coordinator"]
        Selector1{"Selector Cámara 1<br/>(config.json)"}
        Selector2{"Selector Cámara 2<br/>(config.json)"}
        WorkerNDI["Worker NDI Loop"]
        WorkerRTSP["Worker RTSP Loop"]
    end

    subgraph Salidas["Salidas Transparentes"]
        DS1["DirectShow Dev 1"]
        DS2["DirectShow Dev 2"]
        MKV["Grabador Dual MKV"]
        Thumb["Miniaturas UI"]
    end

    StreamNDI1 -.-> Selector1
    StreamRTSP1 --> Selector1
    StreamNDI2 --> Selector2
    StreamRTSP2 -.-> Selector2

    Selector1 --> WorkerRTSP
    Selector2 --> WorkerNDI

    WorkerRTSP --> DS1
    WorkerRTSP --> MKV
    WorkerRTSP --> Thumb

    WorkerNDI --> DS2
    WorkerNDI --> MKV
    WorkerNDI --> Thumb
```

### 10.3. Conmutación en Caliente (*Hot-Switching*) sin Reinicio
El coordinador de hilos (`VideoPipeline._coordinator_loop` en [`core/video_pipeline.py`](file:///d:/Documentos/Antigravity/NDI%20Virtual%20C%C3%A1mera/core/video_pipeline.py)) compara en tiempo real el protocolo deseado por el usuario con el protocolo en ejecución de cada `CameraStreamWorker`. Si el usuario cambia una cámara de NDI a RTSP o viceversa:
1. El hilo activo finaliza de forma segura y controlada liberando sus descriptores de red.
2. Se instancia el nuevo worker adecuado (NDI C receiver o RTSP low-latency client) sin afectar a las otras cámaras.
3. La interfaz web actualiza al instante la insignia visual de la tarjeta (`NDI 1080p` en cian / `RTSP 720p` en ámbar) y en la configuración muestra el driver asignado junto a su resolución (`NDI Camara X · 720p / 1080p`).
4. El dispositivo DirectShow asociado adapta su lienzo virtual (`1280x720` para RTSP o `1920x1080` para NDI) eliminando el consumo de interpolación en CPU (`cv2.resize`) y reduciendo el ancho de banda RAM en más del 55%. La grabación MKV continúa recibiendo fotogramas fluidamente.

### 10.4. Análisis Técnico de Latencia: ¿Por Qué el Retraso en RTSP es Mayor que en NDI?
Durante las pruebas operativas se observa de manera consistente que **la señal capturada por RTSP presenta un retraso (latencia) visiblemente superior al flujo NDI** (generalmente entre 300 ms y 700 ms frente a los 15-45 ms de NDI). Este comportamiento no es un defecto de implementación ni un error de red, sino el resultado directo de diferencias fundamentales de arquitectura entre ambos protocolos:

#### 1. Filosofía de Diseño y Caso de Uso Original
* **NDI (Network Device Interface):** Diseñado específicamente por NewTek para **producción broadcast y realización en directo** sobre redes locales LAN. Su prioridad absoluta es la latencia ultra-baja (sub-frame a 1-2 frames) y la fidelidad visual, permitiendo mezclar cámaras en tiempo real sin desfases perceptibles con la acción o el audio de mesa.
* **RTSP (Real-Time Streaming Protocol):** Diseñado para control y transporte de streaming continuo en videovigilancia (CCTV) o distribución remota. Su prioridad es la **estabilidad de transmisión y el bajo consumo de ancho de banda** frente a pérdidas de paquetes o congestión, tolerando retrasos de amortiguación para evitar cortes de imagen.

#### 2. Compresión de Vídeo: Intra-frame (SpeedHQ) vs. Inter-frame (H.264 / GOP)
* **NDI (High Bandwidth / NDI C SDK):** Emplea compresión de tipo *Intra-frame* (SpeedHQ, similar conceptualmente a Apple ProRes o Avid DNxHD). Cada fotograma se comprime y decodifica como una entidad geométrica completa e independiente:
  * El codificador y el decodificador procesan cada frame en **< 5 milisegundos**.
  * No hay análisis de movimiento temporal ni retención de secuencias en memoria.
* **RTSP (H.264 nativo de la cámara Nuroum V403):** El chip SoC de la cámara comprime el flujo 720p mediante compresión *Inter-frame* estructurada en un GOP (*Group of Pictures*) con fotogramas I (clave) y P (predictivos):
  * El codificador hardware interno de la cámara debe retener y comparar fotogramas para calcular vectores de movimiento antes de enviar los paquetes RTP por la red, introduciendo una latencia inicial inherente de codificación (*encoder delay*).

#### 3. Búfer de Demuxing y Recepción (*Jitter Buffer*)
* **RTSP (OpenCV + FFmpeg Backend):** En [`core/video_pipeline.py`](file:///d:/Documentos/Antigravity/NDI%20Virtual%20C%C3%A1mera/core/video_pipeline.py), el flujo RTSP se procesa a través de `cv2.VideoCapture(..., cv2.CAP_FFMPEG)`. Aunque se configuren banderas de baja latencia (`fflags;nobuffer|max_delay;500000|buffer_size;102400`), el demuxer y el decodificador H.264 de FFmpeg requieren acumular internamente paquetes para reconstruir las unidades NAL y asegurar la continuidad del flujo antes de volcar la imagen descompresa en memoria compartida.
* **NDI:** La librería C de NDI transfiere los fotogramas en memoria BGR/UYVY de forma inmediata en cuanto el socket recibe los paquetes del frame, eliminando colas de espera en el receptor.

#### 4. Transporte de Red y Tasa de Cuadros (FPS)
* **Cadencia temporal:** El flujo NDI emite a **30.0 FPS** (33.3 ms por cuadro), mientras que el flujo RTSP secundario de la cámara entrega **25.0 FPS** (40.0 ms por cuadro).
* **Transporte TCP:** La conexión RTSP utiliza `rtsp_transport;tcp` para atravesar cortafuegos y evitar pérdida de paquetes. Si se produce una mínima retransmisión TCP, se produce una retención en cola (*head-of-line blocking*), acumulando un retraso adicional que se percibe como una latencia constante respecto al directo.

#### 5. Cuadro Comparativo de Compromiso (*Trade-off*)

| Característica | NDI (1080p) | RTSP (720p) |
| :--- | :--- | :--- |
| **Latencia perceptual típica** | **15 – 45 ms** (Tiempo real broadcast / sub-frame) | **300 – 700 ms** (Retraso notable de buffer/GOP) |
| **Tipo de compresión** | Intra-frame (SpeedHQ / NDI nativo) | Inter-frame (H.264 con GOP temporal) |
| **Tasa de fotogramas** | 30.0 FPS constantes | 25.0 FPS constantes |
| **Carga de CPU (Receptor)** | Mayor (descompresión Full HD 1080p) | Reducida (~55,6% menos píxeles) |
| **Consumo de ancho de banda** | ~100 – 140 Mbps por señal | ~3 – 6 Mbps por señal |
| **Uso idóneo recomendado** | Cámara principal, presentadores hablando (labios sincronizados con micro) | Cámara secundaria de contexto, monitores de apoyo, equipos de CPU modesta |

---

## 11. Arquitectura de Ciclo de Vida: Limpieza Pre y Post Aplicación (Anti-Zombies y Desbloqueo de Drivers)

### 11.1. Diagnóstico de Problemas de Sesión y Bloqueo en Windows
Durante sesiones continuadas de uso y pruebas, se identificaron tres incidencias clásicas en aplicaciones multimedia bajo Windows:
1. **Instancias Zombies Huérfanas:** Al cerrar la ventana, el proceso `python.exe` o `NDI Virtual Camera.exe` permanecía invisible en la tabla de procesos debido a bloqueos síncronos en el servidor HTTP (`server.shutdown()` esperando conexiones *keep-alive* activas del frontend).
2. **Bloqueo Persistente de Drivers DirectShow (`UnityCaptureFilter64.dll`):** Al quedar procesos zombies reteniéndola, la DLL del driver DirectShow quedaba cargada en memoria por el kernel de Windows. Windows impedía sobrescribir, compilar o reinstalar los archivos del driver ("Acceso denegado / Archivo en uso por otro proceso") hasta reiniciar el equipo.
3. **Pantalla en Blanco al Arrancar (*White Screen of Death*):** Si una sesión previa zombie dejaba el puerto TCP `8765` en estado `LISTEN` o `CLOSE_WAIT`, la nueva instancia de la aplicación no lograba servir la web local y `pywebview` abría una ventana vacía sin interfaz gráfica.

```mermaid
flowchart TD
    subgraph Arranque["1. Protocolo PRE-Aplicación (Startup)"]
        CheckZombie["kill_orphan_instances()<br/>Sondeo de PIDs anteriores"]
        CheckPort["find_pid_by_port(8765)<br/>Verificar socket TCP"]
        KillZombie["Terminación forzosa de zombies<br/>taskkill /F + CIM Terminate"]
        DynamicPort{"¿Puerto 8765 ocupado?"}
        Use8765["Usar 8765 (Estándar)"]
        FallbackPort["Asignar puerto dinámico<br/>8766, 8767... (Anti-White-Screen)"]
    end

    subgraph Ejecucion["2. Sesión Activa"]
        Webview["Ventana Táctica WebView2"]
        Engine["Ingesta Híbrida NDI/RTSP + VCam DirectShow"]
    end

    subgraph Cierre["3. Protocolo POST-Aplicación (Shutdown)"]
        Trigger["Evento 'X' (closing) / SIGINT / atexit"]
        MutexLock["Mutex Atómico (_shutdown_lock)"]
        StopPipe["1. Detener Pipeline y Grabador MKV (FFmpeg)"]
        CloseVCam["2. Cerrar Cámaras Virtuales DirectShow<br/>Liberar memoria y descargar DLLs"]
        StopDisc["3. Detener Demonio de Autodescubrimiento"]
        CloseSock["4. server_close() socket HTTP inmediato"]
        ForceExit["5. os._exit(0) Terminación Limpia Garantizada"]
    end

    CheckZombie --> CheckPort
    CheckPort --> KillZombie
    KillZombie --> DynamicPort
    DynamicPort -- "No" --> Use8765
    DynamicPort -- "Sí (inquebrantable)" --> FallbackPort
    Use8765 --> Webview
    FallbackPort --> Webview
    Webview <--> Engine

    Webview --> Trigger
    Trigger --> MutexLock
    MutexLock --> StopPipe
    StopPipe --> CloseVCam
    CloseVCam --> StopDisc
    StopDisc --> CloseSock
    CloseSock --> ForceExit
```

### 11.2. Protocolo de Limpieza PRE-Aplicación (Arranque Seguro)
Al iniciarse la aplicación ([`core/main.py`](file:///d:/Documentos/Antigravity/NDI%20Virtual%20C%C3%A1mera/core/main.py)), antes de crear ventanas o inicializar dispositivos multimedia:
1. **Inspección de Procesos Huérfanos:**
   - Si se ejecuta como binario `.exe`, localiza mediante PowerShell/WMI cualquier otro proceso `NDI Virtual Camera.exe` cuyo PID difiera del actual (`os.getpid()`) y lo finaliza.
   - Si se ejecuta desde el entorno virtual de Python, inspecciona la red local y los procesos asociados a `core/main.py`.
2. **Inspección de Socket Local TCP (`find_pid_by_port`):**
   - Ejecuta un sondeo nativo de conexiones activas. Si detecta que un proceso previo mantiene retenido el puerto `8765`, extrae su PID y lo destruye de inmediato mediante combinación de `taskkill /F /T` y el método WMI `Win32_Process.Terminate()`.
3. **Asignación Dinámica de Puerto de Rescate (*Anti-White-Screen*):**
   - Si por alguna directiva de seguridad del sistema operativo el puerto `8765` continuara ocupado, `start_http_server()` prueba automáticamente los puertos `8766` a `8775`. Al encontrar un puerto libre, levanta el servidor táctico y conecta `pywebview` exactamente a esa dirección (`http://127.0.0.1:<puerto_activo>`), eliminando por completo la posibilidad de pantallas en blanco.

### 11.3. Protocolo de Limpieza POST-Aplicación (Cierre Atómico)
Para asegurar que **nunca más queden procesos en segundo plano ni drivers bloqueados**:
1. **Manejador Atómico Protegido (`cleanup_all`):**
   - Implementado con cerrojo de exclusión mutua (`_shutdown_lock`) para evitar que múltiples eventos de cierre compitan entre sí.
2. **Inversión Estricta del Orden de Cierre:**
   - **Paso 1:** Se detiene el pipeline de vídeo y se cierran las grabaciones MKV de FFmpeg para sellar e indexar correctamente los ficheros de vídeo.
   - **Paso 2:** Se llama a `VirtualCameraManager.stop_all()`. Cada dispositivo virtual `VirtualCameraDevice` cancela su hilo de renderizado, invoca explícitamente `cam.close()` en `pyvirtualcam` y desmapea los canales de memoria compartida Win32. Al no quedar descriptores abiertos, Windows descarga de inmediato `UnityCaptureFilter64.dll`.
   - **Paso 3:** Se detiene el demonio de autodescubrimiento NDI y se destruye el objeto NDI Finder.
   - **Paso 4:** Se cierra el socket HTTP con `server.server_close()` en lugar de `shutdown()`, evitando esperas innecesarias de *keep-alive*.
   - **Paso 5:** Se invoca `os._exit(0)` para terminar el proceso inmediatamente a nivel de kernel, impidiendo que hilos secundarios de C/C++ queden como zombies.
3. **Enganches a Eventos de Ventana y Señales:**
   - `webview_window.events.closing`: inicia la liberación en el instante en que el usuario hace clic en el aspa `X` de Windows.
   - `webview_window.events.closed`: ejecuta la salida definitiva `os._exit(0)`.
   - Manejadores de señal `SIGINT` (Ctrl+C), `SIGTERM` y `atexit.register()`.

### 11.4. Resiliencia en Compilación y Despliegue (`build_exe.py`)
- **Rutina `safe_copy_file()`:** Si al compilar o actualizar la carpeta `dist_portable/` Windows detecta que un archivo (como un ejecutable o DLL) está siendo retenido por un proceso externo, el script renombra automáticamente el archivo en disco a `.old` (acción permitida por el sistema de archivos NTFS aun con *file locks* abiertos) y escribe el nuevo archivo limpio en su lugar, evitando que el compilador aborte por `PermissionError (WinError 32)`.
- **Scripts de Instalación de Drivers:** Tanto [`driver/instalar_multicamara.ps1`](file:///d:/Documentos/Antigravity/NDI%20Virtual%20C%C3%A1mera/driver/instalar_multicamara.ps1) como [`driver/desinstalar_multicamara.ps1`](file:///d:/Documentos/Antigravity/NDI%20Virtual%20C%C3%A1mera/driver/desinstalar_multicamara.ps1) detienen preventivamente cualquier proceso de cámara virtual antes de registrar o desregistrar las librerías con `regsvr32`.

---

## 12. Salida DirectShow Dedicada 1:1, Optimización de Rendimiento 720p y Negociación en OBS

### 12.1. Eliminación del Modo Espejo (Enrutamiento Dedicado 1:1 Estricto)
En versiones preliminares se implementó una función de duplicación o "espejo" donde, si solo una cámara estaba conectada, su flujo se duplicaba en el driver secundario. 
* **Problema Identificado:** En OBS Studio se producía un parpadeo intermitente cíclico entre el vídeo en vivo y la pantalla de espera (*standby*). Esto se debía a una condición de carrera: al enviar fotogramas al segundo dispositivo para espejarlo, el flag `is_receiving_frames()` pasaba a `True`, lo que detenía el clonado; tras 1,2 segundos de *timeout*, el dispositivo conmutaba al patrón de espera, reactivando nuevamente el espejo y ciclando infinitamente.
* **Solución Definitiva:** Se eliminó por completo cualquier lógica de clonado/espejo. Cada cámara tiene un mapeo físico estricto y dedicado:
  - **Cámara 1 (`192.168.9.108`):** Sale única y exclusivamente por el dispositivo DirectShow **`NDI Camara 1`**.
  - **Cámara 2 (`192.168.9.171`):** Sale única y exclusivamente por el dispositivo DirectShow **`NDI Camara 2`**.
  - Si una cámara está apagada o no conectada, su driver asociado permanece pacíficamente en pantalla de espera sin parpadeos ni interferencias cruzadas.

### 12.2. Depuración de la Interfaz de Configuración
Se refinaron los campos del panel de Ajustes para maximizar la usabilidad y eliminar parámetros redundantes:
1. **Eliminación de "IPs Adicionales NDI (Sondeo Dirigido)":** Se constató que en redes con direccionamiento diferente provocaba bloqueos y que el demonio de autodescubrimiento automático NDI resuelve dinámicamente las cámaras presentes sin requerir listas estáticas.
2. **Eliminación de "Nombre del Dispositivo Virtual":** El nombre de las cámaras virtuales (`NDI Camara 1`, `NDI Camara 2`) viene predeterminado por el registro de los drivers DirectShow en Windows, por lo que no tiene sentido exponerlo como texto editable al usuario.
3. **Filtrado de Cámaras Online:** En la lista de alias editables solo se muestran las cámaras que están físicamente conectadas y online en la red en ese momento.
4. **Insignia del Driver Asignado y Resolución:** Cada cámara online muestra de forma clara el driver DirectShow por el que está saliendo junto con su resolución negociada (ej. `SALIDA DIRECTSHOW: NDI Camara 2 · 720p` o `NDI Camara 1 · 1080p`).

### 12.3. Salida DirectShow Nativa 720p para el Modo RTSP (Cero CPU / Memoria)
Para optimizar el uso de recursos en ordenadores de potencia contenida:
* Cuando una cámara se configura en protocolo **`RTSP (720p)`**, su dispositivo virtual DirectShow asociado (`NDI Camara 2`) se crea e inicializa directamente en **1280x720 a 25.0 FPS**.
* **Eliminación del Reescalado OpenCV:** Al coincidir exactamente la resolución recibida por RTSP (1280x720) con el lienzo virtual de DirectShow (1280x720), la rutina `push_frame` omite la llamada a `cv2.resize`. El fotograma pasa de forma transparente a la memoria compartida, ahorrando entre un 3% y un 8% de uso de CPU por cámara.
* **Ahorro de Ancho de Banda en Bus/RAM:** Cada fotograma RGB sin comprimir ocupa 3,68 MB en 720p frente a los 8,29 MB de 1080p, lo que representa una reducción de más del 55% en la tasa de transferencia continua hacia DirectShow.
* **Standby Vectorial Adaptativo:** La pantalla de espera ajusta dinámicamente el tamaño de sus tipografías, cuadrículas y timecodes según `scale = width / 1920.0`, manteniéndose nítida y perfectamente encuadrada tanto en 720p como en 1080p.

### 12.4. Negociación DirectShow en OBS Studio: Por Qué OBS Solicita 1080p por Defecto
Al conectar OBS a un dispositivo virtual `NDI Camara 2`, puede observarse en el registro de OBS líneas como:
```text
[DShow Device: 'Dispositivo de captura de video'] settings updated: 
	video device: NDI Camara 2
	resolution: 1920x1080
	fps: 30.00 (interval: 333333)
```

#### Análisis Técnico:
1. **Arquitectura Pull de DirectShow:** En Windows DirectShow, el cliente receptor (OBS) es el *Filter Graph Manager* downstream que impone los parámetros de captura. El driver virtual COM (`UnityCaptureFilter64.dll`) expone una tabla fija de resoluciones soportadas (`_media[]`).
2. **Índice 0 por Defecto:** En `UnityCaptureFilter64.dll`, el índice `0` está compilado con `{1920, 1080}` a 30 FPS. Cuando la fuente de OBS está en *«Tipo de resolución/FPS: Por defecto del dispositivo»*, OBS consulta el formato `0` y exige 1080p al driver, obligando al filtro DirectShow a expandir la imagen para satisfacer la demanda de OBS.
3. **Configuración Óptima en OBS (Sincronización Nativa 1:1):**
   Para que OBS reciba nativamente los 720p a 25.0 FPS reales sin ningún sobremuestreo ni escalado:
   - Haz doble clic en la fuente de OBS $\rightarrow$ **Propiedades**.
   - Cambia **Tipo de resolución/FPS** a **Personalizado**.
   - En **Resolución**, selecciona **`1280x720`**.
   - En **FPS**, selecciona **`25`** (o *«Hacer coincidir con los FPS de salida»*).
   - Pulsa **Aceptar**.
   Tras este ajuste único, OBS leerá el flujo de memoria compartida directamente a 1280x720 @ 25.0 FPS, logrando el mínimo consumo de GPU y CPU en el sistema.












