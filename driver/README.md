# Módulo Driver DirectShow Multicámara Virtual

Este directorio contiene los filtros DirectShow y los scripts de instalación para exponer las transmisiones NDI como múltiples dispositivos de captura simultáneos e independientes en Windows 10 y 11.

## 1. Archivos Activos
* **`UnityCaptureFilter64.dll`**: Filtro DirectShow de 64 bits de alto rendimiento basado en UnityCapture. Permite instanciar múltiples dispositivos independientes de captura con canales de memoria compartida dedicados (`UnityCapture_Data0`, `UnityCapture_Data1`).
* **`UnityCaptureFilter32.dll`**: Filtro DirectShow de 32 bits para compatibilidad opcional con aplicaciones de 32 bits.
* **`instalar_driver_multicamara.bat`**: Lanzador con auto-elevación a Administrador que ejecuta el registro de los 2 dispositivos virtuales.
* **`instalar_multicamara.ps1`**: Script PowerShell que invoca `regsvr32.exe /s /i:UnityCaptureDevices=2` y configura los nombres amigables:
  * `Camara 1 - Frontal (NDI)`
  * `Camara 2 - Lateral (NDI)`
* **`desinstalar_driver_multicamara.bat`**: Lanzador para desinstalar y desregistrar los filtros.
* **`desinstalar_multicamara.ps1`**: Limpia las entradas DirectShow del registro de Windows.

## 2. Mecanismo Multidispositivo (Shared Memory IPC)
Cada canal virtual opera con memoria compartida desacoplada:
* **Canal 0 (Cámara 1):** `UnityCapture_Mutx0`, `UnityCapture_Want0`, `UnityCapture_Sent0`, `UnityCapture_Data0`
* **Canal 1 (Cámara 2):** `UnityCapture_Mutx1`, `UnityCapture_Want1`, `UnityCapture_Sent1`, `UnityCapture_Data1`

Esto permite la captura simultánea en OBS Studio, ManyCam, Zoom o cualquier suite de producción sin bloqueos de contención ni parpadeos entre cámaras.
