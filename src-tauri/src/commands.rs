use crate::models::{AppConfig, CameraInfo, StatusResponse, VcamDeviceInfo, VcamStatus};
use crate::pipeline::PipelineManager;
use crate::vcam::VirtualCameraManager;
use std::collections::HashMap;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, Mutex};
use tauri::State;

pub struct AppState {
    pub config: Arc<Mutex<AppConfig>>,
    pub cameras: Arc<Mutex<Vec<CameraInfo>>>,
    pub pipeline: PipelineManager,
    pub vcam: VirtualCameraManager,
    pub is_pinned: AtomicBool,
}

#[tauri::command]
pub fn get_cameras(state: State<'_, AppState>) -> Vec<CameraInfo> {
    let mut cams = state.cameras.lock().unwrap_or_else(|e| e.into_inner()).clone();
    let live_fps = state.pipeline.live_fps.lock().unwrap_or_else(|e| e.into_inner());
    let live_res = state.pipeline.live_res.lock().unwrap_or_else(|e| e.into_inner());

    for cam in &mut cams {
        if let Some(&fps) = live_fps.get(&cam.cam_id) {
            cam.fps = fps;
        }
        if let Some(res) = live_res.get(&cam.cam_id) {
            cam.resolution = res.clone();
        }
    }
    cams
}

#[tauri::command]
pub fn get_status(state: State<'_, AppState>) -> StatusResponse {
    let cams = state.cameras.lock().unwrap_or_else(|e| e.into_inner());
    let frames0 = state.vcam.get_frames_sent(0);
    let frames1 = state.vcam.get_frames_sent(1);

    let dev0_label = cams.get(0).map_or("Cám 1 (192.168.9.108)".into(), |c| format!("{} ({})", c.alias, c.ip));
    let dev1_label = cams.get(1).map_or("Cám 2 (192.168.9.171)".into(), |c| format!("{} ({})", c.alias, c.ip));

    let dev0 = VcamDeviceInfo {
        channel_id: cams.get(0).map_or("cam-1".into(), |c| c.cam_id.clone()),
        label: dev0_label.clone(),
        device: "Unity Video Capture".into(),
        is_active: true,
        fps: 30.0,
        frames_sent: frames0,
    };

    let dev1 = VcamDeviceInfo {
        channel_id: cams.get(1).map_or("cam-2".into(), |c| c.cam_id.clone()),
        label: dev1_label.clone(),
        device: "Unity Video Capture #2".into(),
        is_active: true,
        fps: 30.0,
        frames_sent: frames1,
    };

    let vcam = VcamStatus {
        is_active: true,
        active_devices_count: 2,
        device: "Multicam (2 dispositivos activos)".into(),
        resolution: "1920x1080".into(),
        fps: 30.0,
        source_label: dev0_label,
        devices: vec![dev0, dev1],
    };

    StatusResponse {
        status: "nominal".into(),
        vcam,
        is_pinned: state.is_pinned.load(Ordering::Relaxed),
    }
}

#[tauri::command]
pub fn get_thumbnails(state: State<'_, AppState>) -> HashMap<String, String> {
    state.pipeline.thumbnails.lock().unwrap_or_else(|e| e.into_inner()).clone()
}

#[tauri::command]
pub fn save_config(state: State<'_, AppState>, new_config: AppConfig) -> Result<(), String> {
    if let Ok(mut cfg) = state.config.lock() {
        *cfg = new_config.clone();
    }
    // Save to config.json next to executable or working dir
    let json = serde_json::to_string_pretty(&new_config).map_err(|e| e.to_string())?;
    let config_path = std::env::current_exe()
        .ok()
        .and_then(|p| p.parent().map(|d| d.join("config.json")))
        .unwrap_or_else(|| std::path::PathBuf::from("config.json"));

    std::fs::write(&config_path, json).map_err(|e| e.to_string())?;
    Ok(())
}

#[tauri::command]
pub fn toggle_pin(window: tauri::Window, state: State<'_, AppState>) -> Result<bool, String> {
    let current = state.is_pinned.load(Ordering::Relaxed);
    let next = !current;
    window.set_always_on_top(next).map_err(|e| e.to_string())?;
    state.is_pinned.store(next, Ordering::Relaxed);
    Ok(next)
}
