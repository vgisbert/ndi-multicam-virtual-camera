/**
 * NDI Virtual Camera — Frontend Client Logic
 * Tactical Broadcast Console
 */

let isPinned = false;
let isMonitoringEnabled = true;
let isRecording = false;
let isDocumentVisible = !document.hidden;
let currentPreviewFps = 4;
let currentCameras = [];
let currentStatus = {};
let statusInterval = null;
let thumbInterval = null;

function setupPolling() {
  if (statusInterval) clearInterval(statusInterval);
  const statusRate = isDocumentVisible ? 500 : 2000;
  statusInterval = setInterval(() => {
    fetchStatus();
    fetchCameras();
  }, statusRate);

  restartThumbPolling();
}

function restartThumbPolling() {
  if (thumbInterval) clearInterval(thumbInterval);
  if (!isDocumentVisible || !isMonitoringEnabled) {
    return;
  }
  const thumbRate = Math.round(1000 / Math.max(1, currentPreviewFps));
  thumbInterval = setInterval(() => {
    if (isDocumentVisible && isMonitoringEnabled) {
      fetchThumbnails();
    }
  }, thumbRate);
}

// Auto-pausa al minimizar o desenfocar la ventana (document.hidden)
document.addEventListener("visibilitychange", () => {
  const visible = !document.hidden;
  handleVisibilityChange(visible);
});

async function handleVisibilityChange(visible) {
  isDocumentVisible = visible;
  try {
    await fetch("/api/window/visibility", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ visible: visible })
    });
  } catch (err) {
    // Non-critical
  }

  setupPolling();
  if (visible) {
    fetchStatus();
    fetchCameras();
    if (isMonitoringEnabled) {
      fetchThumbnails();
    }
  }
}

// Initialize on page load
document.addEventListener("DOMContentLoaded", () => {
  applyI18n();
  fetchStatus();
  fetchCameras();
  fetchThumbnails();
  setupPolling();
});

async function fetchStatus() {
  try {
    const res = await fetch("/api/status");
    if (!res.ok) return;
    const data = await res.json();
    currentStatus = data;
    renderStatus(data);
  } catch (err) {
    // Backend offline / connecting
  }
}

async function fetchCameras() {
  try {
    const res = await fetch("/api/cameras");
    if (!res.ok) return;
    const cameras = await res.json();
    currentCameras = cameras;
    renderCameras(cameras);
  } catch (err) {
    // Handled in catch
  }
}

async function fetchThumbnails() {
  if (!isMonitoringEnabled || !isDocumentVisible) return;
  try {
    const res = await fetch("/api/thumbnails");
    if (!res.ok) return;
    const thumbs = await res.json();
    updateThumbnails(thumbs);
  } catch (err) {
    // Handled in catch
  }
}

const DEFAULT_NAMES = [
  "Cám 1",
  "Cam 1",
  "Cám 2",
  "Cam 2",
  "Cámara 1 - Frontal",
  "Camera 1 - Front",
  "Cámara 2 - Lateral",
  "Camera 2 - Side",
  "Cámara 108",
  "Camera 108",
  "Cámara 171",
  "Camera 171",
  "Nuroum V403",
  "HAMEDAL-V403 (Channel 1)",
  "HAMEDAL-V403-2 (Channel 1)",
  "LOCALHOST (Nuroum Cam V403-)",
  ""
];

function isCustomAlias(alias) {
  if (!alias || typeof alias !== "string") return false;
  const s = alias.trim();
  if (!s) return false;
  return DEFAULT_NAMES.indexOf(s) === -1;
}

function getLocalizedAlias(cam) {
  if (!cam) return "";
  // 1. Si el usuario definió un alias personalizado, siempre tiene máxima prioridad
  if (isCustomAlias(cam.alias)) {
    return cam.alias;
  }
  // 2. Si no es personalizado, mostrar el nombre por defecto según idioma e IP
  const ip = cam.ip || "";
  const url = cam.url_address || "";
  if (ip === "192.168.9.108" || url.includes("192.168.9.108")) {
    return t("cam_default_1");
  }
  if (ip === "192.168.9.171" || url.includes("192.168.9.171")) {
    return t("cam_default_2");
  }
  return cam.alias || `Cámara ${cam.ip}`;
}

function renderStatus(status) {
  const oledPgm = document.getElementById("oled-pgm");
  const oledRes = document.getElementById("oled-res");
  const oledFps = document.getElementById("oled-fps");
  const statusLabel = document.getElementById("status-label");
  const vcamNote = document.getElementById("vcam-status-note");

  if (status.vcam) {
    if (oledRes) oledRes.textContent = status.vcam.resolution || "1920x1080";
    if (oledFps) oledFps.textContent = (status.vcam.fps || 0.0).toFixed(1);
    if (oledPgm) {
      oledPgm.textContent = status.vcam.is_active ? t("telem_active") : t("telem_standby");
      oledPgm.className = status.vcam.is_active ? "text-red-tac font-bold truncate max-w-[130px]" : "text-amber-tac font-bold truncate max-w-[130px]";
    }

    if (vcamNote) {
      vcamNote.textContent = status.vcam.is_active ? t("vcam_active_notice") : t("vcam_stopped_notice");
      vcamNote.className = status.vcam.is_active ? "text-cyan-tac/90 font-bold" : "text-txt-muted";
    }
  }

  if (status.monitoring_enabled !== undefined && status.monitoring_enabled !== isMonitoringEnabled) {
    updateMonitoringUI(status.monitoring_enabled);
  }

  if (status.preview_fps && status.preview_fps !== currentPreviewFps) {
    currentPreviewFps = status.preview_fps;
    restartThumbPolling();
  }

  if (status.recording) {
    renderRecordingState(status.recording);
  }

  // Header status indicator
  const onlineCount = currentCameras.filter(c => c.is_online).length;
  const countEl = document.getElementById("sources-count");
  if (countEl) countEl.textContent = onlineCount;
  const suffixEl = document.getElementById("sources-suffix");
  if (suffixEl) suffixEl.textContent = t("cam_online_suffix");

  if (onlineCount > 0) {
    statusLabel.textContent = t("status_nominal");
    statusLabel.className = "text-cyan-tac font-bold tracking-wider";
  } else {
    statusLabel.textContent = t("status_searching");
    statusLabel.className = "text-amber-tac font-bold tracking-wider";
  }
}

let lastResizedCount = null;

async function requestWindowResize(cameraCount) {
  if (lastResizedCount === cameraCount) return;
  lastResizedCount = cameraCount;
  try {
    await fetch("/api/window/resize", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ camera_count: cameraCount })
    });
  } catch (err) {
    // Non-critical in browser mode
  }
}

function renderCameras(cameras) {
  const container = document.getElementById("cameras-container");
  if (!container) return;

  // Filtrar solo las cámaras activas/conectadas (is_online)
  // Si no hay ninguna online, se muestra el indicador de búsqueda
  const onlineCameras = (cameras || []).filter(c => c.is_online);
  const displayCameras = onlineCameras.length > 0 ? onlineCameras : (cameras || []);

  const activeCount = onlineCameras.length;
  requestWindowResize(activeCount);

  if (!displayCameras || displayCameras.length === 0) {
    container.innerHTML = `
      <div class="p-4 text-center text-txt-muted flex flex-col items-center justify-center gap-2">
        <span class="material-symbols-outlined text-[24px] animate-spin text-cyan-tac">progress_activity</span>
        <span>${t("status_searching")}</span>
      </div>
    `;
    return;
  }

  // Preserve existing cards to avoid UI flicker, update contents or rebuild if length changed
  let existingCards = container.querySelectorAll(".camera-card");
  if (existingCards.length !== displayCameras.length) {
    container.innerHTML = "";
    displayCameras.forEach(cam => {
      const card = createCameraCardElement(cam);
      container.appendChild(card);
    });
  } else {
    displayCameras.forEach(cam => {
      updateCameraCardElement(cam);
    });
  }
}

function createCameraCardElement(cam) {
  const card = document.createElement("div");
  card.id = `card-${cam.cam_id}`;
  card.className = "camera-card rounded border p-1.5 flex flex-col gap-1 cursor-pointer transition-all";
  card.onclick = () => selectPgm(cam.cam_id);

  card.innerHTML = `
    <!-- CABECERA DE LA TARJETA -->
    <div class="flex items-center justify-between px-0.5">
      <div class="flex items-center gap-1 min-w-0">
        <span class="badge-tally px-1.5 py-0.2 rounded font-bold text-[8.5px] uppercase tracking-wider shrink-0"></span>
        <span class="cam-proto px-1 py-0.2 rounded font-bold text-[7.5px] uppercase tracking-wider shrink-0"></span>
        <span class="cam-alias font-sans font-bold text-[11px] text-txt-main truncate max-w-[125px]"></span>
      </div>
      <div class="text-[9px] text-txt-muted flex items-center gap-1 font-mono shrink-0">
        <span class="cam-fps text-amber-tac font-bold"></span>
        <span class="cam-res text-txt-muted/80"></span>
      </div>
    </div>

    <!-- PREVISUALIZACIÓN MINIATURA (ASPECT RATIO 16:9) -->
    <div class="relative w-full aspect-video bg-surface-lowest rounded overflow-hidden border border-border-tac/30 flex items-center justify-center">
      <img id="thumb-${cam.cam_id}" class="w-full h-full object-cover thumb-fade" src="" alt="Live Preview" style="display: none;">
      
      <!-- BADGE REC (GRABANDO) -->
      <div id="badge-rec-${cam.cam_id}" class="${isRecording ? '' : 'hidden'} absolute top-1.5 right-1.5 z-20 px-1.5 py-0.5 rounded bg-red-tac text-white font-bold text-[8px] flex items-center gap-1 shadow-[0_0_8px_#ff1744] tracking-wider">
        <span class="w-1.5 h-1.5 rounded-full bg-white animate-ping"></span>
        <span>REC</span>
      </div>
      
      <!-- FALLBACK DE ESPERA CUANDO NO HAY FOTOGRAMA -->
      <div id="thumb-placeholder-${cam.cam_id}" class="absolute inset-0 flex flex-col items-center justify-center text-txt-muted gap-1 p-2 text-center bg-surface-lowest">
        <span class="material-symbols-outlined text-[20px] text-cyan-tac/80 animate-pulse">videocam</span>
        <span class="text-[8.5px] uppercase tracking-wider text-txt-muted/70">${t("offline_reconnecting")}</span>
      </div>

      <!-- OVERLAY OFFLINE SI LA CÁMARA PIERDE CONEXIÓN -->
      <div id="thumb-offline-${cam.cam_id}" class="hidden absolute inset-0 bg-black/75 backdrop-blur-[1px] flex flex-col items-center justify-center gap-1 p-2 text-center">
        <div class="px-1.5 py-0.5 rounded bg-amber-dim border border-amber-tac text-amber-tac font-bold text-[9px] tracking-wider flex items-center gap-1">
          <span class="material-symbols-outlined text-[12px]">wifi_off</span>
          <span>${t("offline_notice")}</span>
        </div>
        <span class="text-[8px] text-txt-muted">${t("offline_reconnecting")}</span>
      </div>

      <!-- OVERLAY MODO RENDIMIENTO / ECO (MONITORIZACIÓN EN PAUSA) -->
      <div id="thumb-eco-${cam.cam_id}" class="${isMonitoringEnabled ? 'hidden' : ''} absolute inset-0 bg-surface-dim/95 flex flex-col items-center justify-center gap-1.5 p-2 text-center z-10">
        <div class="px-2 py-0.5 rounded bg-surface-high border border-cyan-tac/40 text-cyan-tac font-bold text-[9px] tracking-wider flex items-center gap-1">
          <span class="material-symbols-outlined text-[13px] text-cyan-tac">speed</span>
          <span class="eco-badge-text">${t("monitor_eco_badge")}</span>
        </div>
        <span class="text-[8px] text-txt-muted eco-subtext">${t("monitor_eco_subtext")}</span>
      </div>
    </div>

    <!-- PIE DE LA TARJETA CON METADATOS Y RED -->
    <div class="flex items-center justify-between px-0.5 text-[9px] text-txt-muted font-mono">
      <div class="flex items-center gap-1">
        <span class="w-1.5 h-1.5 rounded-full status-dot"></span>
        <span class="cam-ip text-txt-main font-bold"></span>
      </div>
      <div class="flex items-center gap-1.5">
        <span class="cam-mac text-txt-muted/70 text-[8px]"></span>
        <span class="cam-rtt font-bold"></span>
      </div>
    </div>
  `;

  applyCardData(card, cam);
  return card;
}

function updateCameraCardElement(cam) {
  const card = document.getElementById(`card-${cam.cam_id}`);
  if (card) {
    applyCardData(card, cam);
  }
}

function forceRefreshUI() {
  const container = document.getElementById("cameras-container");
  if (container) container.innerHTML = "";
  if (currentCameras) renderCameras(currentCameras);
  if (currentStatus) renderStatus(currentStatus);
}

function applyCardData(card, cam) {
  const tallyBadge = card.querySelector(".badge-tally");
  const protoBadge = card.querySelector(".cam-proto");
  const aliasEl = card.querySelector(".cam-alias");
  const fpsEl = card.querySelector(".cam-fps");
  const resEl = card.querySelector(".cam-res");
  const ipEl = card.querySelector(".cam-ip");
  const macEl = card.querySelector(".cam-mac");
  const rttEl = card.querySelector(".cam-rtt");
  const statusDot = card.querySelector(".status-dot");
  const offlineOverlay = card.querySelector(`#thumb-offline-${cam.cam_id}`);
  const ecoOverlay = card.querySelector(`#thumb-eco-${cam.cam_id}`);

  if (protoBadge) {
    const isRtsp = (cam.protocol === "rtsp");
    protoBadge.textContent = isRtsp ? "RTSP 720p" : "NDI 1080p";
    protoBadge.className = isRtsp
      ? "cam-proto px-1 py-0.2 rounded font-bold text-[7.5px] uppercase tracking-wider shrink-0 bg-amber-dim/60 border border-amber-tac/50 text-amber-tac"
      : "cam-proto px-1 py-0.2 rounded font-bold text-[7.5px] uppercase tracking-wider shrink-0 bg-cyan-dim/60 border border-cyan-tac/50 text-cyan-tac";
  }

  if (ecoOverlay) {
    if (isMonitoringEnabled) {
      ecoOverlay.classList.add("hidden");
    } else {
      ecoOverlay.classList.remove("hidden");
    }
  }

  aliasEl.textContent = getLocalizedAlias(cam);
  ipEl.textContent = cam.ip;
  macEl.textContent = cam.mac;
  resEl.textContent = cam.resolution || "1080p";

  if (cam.is_online) {
    statusDot.className = "w-1.5 h-1.5 rounded-full bg-cyan-tac shadow-[0_0_4px_#00f0ff]";
    rttEl.textContent = `${cam.latency_ms}ms`;
    rttEl.className = "cam-rtt text-cyan-tac font-bold";
    if (offlineOverlay) offlineOverlay.classList.add("hidden");
  } else {
    statusDot.className = "w-1.5 h-1.5 rounded-full bg-txt-muted";
    rttEl.textContent = "--ms";
    rttEl.className = "cam-rtt text-txt-muted font-bold";
    if (offlineOverlay) offlineOverlay.classList.remove("hidden");
  }

  // Multicamera Tally & card border styling
  const vcamActive = currentStatus.vcam && currentStatus.vcam.is_active;

  const displayFps = (cam.fps && cam.fps > 0) ? `${cam.fps.toFixed(1)} FPS` : (cam.is_online ? "30.0 FPS" : "--");

  if (vcamActive && cam.is_online) {
    // When virtual cameras are running and camera is online: LIVE ON AIR!
    card.className = "camera-card rounded border-2 border-red-tac bg-surface-low p-1.5 flex flex-col gap-1 transition-all tally-pgm-pulse";
    tallyBadge.className = "badge-tally px-1.5 py-0.2 rounded font-bold text-[8.5px] uppercase tracking-wider bg-red-tac text-white shadow-[0_0_8px_#ff1744]";
    tallyBadge.textContent = t("tally_on_air");
    fpsEl.textContent = displayFps;
    fpsEl.className = "cam-fps text-red-tac font-bold";
  } else if (cam.is_online) {
    // When virtual cameras are stopped, but camera is online and ready: PREPARADA
    card.className = "camera-card rounded border border-border-tac/60 hover:border-cyan-tac/60 bg-surface-low p-1.5 flex flex-col gap-1 transition-all";
    tallyBadge.className = "badge-tally px-1.5 py-0.2 rounded font-bold text-[8.5px] uppercase tracking-wider bg-surface-high border border-border-tac text-cyan-tac";
    tallyBadge.textContent = t("tally_stby");
    fpsEl.textContent = displayFps;
    fpsEl.className = "cam-fps text-amber-tac font-bold";
  } else {
    // When camera is offline
    card.className = "camera-card rounded border border-border-tac/20 bg-surface-dim opacity-70 p-1.5 flex flex-col gap-1 transition-all";
    tallyBadge.className = "badge-tally px-1.5 py-0.2 rounded font-bold text-[8.5px] uppercase tracking-wider bg-surface-high text-txt-muted";
    tallyBadge.textContent = t("tally_offline");
    fpsEl.textContent = "--";
    fpsEl.className = "cam-fps text-txt-muted font-bold";
  }
}

function updateThumbnails(thumbs) {
  if (!isMonitoringEnabled || !thumbs) return;
  for (const [camId, dataUrl] of Object.entries(thumbs)) {
    const img = document.getElementById(`thumb-${camId}`);
    const placeholder = document.getElementById(`thumb-placeholder-${camId}`);
    if (img && dataUrl) {
      if (img.src !== dataUrl) {
        img.src = dataUrl;
      }
      img.style.display = "block";
      if (placeholder) placeholder.style.display = "none";
    }
  }
}

function updateMonitoringUI(enabled) {
  isMonitoringEnabled = enabled;
  restartThumbPolling();
  const btn = document.getElementById("btn-monitor");
  const icon = document.getElementById("btn-monitor-icon");
  const text = document.getElementById("btn-monitor-text");

  if (btn && icon && text) {
    if (enabled) {
      btn.className = "px-1.5 py-0.5 rounded bg-surface-high hover:bg-surface-highest text-cyan-tac font-bold text-[9.5px] border border-border-tac/40 flex items-center gap-1 transition-colors cursor-pointer";
      icon.textContent = "visibility";
      text.textContent = t("monitor_on");
    } else {
      btn.className = "px-1.5 py-0.5 rounded bg-amber-dim/50 hover:bg-amber-dim/70 text-amber-tac font-bold text-[9.5px] border border-amber-tac/50 flex items-center gap-1 transition-colors cursor-pointer";
      icon.textContent = "visibility_off";
      text.textContent = t("monitor_off");
    }
  }

  // Update eco overlay on camera cards
  document.querySelectorAll('[id^="thumb-eco-"]').forEach(el => {
    if (enabled) {
      el.classList.add("hidden");
    } else {
      el.classList.remove("hidden");
    }
  });
}

async function toggleMonitoring() {
  try {
    const res = await fetch("/api/monitoring/toggle", { method: "POST" });
    const data = await res.json();
    if (data.success) {
      updateMonitoringUI(data.monitoring_enabled);
      if (data.monitoring_enabled) {
        fetchThumbnails();
      }
    }
  } catch (err) {
    console.error("Error al conmutar monitorizacion:", err);
  }
}

function formatRecordingDuration(totalSeconds) {
  const s = Math.max(0, Math.floor(totalSeconds || 0));
  const hrs = Math.floor(s / 3600);
  const mins = Math.floor((s % 3600) / 60);
  const secs = s % 60;
  const pad = (n) => String(n).padStart(2, "0");
  if (hrs > 0) {
    return `${pad(hrs)}:${pad(mins)}:${pad(secs)}`;
  }
  return `${pad(mins)}:${pad(secs)}`;
}

function renderRecordingState(rec) {
  if (!rec) return;
  isRecording = !!rec.is_recording;

  const btn = document.getElementById("btn-record");
  const dot = document.getElementById("btn-record-dot");
  const text = document.getElementById("btn-record-text");

  if (btn && dot && text) {
    if (isRecording) {
      const durStr = formatRecordingDuration(rec.elapsed_seconds);
      btn.className = "px-2 py-0.5 rounded bg-red-tac hover:bg-red-tac/90 text-white font-bold text-[9.5px] border border-red-tac shadow-[0_0_10px_#ff1744] flex items-center gap-1 transition-all cursor-pointer";
      dot.className = "w-2 h-2 rounded-full bg-white animate-ping";
      text.textContent = `REC ${durStr}`;
      const encText = rec.encoder_desc ? ` (${rec.encoder_desc})` : "";
      btn.title = `${t("btn_rec_title")}${encText}`;
    } else {
      btn.className = "px-2 py-0.5 rounded bg-surface-high hover:bg-surface-highest text-red-tac font-bold text-[9.5px] border border-red-tac/40 flex items-center gap-1 transition-all cursor-pointer";
      dot.className = "w-2 h-2 rounded-full bg-red-tac shadow-[0_0_6px_#ff1744]";
      text.textContent = t("rec_idle") || "REC";
      const encText = rec.encoder_desc ? ` (${rec.encoder_desc})` : "";
      btn.title = `${t("btn_rec_title")}${encText}`;
    }
  }

  // Update REC badge on camera cards
  const recordings = rec.recordings || {};
  document.querySelectorAll('[id^="badge-rec-"]').forEach(badge => {
    const camId = badge.id.replace("badge-rec-", "");
    if (isRecording && (!rec.camera_count || recordings[camId] || recordings[camId] === undefined)) {
      badge.classList.remove("hidden");
    } else {
      badge.classList.add("hidden");
    }
  });
}

async function toggleRecording() {
  const btn = document.getElementById("btn-record");
  if (btn) btn.classList.add("opacity-50");
  try {
    const res = await fetch("/api/recording/toggle", { method: "POST" });
    const data = await res.json();
    if (data.status) {
      renderRecordingState(data.status);
    }
    fetchStatus();
  } catch (err) {
    console.error("Error al conmutar grabacion:", err);
  } finally {
    if (btn) btn.classList.remove("opacity-50");
  }
}

async function selectPgm(camId) {
  try {
    await fetch("/api/pgm", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ cam_id: camId })
    });
    fetchStatus();
    fetchCameras();
  } catch (err) {
    console.error("Error al seleccionar PGM:", err);
  }
}

async function toggleVirtualCamera() {
  try {
    const res = await fetch("/api/vcam/toggle", { method: "POST" });
    const data = await res.json();
    fetchStatus();
  } catch (err) {
    console.error("Error al conmutar camara virtual:", err);
  }
}

async function togglePin() {
  try {
    const res = await fetch("/api/pin", { method: "POST" });
    const data = await res.json();
    isPinned = data.is_pinned;
    const pinBtn = document.getElementById("btn-pin");
    if (pinBtn) {
      if (isPinned) {
        pinBtn.className = "w-6 h-6 rounded bg-cyan-dim border border-cyan-tac flex items-center justify-center text-cyan-tac transition-colors cursor-pointer";
      } else {
        pinBtn.className = "w-6 h-6 rounded bg-surface-high hover:bg-surface-highest flex items-center justify-center text-txt-muted hover:text-cyan-tac transition-colors cursor-pointer";
      }
    }
  } catch (err) {
    console.error("Error al fijar ventana:", err);
  }
}

// Modal Settings
async function browseRecordingDir() {
  try {
    const res = await fetch("/api/browse-folder", { method: "POST" });
    const data = await res.json();
    if (data.success && data.directory) {
      const input = document.getElementById("cfg-recording-dir");
      if (input) input.value = data.directory;
    }
  } catch (err) {
    console.error("Error al examinar carpeta:", err);
  }
}

function openSettings() {
  const modal = document.getElementById("modal-settings");
  if (!modal) return;
  modal.classList.remove("hidden");

  // Populate fields
  fetch("/api/config").then(r => r.json()).then(cfg => {
    document.getElementById("cfg-vcam-name").value = cfg.virtual_camera_name || "NDI Virtual Camera";
    const extraIps = (cfg.network && cfg.network.ndi_extra_ips) ? cfg.network.ndi_extra_ips.join(", ") : "";
    document.getElementById("cfg-extra-ips").value = extraIps;
    if (document.getElementById("cfg-preview-fps")) {
      document.getElementById("cfg-preview-fps").value = String(cfg.preview_fps || 4);
    }
    if (document.getElementById("cfg-recording-dir")) {
      document.getElementById("cfg-recording-dir").value = cfg.recording_dir || "";
    }

    const aliasesBox = document.getElementById("cfg-aliases-container");
    aliasesBox.innerHTML = "";
    const errBox = document.getElementById("cfg-aliases-error");
    if (errBox) errBox.classList.add("hidden");

    currentCameras.forEach(cam => {
      const row = document.createElement("div");
      row.className = "flex items-center gap-1.5 bg-surface-lowest/40 p-1.5 rounded border border-border-tac/30";
      const displayVal = getLocalizedAlias(cam);
      const isRtsp = (cam.protocol === "rtsp");
      row.innerHTML = `
        <div class="flex flex-col flex-1 gap-0.5 min-w-0">
          <span class="text-[8.5px] font-mono text-txt-muted font-bold truncate">${cam.ip}</span>
          <input type="text" data-cam-id="${cam.cam_id}" value="${displayVal}" placeholder="Alias..." class="alias-input bg-surface-lowest border border-border-tac rounded px-1.5 py-0.5 text-txt-main text-[9.5px] outline-none focus:border-cyan-tac transition-colors">
        </div>
        <div class="flex flex-col gap-0.5 w-[115px] shrink-0">
          <span class="text-[8px] text-txt-muted uppercase font-bold" data-i18n="settings_protocol_title">${t("settings_protocol_title")}</span>
          <select data-cam-id="${cam.cam_id}" class="protocol-select bg-surface-lowest border border-border-tac rounded px-1 py-0.5 text-txt-main text-[9px] outline-none focus:border-cyan-tac">
            <option value="ndi" ${!isRtsp ? 'selected' : ''}>NDI (1080p)</option>
            <option value="rtsp" ${isRtsp ? 'selected' : ''}>RTSP (720p)</option>
          </select>
        </div>
      `;
      const inputEl = row.querySelector("input");
      if (inputEl) {
        inputEl.addEventListener("input", () => {
          document.querySelectorAll(".alias-input").forEach(i => i.classList.remove("border-red-tac", "bg-red-dim/20"));
          if (errBox) errBox.classList.add("hidden");
        });
      }
      aliasesBox.appendChild(row);
    });
  });
}

function closeSettings() {
  const modal = document.getElementById("modal-settings");
  if (modal) modal.classList.add("hidden");
  const errBox = document.getElementById("cfg-aliases-error");
  if (errBox) errBox.classList.add("hidden");
  document.querySelectorAll(".alias-input").forEach(i => i.classList.remove("border-red-tac", "bg-red-dim/20"));
}

async function saveAndCloseSettings() {
  const vcamName = document.getElementById("cfg-vcam-name").value.trim();
  const rawIps = document.getElementById("cfg-extra-ips").value;
  const extraIps = rawIps.split(",").map(s => s.trim()).filter(s => s.length > 0);

  // Verificación estricta: evitar que por error se ponga el mismo nombre a las cámaras
  const seenAliases = new Map();
  const duplicateInputs = [];
  const errBox = document.getElementById("cfg-aliases-error");

  document.querySelectorAll(".alias-input").forEach(input => {
    input.classList.remove("border-red-tac", "bg-red-dim/20");
    const val = input.value.trim().toLowerCase();
    if (val) {
      if (seenAliases.has(val)) {
        duplicateInputs.push(input);
        duplicateInputs.push(seenAliases.get(val));
      } else {
        seenAliases.set(val, input);
      }
    }
  });

  if (duplicateInputs.length > 0) {
    duplicateInputs.forEach(input => {
      input.classList.add("border-red-tac", "bg-red-dim/20");
    });
    if (errBox) errBox.classList.remove("hidden");
    return; // Cancelar guardado para evitar colisiones: mantiene el modal abierto para corregir
  } else {
    if (errBox) errBox.classList.add("hidden");
  }

  const aliases = {};
  document.querySelectorAll(".alias-input").forEach(input => {
    const camId = input.getAttribute("data-cam-id");
    const val = input.value.trim();
    if (camId) {
      const cam = currentCameras.find(c => c.cam_id === camId);
      if (cam) {
        aliases[cam.url_address] = val;
        aliases[cam.ip] = val;
        aliases[cam.cam_id] = val;
        cam.alias = val;
      }
    }
  });

  const protocols = {};
  document.querySelectorAll(".protocol-select").forEach(sel => {
    const camId = sel.getAttribute("data-cam-id");
    const protoVal = sel.value;
    if (camId) {
      const cam = currentCameras.find(c => c.cam_id === camId);
      if (cam) {
        protocols[cam.ip] = protoVal;
        protocols[cam.url_address] = protoVal;
        protocols[cam.cam_id] = protoVal;
        cam.protocol = protoVal;
      }
    }
  });

  const previewFpsEl = document.getElementById("cfg-preview-fps");
  const previewFps = previewFpsEl ? parseInt(previewFpsEl.value, 10) : 4;
  const recDirEl = document.getElementById("cfg-recording-dir");
  const recDir = recDirEl ? recDirEl.value.trim() : "";

  const payload = {
    virtual_camera_name: vcamName,
    extra_ips: extraIps,
    aliases: aliases,
    protocols: protocols,
    preview_fps: previewFps,
    recording_dir: recDir
  };

  try {
    const res = await fetch("/api/config", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    if (!data.success && data.error) {
      if (errBox) {
        const textEl = document.getElementById("cfg-aliases-error-text");
        if (textEl) textEl.textContent = data.error;
        errBox.classList.remove("hidden");
      }
      return;
    }
    closeSettings();
    currentPreviewFps = previewFps;
    restartThumbPolling();
    forceRefreshUI();
    await fetchCameras();
    fetchStatus();
  } catch (err) {
    console.error("Error al guardar configuracion:", err);
    closeSettings();
  }
}

// Alias de compatibilidad
const saveSettings = saveAndCloseSettings;
