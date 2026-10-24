pub mod commands;
pub mod discovery;
pub mod models;
pub mod ndi;
pub mod pipeline;
pub mod vcam;

use commands::AppState;
use discovery::{probe_tcp_port, resolve_mac_address};
use models::{AppConfig, CameraInfo};
use ndi::NdiLib;
use pipeline::PipelineManager;
use std::sync::atomic::AtomicBool;
use std::sync::{Arc, Mutex};
use std::time::Duration;
use vcam::VirtualCameraManager;

pub fn run() {
    // 1. Load config
    let config_path = std::env::current_exe()
        .ok()
        .and_then(|p| p.parent().map(|d| d.join("config.json")))
        .unwrap_or_else(|| std::path::PathBuf::from("config.json"));

    let config: AppConfig = if config_path.exists() {
        std::fs::read_to_string(&config_path)
            .ok()
            .and_then(|s| serde_json::from_str(&s).ok())
            .unwrap_or_default()
    } else {
        AppConfig::default()
    };

    println!("======================================================");
    println!("   NDI VIRTUAL CAMERA - NATIVE TAURI BROADCAST SUITE");
    println!("   Motor nativo en Rust (sin dependencias de Python)");
    println!("======================================================");

    // 2. Initialize NDI native library
    let ndi = match NdiLib::load() {
        Ok(lib) => Arc::new(lib),
        Err(e) => {
            eprintln!("[WARN] No se pudo inicializar NDI library: {}", e);
            eprintln!("[INFO] Asegúrate de que Processing.NDI.Lib.x64.dll esté presente.");
            panic!("NDI initialization failed: {}", e);
        }
    };
    println!("[OK] NDI SDK nativo cargado exitosamente.");

    // 3. Initialize Virtual Camera Manager (UnityCapture DirectShow)
    let vcam = VirtualCameraManager::new();
    println!("[OK] Dispositivos de cámara virtual DirectShow vinculados.");

    // 4. Initialize Pipeline Manager
    let pipeline = PipelineManager::new(ndi.clone(), vcam.clone());

    // 5. Build Initial Camera List from extra_ips
    let mut initial_cams = Vec::new();
    let extra_ips = config.network.ndi_extra_ips.clone();

    for ip in &extra_ips {
        let mac = resolve_mac_address(ip);
        let clean_mac = mac.replace(':', "").to_lowercase();
        let cam_id = format!("cam-{}", clean_mac);

        let default_alias = if ip.ends_with(".108") {
            "Cám 1".to_string()
        } else if ip.ends_with(".171") {
            "Cám 2".to_string()
        } else {
            format!("Cámara {}", ip.split('.').last().unwrap_or("X"))
        };

        let alias = config
            .camera_aliases
            .get(ip)
            .cloned()
            .unwrap_or(default_alias);

        let cam = CameraInfo {
            cam_id,
            ip: ip.clone(),
            port: 5961,
            mac,
            ndi_name: "Nuroum V403".into(),
            url_address: format!("{}:5961", ip),
            alias,
            is_online: false,
            latency_ms: 0.0,
            fps: 30.0,
            resolution: "1920x1080".into(),
            is_pgm: false,
        };
        initial_cams.push(cam);
    }

    let cameras_arc = Arc::new(Mutex::new(initial_cams));
    let config_arc = Arc::new(Mutex::new(config));

    // 6. Launch streaming pipeline workers for cameras
    {
        let cams = cameras_arc.lock().unwrap();
        for (idx, cam) in cams.iter().enumerate() {
            pipeline.start_worker(idx, cam.clone());
        }
    }

    // 7. Background Discovery & Health Probe Loop
    let cams_clone = cameras_arc.clone();
    let ndi_clone = ndi.clone();
    let extra_ips_str = extra_ips.join(",");
    std::thread::Builder::new()
        .name("DiscoveryDaemon".into())
        .spawn(move || {
            let p_find = ndi_clone.create_finder(Some(&extra_ips_str));
            println!("[OK] Demonio nativo de descubrimiento NDI y sondeo de red iniciado.");

            loop {
                // Query NDI Finder sources
                let sources = ndi_clone.get_sources(p_find, 300);

                if let Ok(mut cams) = cams_clone.lock() {
                    for cam in cams.iter_mut() {
                        // Check if discovered in NDI
                        for (ndi_name, url_addr) in &sources {
                            if url_addr.contains(&cam.ip) {
                                cam.ndi_name = ndi_name.clone();
                                cam.url_address = url_addr.clone();
                            }
                        }

                        // TCP Health probe
                        if let Some(lat) = probe_tcp_port(&cam.ip, cam.port, 300) {
                            cam.is_online = true;
                            cam.latency_ms = (lat * 10.0).round() / 10.0;
                        } else if let Some(rtsp_lat) = probe_tcp_port(&cam.ip, 554, 200) {
                            cam.is_online = true;
                            cam.latency_ms = (rtsp_lat * 10.0).round() / 10.0;
                        } else {
                            cam.is_online = false;
                            cam.latency_ms = 0.0;
                        }
                    }
                }

                std::thread::sleep(Duration::from_millis(500));
            }
        })
        .expect("Failed to spawn Discovery thread");

    let app_state = AppState {
        config: config_arc,
        cameras: cameras_arc,
        pipeline,
        vcam,
        is_pinned: AtomicBool::new(false),
    };

    // 8. Launch Tauri Application
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .manage(app_state)
        .invoke_handler(tauri::generate_handler![
            commands::get_cameras,
            commands::get_status,
            commands::get_thumbnails,
            commands::save_config,
            commands::toggle_pin,
        ])
        .run(tauri::generate_context!())
        .expect("Error while running Tauri application");
}
