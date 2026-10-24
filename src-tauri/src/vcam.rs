use std::sync::{Arc, Mutex};
use windows::core::PCSTR;
use windows::Win32::Foundation::{CloseHandle, HANDLE, INVALID_HANDLE_VALUE, WAIT_ABANDONED, WAIT_OBJECT_0};
use windows::Win32::System::Memory::{
    CreateFileMappingA, MapViewOfFile, UnmapViewOfFile, FILE_MAP_ALL_ACCESS, PAGE_READWRITE,
};
use windows::Win32::System::Threading::{
    CreateEventA, CreateMutexA, ReleaseMutex, SetEvent, WaitForSingleObject,
};

// 4K Headroom: 3840 * 2160 * 4 * sizeof(short) = 66,355,200 bytes (0x3F48000)
pub const MAX_SHARED_IMAGE_SIZE: usize = 3840 * 2160 * 4 * 2;
// UnityCapture SharedMemHeader is exactly 32 bytes (8 x 32-bit fields)
pub const HEADER_SIZE: usize = 32;
pub const TOTAL_SECTION_SIZE: usize = HEADER_SIZE + MAX_SHARED_IMAGE_SIZE;

/// Exact memory layout of UnityCapture SharedMemHeader
#[repr(C)]
#[derive(Debug, Clone, Copy)]
pub struct SharedMemHeader {
    pub max_size: u32,    // Offset 0x00: MAX_SHARED_IMAGE_SIZE (0x3F48000 = 66,355,200)
    pub width: i32,       // Offset 0x04: frame width
    pub height: i32,      // Offset 0x08: frame height
    pub stride: i32,      // Offset 0x0C: row stride in pixels
    pub format: i32,      // Offset 0x10: 0 = FORMAT_UINT8
    pub resize_mode: i32, // Offset 0x14: 1 = RESIZEMODE_LINEAR
    pub mirror_mode: i32, // Offset 0x18: 0 = MIRRORMODE_DISABLED
    pub timeout: i32,     // Offset 0x1C: Keep showing last frame: i32::MAX - 200 (2_147_483_447)
}

fn get_unity_names(device_index: usize) -> (String, String, String, String) {
    if device_index == 0 {
        // Device 0 uses NULL terminator without trailing digit for backward compatibility
        (
            "UnityCapture_Mutx\0".to_string(),
            "UnityCapture_Want\0".to_string(),
            "UnityCapture_Sent\0".to_string(),
            "UnityCapture_Data\0".to_string(),
        )
    } else {
        (
            format!("UnityCapture_Mutx{}\0", device_index),
            format!("UnityCapture_Want{}\0", device_index),
            format!("UnityCapture_Sent{}\0", device_index),
            format!("UnityCapture_Data{}\0", device_index),
        )
    }
}

pub struct UnityCaptureProducer {
    pub device_index: usize,
    h_mutex: HANDLE,
    h_want_event: HANDLE,
    h_sent_event: HANDLE,
    h_map: HANDLE,
    ptr: *mut u8,
    converted_buf: Vec<u8>,
    pub frames_sent: u64,
}

unsafe impl Send for UnityCaptureProducer {}
unsafe impl Sync for UnityCaptureProducer {}

impl UnityCaptureProducer {
    pub fn new(device_index: usize, initial_width: i32, initial_height: i32) -> Result<Self, String> {
        let (mutx_name, want_name, sent_name, data_name) = get_unity_names(device_index);

        unsafe {
            // 1. Mutex (CreateMutexA safely creates or opens existing named mutex)
            let h_mutex = CreateMutexA(None, false, PCSTR(mutx_name.as_ptr()))
                .map_err(|e| format!("CreateMutexA failed for {}: {}", mutx_name, e))?;

            // 2. Want Event (Signaled by DirectShow receiver when ready for next frame)
            let h_want_event = CreateEventA(None, false, false, PCSTR(want_name.as_ptr()))
                .map_err(|e| format!("CreateEventA failed for {}: {}", want_name, e))?;

            // 3. Sent Event (Signaled by producer when frame is written)
            let h_sent_event = CreateEventA(None, false, false, PCSTR(sent_name.as_ptr()))
                .map_err(|e| format!("CreateEventA failed for {}: {}", sent_name, e))?;

            // 4. File Mapping (CreateFileMappingA safely creates or opens existing named mapping)
            let total_size = TOTAL_SECTION_SIZE;
            let h_map = CreateFileMappingA(
                INVALID_HANDLE_VALUE,
                None,
                PAGE_READWRITE,
                0,
                total_size as u32,
                PCSTR(data_name.as_ptr()),
            )
            .map_err(|e| format!("CreateFileMappingA failed for {}: {}", data_name, e))?;

            // 5. Map view of file
            let view = MapViewOfFile(h_map, FILE_MAP_ALL_ACCESS, 0, 0, total_size);
            if view.Value.is_null() {
                let _ = CloseHandle(h_map);
                let _ = CloseHandle(h_sent_event);
                let _ = CloseHandle(h_want_event);
                let _ = CloseHandle(h_mutex);
                return Err(format!("MapViewOfFile failed for {}", data_name));
            }
            let ptr = view.Value as *mut u8;

            // 6. Initialize Header
            let header = SharedMemHeader {
                max_size: MAX_SHARED_IMAGE_SIZE as u32,
                width: initial_width,
                height: initial_height,
                stride: initial_width,
                format: 0, // FORMAT_UINT8
                resize_mode: 1, // RESIZEMODE_LINEAR
                mirror_mode: 0, // MIRRORMODE_DISABLED
                timeout: 2_147_483_447, // i32::MAX - 200
            };
            std::ptr::copy_nonoverlapping(
                &header as *const _ as *const u8,
                ptr,
                HEADER_SIZE,
            );

            let initial_buf_size = (initial_width * initial_height * 4) as usize;

            Ok(Self {
                device_index,
                h_mutex,
                h_want_event,
                h_sent_event,
                h_map,
                ptr,
                converted_buf: vec![0u8; initial_buf_size],
                frames_sent: 0,
            })
        }
    }

    /// Sends a video frame from NDI (BGRX / BGRA) to the UnityCapture DirectShow Filter
    pub fn send_frame(&mut self, width: i32, height: i32, stride_in_bytes: usize, bgrx_data: &[u8]) {
        if self.ptr.is_null() || width <= 0 || height <= 0 {
            return;
        }

        let w = width as usize;
        let h = height as usize;
        let expected_len = w * h * 4;

        if self.converted_buf.len() != expected_len {
            self.converted_buf.resize(expected_len, 255);
        }

        // Fast conversion: NDI BGRX/BGRA -> UnityCapture RGBA with vertical flip
        for y in 0..h {
            let src_row = y * stride_in_bytes;
            let dst_row = (h - 1 - y) * (w * 4);
            if src_row + w * 4 <= bgrx_data.len() {
                let src_slice = &bgrx_data[src_row..src_row + w * 4];
                let dst_slice = &mut self.converted_buf[dst_row..dst_row + w * 4];
                for x in 0..w {
                    let sx = x * 4;
                    let b = src_slice[sx];
                    let g = src_slice[sx + 1];
                    let r = src_slice[sx + 2];
                    dst_slice[sx] = r;
                    dst_slice[sx + 1] = g;
                    dst_slice[sx + 2] = b;
                    dst_slice[sx + 3] = 255;
                }
            }
        }

        unsafe {
            // Lock mutex (with 40ms timeout to never stall video pipeline if receiver is busy)
            let wait = WaitForSingleObject(self.h_mutex, 40);
            if wait == WAIT_OBJECT_0 || wait == WAIT_ABANDONED {
                // Update Header
                let header = SharedMemHeader {
                    max_size: MAX_SHARED_IMAGE_SIZE as u32,
                    width,
                    height,
                    stride: width,
                    format: 0, // FORMAT_UINT8
                    resize_mode: 1, // RESIZEMODE_LINEAR
                    mirror_mode: 0, // MIRRORMODE_DISABLED
                    timeout: 2_147_483_447, // i32::MAX - 200
                };
                std::ptr::copy_nonoverlapping(
                    &header as *const _ as *const u8,
                    self.ptr,
                    HEADER_SIZE,
                );

                // Copy pixel payload starting at offset 0x20 (byte 32)
                let pixel_dest = self.ptr.add(HEADER_SIZE);
                std::ptr::copy_nonoverlapping(
                    self.converted_buf.as_ptr(),
                    pixel_dest,
                    expected_len.min(MAX_SHARED_IMAGE_SIZE),
                );

                // Release mutex
                let _ = ReleaseMutex(self.h_mutex);

                // Signal receiver that a new frame is ready
                let _ = SetEvent(self.h_sent_event);
            }
        }

        self.frames_sent += 1;
    }
}

impl Drop for UnityCaptureProducer {
    fn drop(&mut self) {
        unsafe {
            if !self.ptr.is_null() {
                let _ = UnmapViewOfFile(windows::Win32::System::Memory::MEMORY_MAPPED_VIEW_ADDRESS {
                    Value: self.ptr as *mut _,
                });
            }
            if !self.h_map.is_invalid() {
                let _ = CloseHandle(self.h_map);
            }
            if !self.h_sent_event.is_invalid() {
                let _ = CloseHandle(self.h_sent_event);
            }
            if !self.h_want_event.is_invalid() {
                let _ = CloseHandle(self.h_want_event);
            }
            if !self.h_mutex.is_invalid() {
                let _ = CloseHandle(self.h_mutex);
            }
        }
    }
}

#[derive(Clone)]
pub struct VirtualCameraManager {
    devices: Arc<Mutex<Vec<UnityCaptureProducer>>>,
}

impl VirtualCameraManager {
    pub fn new() -> Self {
        let mut list = Vec::new();
        // Initialize virtual camera channels 0 and 1
        match UnityCaptureProducer::new(0, 1920, 1080) {
            Ok(dev0) => {
                println!("[OK] Cámara Virtual Canal 0 vinculada a DirectShow (UnityCapture Device #1).");
                list.push(dev0);
            }
            Err(e) => eprintln!("[WARN] No se pudo vincular Canal 0 a DirectShow: {}", e),
        }
        match UnityCaptureProducer::new(1, 1920, 1080) {
            Ok(dev1) => {
                println!("[OK] Cámara Virtual Canal 1 vinculada a DirectShow (UnityCapture Device #2).");
                list.push(dev1);
            }
            Err(e) => eprintln!("[WARN] No se pudo vincular Canal 1 a DirectShow: {}", e),
        }
        Self {
            devices: Arc::new(Mutex::new(list)),
        }
    }

    pub fn push_frame(&self, device_index: usize, width: i32, height: i32, stride: usize, data: &[u8]) {
        if let Ok(mut devs) = self.devices.lock() {
            if device_index < devs.len() {
                devs[device_index].send_frame(width, height, stride, data);
            }
        }
    }

    pub fn get_frames_sent(&self, device_index: usize) -> u64 {
        if let Ok(devs) = self.devices.lock() {
            if device_index < devs.len() {
                return devs[device_index].frames_sent;
            }
        }
        0
    }
}
