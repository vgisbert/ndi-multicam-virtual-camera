/**
 * NDI Virtual Camera — Sistema de Internacionalización (i18n)
 * Tactical Broadcast Console
 */

const I18N_LOCALES = {
  SP: {
    _label: "SP",
    _name: "Español",

    // Cabecera
    app_title: "CÁMARA VIRTUAL NDI",
    btn_lang_title: "Cambiar idioma (Haga clic para alternar)",
    btn_pin_title: "Fijar ventana siempre visible (Always on Top)",
    btn_settings_title: "Configuración y Ajustes",
    btn_rec_title: "Grabar cámaras en formato MKV (Clic para iniciar/detener)",
    rec_idle: "REC",
    rec_active: "REC",
    btn_monitor_title: "Conmutar monitorización (Modo Rendimiento / Ahorro CPU)",
    monitor_on: "VISTA ON",
    monitor_off: "ECO (OFF)",
    monitor_eco_badge: "MODO RENDIMIENTO // PREVIEW EN PAUSA",
    monitor_eco_subtext: "Cámaras virtuales activas en segundo plano sin gasto de CPU",
    status_nominal: "SISTEMA NOMINAL // TODO OK",
    status_searching: "BUSCANDO CÁMARAS NDI EN LA RED...",
    status_no_network: "SIN ENLACE NDI // COMPRUEBE RED",
    cam_online_suffix: "CÁM ONLINE",

    // Sección de Miniaturas
    section_thumbnails: "CÁMARAS NDI DETECTADAS (SUPERVISIÓN EN VIVO)",
    tally_on_air: "EN EMISIÓN",
    tally_stby: "PREPARADA",
    tally_offline: "DESCONECTADA",
    offline_notice: "SIN SEÑAL NDI",
    offline_reconnecting: "REINTENTANDO CONEXIÓN...",

    // Telemetría
    telem_pgm: "MODO",
    telem_res: "RESOLUCIÓN",
    telem_fps: "FPS",
    telem_latency: "LATENCIA",
    telem_active: "MULTICAM ACTIVA",
    telem_standby: "EN ESPERA",

    // Nombres por defecto de cámaras
    cam_default_1: "Cám 1",
    cam_default_2: "Cám 2",

    // Botón Maestro de Cámara Virtual
    btn_start_vcam: "ACTIVAR CÁMARAS VIRTUALES",
    btn_stop_vcam: "DETENER CÁMARAS VIRTUALES",
    vcam_active_notice: "MULTIDISPOSITIVO ACTIVO (OBS / MANYCAM / ZOOM)",
    vcam_stopped_notice: "DISPOSITIVOS VIRTUALES EN ESPERA",

    // Modal de Configuración
    settings_title: "CONFIGURACIÓN NDI VIRTUAL CAM",
    settings_vcam_name: "Nombre del dispositivo virtual",
    settings_aliases_title: "Alias de Cámaras Detectadas",
    settings_duplicate_alias_error: "Error: Las cámaras deben tener nombres diferentes para evitar confusiones y colisiones.",
    settings_extra_ips_title: "IPs Adicionales NDI (Sondeo Dirigido)",
    settings_extra_ips_hint: "Separadas por comas (ej. 192.168.9.108, 192.168.9.171)",
    settings_preview_fps: "Tasa de Refresco de Miniatura (Previsualización)",
    fps_opt_2: "2 FPS (Modo Eco / Mínimo consumo CPU)",
    fps_opt_4: "4 FPS (Equilibrado - Recomendado)",
    fps_opt_8: "8 FPS (Fluido - Operador Joystick)",
    settings_recording_dir: "Carpeta de Grabaciones (MKV)",
    settings_recording_dir_hint: "Formato: <fecha>_<hora>_<id_cámara>.mkv. En blanco = subcarpeta 'grabaciones'",
    settings_browse_title: "Examinar carpeta de destino...",
    settings_protocol_title: "Protocolo / Resolución",
    proto_ndi_1080p: "NDI (1080p)",
    proto_rtsp_720p: "RTSP (720p)",
    settings_auto_start: "Iniciar cámara virtual automáticamente al arrancar",
    settings_btn_save: "GUARDAR CONFIGURACIÓN",
    settings_btn_close: "CERRAR",
    settings_close_title: "Guardar cambios y cerrar",
    settings_saved_toast: "Configuración guardada correctamente."
  },

  EN: {
    _label: "EN",
    _name: "English",

    // Header
    app_title: "NDI VIRTUAL CAMERA",
    btn_lang_title: "Change language (Click to toggle)",
    btn_pin_title: "Pin window always on top",
    btn_settings_title: "Settings & Configuration",
    btn_rec_title: "Record cameras in MKV format (Click to start/stop)",
    rec_idle: "REC",
    rec_active: "REC",
    btn_monitor_title: "Toggle video monitoring (Performance / Eco Mode)",
    monitor_on: "PREVIEW ON",
    monitor_off: "ECO (OFF)",
    monitor_eco_badge: "PERFORMANCE MODE // PREVIEW PAUSED",
    monitor_eco_subtext: "Virtual cameras active in background with zero graphic overhead",
    status_nominal: "SYSTEM NOMINAL // ALL SYSTEMS OK",
    status_searching: "SEARCHING FOR NDI CAMERAS...",
    status_no_network: "NO NDI LINK // CHECK LAN",
    cam_online_suffix: "CAM ONLINE",

    // Thumbnails Section
    section_thumbnails: "DETECTED NDI CAMERAS (LIVE MONITOR)",
    tally_on_air: "ON AIR",
    tally_stby: "READY",
    tally_offline: "OFFLINE",
    offline_notice: "NO NDI SIGNAL",
    offline_reconnecting: "RECONNECTING...",

    // Telemetry
    telem_pgm: "MODE",
    telem_res: "RESOLUTION",
    telem_fps: "FPS",
    telem_latency: "LATENCY",
    telem_active: "MULTICAM ACTIVE",
    telem_standby: "STANDBY",

    // Default camera names
    cam_default_1: "Cam 1",
    cam_default_2: "Cam 2",

    // Master Virtual Cam Action Button
    btn_start_vcam: "START VIRTUAL CAMERAS",
    btn_stop_vcam: "STOP VIRTUAL CAMERAS",
    vcam_active_notice: "MULTI-DEVICE ACTIVE (OBS / MANYCAM / ZOOM)",
    vcam_stopped_notice: "VIRTUAL DEVICES IN STANDBY",

    // Settings Modal
    settings_title: "NDI VIRTUAL CAM SETTINGS",
    settings_vcam_name: "Virtual device display name",
    settings_aliases_title: "Camera Friendly Aliases",
    settings_duplicate_alias_error: "Error: Cameras must have unique names to avoid confusion and file collisions.",
    settings_extra_ips_title: "NDI Extra IPs (Targeted Scanning)",
    settings_extra_ips_hint: "Comma separated (e.g. 192.168.9.108, 192.168.9.171)",
    settings_preview_fps: "Preview Thumbnail Refresh Rate",
    fps_opt_2: "2 FPS (Eco Mode / Low CPU)",
    fps_opt_4: "4 FPS (Balanced - Recommended)",
    fps_opt_8: "8 FPS (Fluid - Joystick Operator)",
    settings_recording_dir: "Recording Folder (MKV)",
    settings_recording_dir_hint: "Format: <date>_<time>_<camera_id>.mkv. Blank = 'grabaciones' subfolder",
    settings_browse_title: "Browse destination folder...",
    settings_protocol_title: "Protocol / Resolution",
    proto_ndi_1080p: "NDI (1080p)",
    proto_rtsp_720p: "RTSP (720p)",
    settings_auto_start: "Auto-start virtual camera on launch",
    settings_btn_save: "SAVE CONFIGURATION",
    settings_btn_close: "CLOSE",
    settings_close_title: "Save changes and close",
    settings_saved_toast: "Settings successfully saved."
  }
};

let currentLang = localStorage.getItem("ndi_vcam_lang") || "SP";
if (!I18N_LOCALES[currentLang]) currentLang = "SP";

function t(key) {
  const dict = I18N_LOCALES[currentLang] || I18N_LOCALES.SP;
  return dict[key] || key;
}

function applyI18n() {
  document.querySelectorAll("[data-i18n]").forEach(el => {
    const k = el.getAttribute("data-i18n");
    if (k && t(k)) el.textContent = t(k);
  });
  document.querySelectorAll("[data-i18n-title]").forEach(el => {
    const k = el.getAttribute("data-i18n-title");
    if (k && t(k)) el.setAttribute("title", t(k));
  });
  document.querySelectorAll("[data-i18n-placeholder]").forEach(el => {
    const k = el.getAttribute("data-i18n-placeholder");
    if (k && t(k)) el.setAttribute("placeholder", t(k));
  });

  const langBtn = document.getElementById("btn-lang");
  if (langBtn) {
    langBtn.textContent = I18N_LOCALES[currentLang]._label;
  }

  const monitorText = document.getElementById("btn-monitor-text");
  if (monitorText) {
    const isMon = (typeof isMonitoringEnabled !== "undefined") ? isMonitoringEnabled : true;
    monitorText.textContent = t(isMon ? "monitor_on" : "monitor_off");
  }

  const recText = document.getElementById("btn-record-text");
  if (recText && (typeof isRecording === "undefined" || !isRecording)) {
    recText.textContent = t("rec_idle") || "REC";
  }

  document.querySelectorAll(".eco-badge-text").forEach(el => {
    el.textContent = t("monitor_eco_badge");
  });
  document.querySelectorAll(".eco-subtext").forEach(el => {
    el.textContent = t("monitor_eco_subtext");
  });

  if (typeof updateMonitoringUI === "function" && typeof isMonitoringEnabled !== "undefined") {
    updateMonitoringUI(isMonitoringEnabled);
  }
}

function cycleLanguage() {
  const keys = Object.keys(I18N_LOCALES);
  let idx = keys.indexOf(currentLang);
  idx = (idx + 1) % keys.length;
  currentLang = keys[idx];
  localStorage.setItem("ndi_vcam_lang", currentLang);
  applyI18n();

  // Trigger reactive re-rendering of cards and telemetry in app.js
  if (typeof forceRefreshUI === "function") {
    forceRefreshUI();
  } else {
    if (typeof renderStatus === "function" && currentStatus) renderStatus(currentStatus);
    if (typeof renderCameras === "function" && currentCameras) renderCameras(currentCameras);
  }
}
