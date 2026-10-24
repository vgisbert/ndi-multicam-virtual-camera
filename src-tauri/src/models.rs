use serde::{Deserialize, Serialize};
use std::collections::HashMap;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CameraInfo {
    pub cam_id: String,
    pub ip: String,
    pub port: u16,
    pub mac: String,
    pub ndi_name: String,
    pub url_address: String,
    pub alias: String,
    pub is_online: bool,
    pub latency_ms: f32,
    pub fps: f32,
    pub resolution: String,
    pub is_pgm: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct VcamDeviceInfo {
    pub channel_id: String,
    pub label: String,
    pub device: String,
    pub is_active: bool,
    pub fps: f32,
    pub frames_sent: u64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct VcamStatus {
    pub is_active: bool,
    pub active_devices_count: usize,
    pub device: String,
    pub resolution: String,
    pub fps: f32,
    pub source_label: String,
    pub devices: Vec<VcamDeviceInfo>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct StatusResponse {
    pub status: String,
    pub vcam: VcamStatus,
    pub is_pinned: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct NetworkConfig {
    pub ndi_extra_ips: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ResolutionConfig {
    pub width: i32,
    pub height: i32,
    pub fps: i32,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AppConfig {
    pub virtual_camera_name: String,
    pub selected_source: String,
    pub auto_start_virtual_cam: bool,
    pub resolution: ResolutionConfig,
    pub camera_aliases: HashMap<String, String>,
    pub network: NetworkConfig,
}

impl Default for AppConfig {
    fn default() -> Self {
        Self {
            virtual_camera_name: "NDI Virtual Camera".into(),
            selected_source: "".into(),
            auto_start_virtual_cam: true,
            resolution: ResolutionConfig {
                width: 1920,
                height: 1080,
                fps: 30,
            },
            camera_aliases: HashMap::new(),
            network: NetworkConfig {
                ndi_extra_ips: vec!["192.168.9.108".into(), "192.168.9.171".into()],
            },
        }
    }
}
