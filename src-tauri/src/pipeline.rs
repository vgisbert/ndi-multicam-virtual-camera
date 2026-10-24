use crate::models::CameraInfo;
use crate::ndi::{NdiLib, NDILIB_FRAME_TYPE_VIDEO};
use crate::vcam::VirtualCameraManager;
use base64::engine::general_purpose::STANDARD as BASE64;
use base64::Engine;
use image::{ImageBuffer, Rgb};
use std::collections::HashMap;
use std::io::Cursor;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, Mutex};
use std::time::{Duration, Instant};

#[derive(Clone)]
pub struct PipelineManager {
    ndi: Arc<NdiLib>,
    vcam: VirtualCameraManager,
    pub thumbnails: Arc<Mutex<HashMap<String, String>>>,
    pub live_fps: Arc<Mutex<HashMap<String, f32>>>,
    pub live_res: Arc<Mutex<HashMap<String, String>>>,
    running: Arc<AtomicBool>,
}

impl PipelineManager {
    pub fn new(ndi: Arc<NdiLib>, vcam: VirtualCameraManager) -> Self {
        Self {
            ndi,
            vcam,
            thumbnails: Arc::new(Mutex::new(HashMap::new())),
            live_fps: Arc::new(Mutex::new(HashMap::new())),
            live_res: Arc::new(Mutex::new(HashMap::new())),
            running: Arc::new(AtomicBool::new(true)),
        }
    }

    pub fn start_worker(&self, device_index: usize, cam: CameraInfo) {
        let ndi = self.ndi.clone();
        let vcam = self.vcam.clone();
        let thumbnails = self.thumbnails.clone();
        let live_fps = self.live_fps.clone();
        let live_res = self.live_res.clone();
        let running = self.running.clone();

        std::thread::Builder::new()
            .name(format!("NDIWorker-{}", cam.ip))
            .spawn(move || {
                let recv_name = format!("NDI Ingest {}", cam.ip);
                let p_recv = ndi.create_receiver(&cam.ndi_name, &cam.url_address, &recv_name);
                if p_recv.is_null() {
                    eprintln!("[ERROR] Could not create NDI receiver for {}", cam.url_address);
                    return;
                }
                println!("[OK] Canal NDI nativo activo para: {} ({})", cam.alias, cam.url_address);

                let mut last_thumb_time = Instant::now();
                let mut frame_count = 0u32;
                let mut fps_timer = Instant::now();

                while running.load(Ordering::Relaxed) {
                    let mut frame = crate::ndi::NDIlib_video_frame_v2_t::default();
                    let res = ndi.capture_frame(p_recv, &mut frame, 35);

                    if res == NDILIB_FRAME_TYPE_VIDEO && !frame.p_data.is_null() {
                        let w = frame.xres;
                        let h = frame.yres;
                        let stride = frame.line_stride_in_bytes as usize;
                        let total_bytes = stride * (h as usize);

                        let raw_slice = unsafe { std::slice::from_raw_parts(frame.p_data, total_bytes) };

                        // 1. Push to Virtual Camera (UnityCapture 0 or 1)
                        vcam.push_frame(device_index, w, h, stride, raw_slice);

                        // FPS Calculation
                        frame_count += 1;
                        if fps_timer.elapsed() >= Duration::from_millis(1000) {
                            let measured = (frame_count as f32) / fps_timer.elapsed().as_secs_f32();
                            if let Ok(mut fps_map) = live_fps.lock() {
                                fps_map.insert(cam.cam_id.clone(), (measured * 10.0).round() / 10.0);
                            }
                            frame_count = 0;
                            fps_timer = Instant::now();
                        }

                        // Resolution tracking
                        if let Ok(mut res_map) = live_res.lock() {
                            res_map.insert(cam.cam_id.clone(), format!("{}x{}", w, h));
                        }

                        // 2. Generate UI Thumbnail at ~10 fps
                        if last_thumb_time.elapsed() >= Duration::from_millis(100) {
                            last_thumb_time = Instant::now();

                            let target_w = 280u32;
                            let target_h = 158u32;

                            // Fast downsampling from BGRX to RGB
                            let mut thumb_buf: ImageBuffer<Rgb<u8>, Vec<u8>> =
                                ImageBuffer::new(target_w, target_h);

                            let scale_x = (w as f32) / (target_w as f32);
                            let scale_y = (h as f32) / (target_h as f32);

                            for ty in 0..target_h {
                                let sy = ((ty as f32 * scale_y) as usize).min((h - 1) as usize);
                                let row_offset = sy * stride;
                                for tx in 0..target_w {
                                    let sx = ((tx as f32 * scale_x) as usize).min((w - 1) as usize);
                                    let pixel_offset = row_offset + sx * 4;
                                    if pixel_offset + 3 <= raw_slice.len() {
                                        let b = raw_slice[pixel_offset];
                                        let g = raw_slice[pixel_offset + 1];
                                        let r = raw_slice[pixel_offset + 2];
                                        thumb_buf.put_pixel(tx, ty, Rgb([r, g, b]));
                                    }
                                }
                            }

                            // Encode JPEG to Base64 in memory
                            let mut jpeg_bytes = Vec::new();
                            let mut cursor = Cursor::new(&mut jpeg_bytes);
                            if thumb_buf.write_to(&mut cursor, image::ImageFormat::Jpeg).is_ok() {
                                let b64 = BASE64.encode(&jpeg_bytes);
                                let data_url = format!("data:image/jpeg;base64,{}", b64);
                                if let Ok(mut thumbs) = thumbnails.lock() {
                                    thumbs.insert(cam.cam_id.clone(), data_url);
                                }
                            }
                        }

                        ndi.free_video_frame(p_recv, &mut frame);
                    } else {
                        std::thread::sleep(Duration::from_millis(5));
                    }
                }

                ndi.destroy_receiver(p_recv);
            })
            .expect("Failed to spawn camera stream worker thread");
    }

    pub fn stop(&self) {
        self.running.store(false, Ordering::Relaxed);
    }
}
