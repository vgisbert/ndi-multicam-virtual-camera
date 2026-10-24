/**
 * NDI Virtual Camera — Frontend Client Logic
 * Tactical Broadcast Console
 */

let isPinned = false;
let currentCameras = [];
let currentStatus = {};
let pollingInterval = null;

// Initialize on page load
document.addEventListener("DOMContentLoaded", () => {
  applyI18n();
  fetchStatus();
  fetchCameras();
  fetchThumbnails();

  // Fast polling for status, cameras, and miniature thumbnails
  pollingInterval = setInterval(() => {
    fetchStatus();
    fetchCameras();
    fetchThumbnails();
  }, 400);
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

function renderCameras(cameras) {
  const container = document.getElementById("cameras-container");
  if (!container) return;

  if (!cameras || cameras.length === 0) {
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
  if (existingCards.length !== cameras.length) {
    container.innerHTML = "";
    cameras.forEach(cam => {
      const card = createCameraCardElement(cam);
      container.appendChild(card);
    });
  } else {
    cameras.forEach(cam => {
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
      <div class="flex items-center gap-1">
        <span class="badge-tally px-1.5 py-0.2 rounded font-bold text-[8.5px] uppercase tracking-wider"></span>
        <span class="cam-alias font-sans font-bold text-[11px] text-txt-main truncate max-w-[150px]"></span>
      </div>
      <div class="text-[9px] text-txt-muted flex items-center gap-1 font-mono">
        <span class="cam-fps text-amber-tac font-bold"></span>
        <span class="cam-res text-txt-muted/80"></span>
      </div>
    </div>

    <!-- PREVISUALIZACIÓN MINIATURA (ASPECT RATIO 16:9) -->
    <div class="relative w-full aspect-video bg-surface-lowest rounded overflow-hidden border border-border-tac/30 flex items-center justify-center">
      <img id="thumb-${cam.cam_id}" class="w-full h-full object-cover thumb-fade" src="" alt="Live Preview" style="display: none;">
      
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
  const aliasEl = card.querySelector(".cam-alias");
  const fpsEl = card.querySelector(".cam-fps");
  const resEl = card.querySelector(".cam-res");
  const ipEl = card.querySelector(".cam-ip");
  const macEl = card.querySelector(".cam-mac");
  const rttEl = card.querySelector(".cam-rtt");
  const statusDot = card.querySelector(".status-dot");
  const offlineOverlay = card.querySelector(`#thumb-offline-${cam.cam_id}`);

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
  if (!thumbs) return;
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
function openSettings() {
  const modal = document.getElementById("modal-settings");
  if (!modal) return;
  modal.classList.remove("hidden");

  // Populate fields
  fetch("/api/config").then(r => r.json()).then(cfg => {
    document.getElementById("cfg-vcam-name").value = cfg.virtual_camera_name || "NDI Virtual Camera";
    const extraIps = (cfg.network && cfg.network.ndi_extra_ips) ? cfg.network.ndi_extra_ips.join(", ") : "";
    document.getElementById("cfg-extra-ips").value = extraIps;

    const aliasesBox = document.getElementById("cfg-aliases-container");
    aliasesBox.innerHTML = "";
    currentCameras.forEach(cam => {
      const row = document.createElement("div");
      row.className = "flex items-center gap-1.5";
      const displayVal = getLocalizedAlias(cam);
      row.innerHTML = `
        <span class="text-[9px] text-txt-muted w-24 truncate">${cam.ip}:</span>
        <input type="text" data-cam-id="${cam.cam_id}" value="${displayVal}" class="alias-input flex-1 bg-surface-lowest border border-border-tac rounded px-2 py-0.5 text-txt-main text-[9.5px] outline-none focus:border-cyan-tac">
      `;
      aliasesBox.appendChild(row);
    });
  });
}

function closeSettings() {
  const modal = document.getElementById("modal-settings");
  if (modal) modal.classList.add("hidden");
}

async function saveSettings() {
  const vcamName = document.getElementById("cfg-vcam-name").value.trim();
  const rawIps = document.getElementById("cfg-extra-ips").value;
  const extraIps = rawIps.split(",").map(s => s.trim()).filter(s => s.length > 0);

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

  const payload = {
    virtual_camera_name: vcamName,
    extra_ips: extraIps,
    aliases: aliases
  };

  try {
    await fetch("/api/config", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    closeSettings();
    forceRefreshUI();
    await fetchCameras();
    fetchStatus();
  } catch (err) {
    console.error("Error al guardar configuracion:", err);
  }
}
