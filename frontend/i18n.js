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
    cam_default_1: "Cámara 1 - Frontal",
    cam_default_2: "Cámara 2 - Lateral",

    // Botón Maestro de Cámara Virtual
    btn_start_vcam: "ACTIVAR CÁMARAS VIRTUALES",
    btn_stop_vcam: "DETENER CÁMARAS VIRTUALES",
    vcam_active_notice: "MULTIDISPOSITIVO ACTIVO (OBS / MANYCAM / ZOOM)",
    vcam_stopped_notice: "DISPOSITIVOS VIRTUALES EN ESPERA",

    // Modal de Configuración
    settings_title: "CONFIGURACIÓN NDI VIRTUAL CAM",
    settings_vcam_name: "Nombre del dispositivo virtual",
    settings_aliases_title: "Alias de Cámaras Detectadas",
    settings_extra_ips_title: "IPs Adicionales NDI (Sondeo Dirigido)",
    settings_extra_ips_hint: "Separadas por comas (ej. 192.168.9.108, 192.168.9.171)",
    settings_auto_start: "Iniciar cámara virtual automáticamente al arrancar",
    settings_btn_save: "GUARDAR CONFIGURACIÓN",
    settings_btn_close: "CERRAR",
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
    cam_default_1: "Camera 1 - Front",
    cam_default_2: "Camera 2 - Side",

    // Master Virtual Cam Action Button
    btn_start_vcam: "START VIRTUAL CAMERAS",
    btn_stop_vcam: "STOP VIRTUAL CAMERAS",
    vcam_active_notice: "MULTI-DEVICE ACTIVE (OBS / MANYCAM / ZOOM)",
    vcam_stopped_notice: "VIRTUAL DEVICES IN STANDBY",

    // Settings Modal
    settings_title: "NDI VIRTUAL CAM SETTINGS",
    settings_vcam_name: "Virtual device display name",
    settings_aliases_title: "Camera Friendly Aliases",
    settings_extra_ips_title: "NDI Extra IPs (Targeted Scanning)",
    settings_extra_ips_hint: "Comma separated (e.g. 192.168.9.108, 192.168.9.171)",
    settings_auto_start: "Auto-start virtual camera on launch",
    settings_btn_save: "SAVE CONFIGURATION",
    settings_btn_close: "CLOSE",
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
