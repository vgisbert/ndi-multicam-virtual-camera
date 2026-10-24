use libloading::{Library, Symbol};
use std::ffi::{c_char, c_void, CStr, CString};
use std::path::{Path, PathBuf};
use std::sync::Arc;

pub const NDILIB_RECV_COLOR_FORMAT_BGRX_BGRA: i32 = 0;
pub const NDILIB_RECV_BANDWIDTH_HIGHEST: i32 = 100;
pub const NDILIB_FRAME_TYPE_NONE: i32 = 0;
pub const NDILIB_FRAME_TYPE_VIDEO: i32 = 1;

#[repr(C)]
#[derive(Debug, Clone, Copy)]
pub struct NDIlib_source_t {
    pub p_ndi_name: *const c_char,
    pub p_url_address: *const c_char,
}

impl Default for NDIlib_source_t {
    fn default() -> Self {
        Self {
            p_ndi_name: std::ptr::null(),
            p_url_address: std::ptr::null(),
        }
    }
}

#[repr(C)]
#[derive(Debug, Clone, Copy)]
pub struct NDIlib_video_frame_v2_t {
    pub xres: i32,
    pub yres: i32,
    pub fourcc: i32,
    pub frame_rate_n: i32,
    pub frame_rate_d: i32,
    pub picture_aspect_ratio: f32,
    pub frame_format_type: i32,
    pub timecode: i64,
    pub p_data: *mut u8,
    pub line_stride_in_bytes: i32,
    pub p_metadata: *const c_char,
    pub timestamp: i64,
}

impl Default for NDIlib_video_frame_v2_t {
    fn default() -> Self {
        Self {
            xres: 0,
            yres: 0,
            fourcc: 0,
            frame_rate_n: 0,
            frame_rate_d: 0,
            picture_aspect_ratio: 0.0,
            frame_format_type: 0,
            timecode: 0,
            p_data: std::ptr::null_mut(),
            line_stride_in_bytes: 0,
            p_metadata: std::ptr::null(),
            timestamp: 0,
        }
    }
}

#[repr(C)]
#[derive(Debug, Clone, Copy)]
pub struct NDIlib_recv_create_v3_t {
    pub source_to_connect_to: NDIlib_source_t,
    pub color_format: i32,
    pub bandwidth: i32,
    pub allow_video_fields: bool,
    pub p_ndi_recv_name: *const c_char,
}

#[repr(C)]
#[derive(Debug, Clone, Copy)]
pub struct NDIlib_find_create_t {
    pub show_local_sources: bool,
    pub p_groups: *const c_char,
    pub p_extra_ips: *const c_char,
}

type NDIlib_initialize_fn = unsafe extern "C" fn() -> bool;
type NDIlib_destroy_fn = unsafe extern "C" fn();
type NDIlib_version_fn = unsafe extern "C" fn() -> *const c_char;

type NDIlib_find_create_v2_fn = unsafe extern "C" fn(*const NDIlib_find_create_t) -> *mut c_void;
type NDIlib_find_destroy_fn = unsafe extern "C" fn(*mut c_void);
type NDIlib_find_wait_for_sources_fn = unsafe extern "C" fn(*mut c_void, u32) -> bool;
type NDIlib_find_get_current_sources_fn = unsafe extern "C" fn(*mut c_void, *mut u32) -> *const NDIlib_source_t;

type NDIlib_recv_create_v3_fn = unsafe extern "C" fn(*const NDIlib_recv_create_v3_t) -> *mut c_void;
type NDIlib_recv_destroy_fn = unsafe extern "C" fn(*mut c_void);
type NDIlib_recv_capture_v2_fn = unsafe extern "C" fn(*mut c_void, *mut NDIlib_video_frame_v2_t, *mut c_void, *mut c_void, u32) -> i32;
type NDIlib_recv_free_video_v2_fn = unsafe extern "C" fn(*mut c_void, *mut NDIlib_video_frame_v2_t);

pub struct NdiLib {
    _lib: Arc<Library>,
    fn_destroy: NDIlib_destroy_fn,
    fn_find_create_v2: NDIlib_find_create_v2_fn,
    fn_find_destroy: NDIlib_find_destroy_fn,
    fn_find_wait_for_sources: NDIlib_find_wait_for_sources_fn,
    fn_find_get_current_sources: NDIlib_find_get_current_sources_fn,
    fn_recv_create_v3: NDIlib_recv_create_v3_fn,
    fn_recv_destroy: NDIlib_recv_destroy_fn,
    fn_recv_capture_v2: NDIlib_recv_capture_v2_fn,
    fn_recv_free_video_v2: NDIlib_recv_free_video_v2_fn,
}

unsafe impl Send for NdiLib {}
unsafe impl Sync for NdiLib {}

impl NdiLib {
    pub fn load() -> Result<Self, String> {
        let candidate_paths = vec![
            PathBuf::from("Processing.NDI.Lib.x64.dll"),
            PathBuf::from("core/lib/Processing.NDI.Lib.x64.dll"),
            PathBuf::from("../core/lib/Processing.NDI.Lib.x64.dll"),
            PathBuf::from("C:\\Program Files\\NDI\\NDI 6 Runtime\\v6\\Processing.NDI.Lib.x64.dll"),
            PathBuf::from("C:\\Program Files\\NDI\\NDI 5 Runtime\\v5\\Processing.NDI.Lib.x64.dll"),
        ];

        let mut loaded_lib: Option<Library> = None;
        for path in candidate_paths {
            if path.exists() {
                if let Ok(lib) = unsafe { Library::new(&path) } {
                    loaded_lib = Some(lib);
                    break;
                }
            }
        }

        let lib = match loaded_lib {
            Some(l) => Arc::new(l),
            None => {
                // Try system search
                unsafe { Library::new("Processing.NDI.Lib.x64.dll") }
                    .map(Arc::new)
                    .map_err(|e| format!("Could not load Processing.NDI.Lib.x64.dll: {}", e))?
            }
        };

        unsafe {
            let fn_init: NDIlib_initialize_fn = *lib
                .get(b"NDIlib_initialize\0")
                .map_err(|e| format!("Symbol NDIlib_initialize missing: {}", e))?;
            if !fn_init() {
                return Err("NDIlib_initialize returned false".into());
            }

            let fn_destroy: NDIlib_destroy_fn = *lib
                .get(b"NDIlib_destroy\0")
                .map_err(|e| format!("Symbol NDIlib_destroy missing: {}", e))?;
            let fn_find_create_v2: NDIlib_find_create_v2_fn = *lib
                .get(b"NDIlib_find_create_v2\0")
                .map_err(|e| format!("Symbol NDIlib_find_create_v2 missing: {}", e))?;
            let fn_find_destroy: NDIlib_find_destroy_fn = *lib
                .get(b"NDIlib_find_destroy\0")
                .map_err(|e| format!("Symbol NDIlib_find_destroy missing: {}", e))?;
            let fn_find_wait_for_sources: NDIlib_find_wait_for_sources_fn = *lib
                .get(b"NDIlib_find_wait_for_sources\0")
                .map_err(|e| format!("Symbol NDIlib_find_wait_for_sources missing: {}", e))?;
            let fn_find_get_current_sources: NDIlib_find_get_current_sources_fn = *lib
                .get(b"NDIlib_find_get_current_sources\0")
                .map_err(|e| format!("Symbol NDIlib_find_get_current_sources missing: {}", e))?;

            let fn_recv_create_v3: NDIlib_recv_create_v3_fn = *lib
                .get(b"NDIlib_recv_create_v3\0")
                .map_err(|e| format!("Symbol NDIlib_recv_create_v3 missing: {}", e))?;
            let fn_recv_destroy: NDIlib_recv_destroy_fn = *lib
                .get(b"NDIlib_recv_destroy\0")
                .map_err(|e| format!("Symbol NDIlib_recv_destroy missing: {}", e))?;
            let fn_recv_capture_v2: NDIlib_recv_capture_v2_fn = *lib
                .get(b"NDIlib_recv_capture_v2\0")
                .map_err(|e| format!("Symbol NDIlib_recv_capture_v2 missing: {}", e))?;
            let fn_recv_free_video_v2: NDIlib_recv_free_video_v2_fn = *lib
                .get(b"NDIlib_recv_free_video_v2\0")
                .map_err(|e| format!("Symbol NDIlib_recv_free_video_v2 missing: {}", e))?;

            Ok(Self {
                _lib: lib,
                fn_destroy,
                fn_find_create_v2,
                fn_find_destroy,
                fn_find_wait_for_sources,
                fn_find_get_current_sources,
                fn_recv_create_v3,
                fn_recv_destroy,
                fn_recv_capture_v2,
                fn_recv_free_video_v2,
            })
        }
    }

    pub fn create_finder(&self, extra_ips: Option<&str>) -> *mut c_void {
        let c_extra = extra_ips.and_then(|s| CString::new(s).ok());
        let desc = NDIlib_find_create_t {
            show_local_sources: true,
            p_groups: std::ptr::null(),
            p_extra_ips: c_extra.as_ref().map_or(std::ptr::null(), |c| c.as_ptr()),
        };
        unsafe { (self.fn_find_create_v2)(&desc) }
    }

    pub fn destroy_finder(&self, p_find: *mut c_void) {
        if !p_find.is_null() {
            unsafe { (self.fn_find_destroy)(p_find) };
        }
    }

    pub fn get_sources(&self, p_find: *mut c_void, wait_ms: u32) -> Vec<(String, String)> {
        if p_find.is_null() {
            return Vec::new();
        }
        unsafe {
            (self.fn_find_wait_for_sources)(p_find, wait_ms);
            let mut num_sources: u32 = 0;
            let p_sources = (self.fn_find_get_current_sources)(p_find, &mut num_sources);
            let mut res = Vec::new();
            if num_sources > 0 && !p_sources.is_null() {
                for i in 0..num_sources {
                    let src = *p_sources.add(i as usize);
                    let name = if !src.p_ndi_name.is_null() {
                        CStr::from_ptr(src.p_ndi_name).to_string_lossy().to_string()
                    } else {
                        "".into()
                    };
                    let url = if !src.p_url_address.is_null() {
                        CStr::from_ptr(src.p_url_address).to_string_lossy().to_string()
                    } else {
                        "".into()
                    };
                    res.push((name, url));
                }
            }
            res
        }
    }

    pub fn create_receiver(&self, ndi_name: &str, url_address: &str, recv_name: &str) -> *mut c_void {
        let c_name = CString::new(ndi_name).unwrap_or_default();
        let c_url = CString::new(url_address).unwrap_or_default();
        let c_recv = CString::new(recv_name).unwrap_or_default();

        let desc = NDIlib_recv_create_v3_t {
            source_to_connect_to: NDIlib_source_t {
                p_ndi_name: if !ndi_name.is_empty() { c_name.as_ptr() } else { std::ptr::null() },
                p_url_address: if !url_address.is_empty() { c_url.as_ptr() } else { std::ptr::null() },
            },
            color_format: NDILIB_RECV_COLOR_FORMAT_BGRX_BGRA,
            bandwidth: NDILIB_RECV_BANDWIDTH_HIGHEST,
            allow_video_fields: false,
            p_ndi_recv_name: c_recv.as_ptr(),
        };

        unsafe { (self.fn_recv_create_v3)(&desc) }
    }

    pub fn destroy_receiver(&self, p_recv: *mut c_void) {
        if !p_recv.is_null() {
            unsafe { (self.fn_recv_destroy)(p_recv) };
        }
    }

    pub fn capture_frame(&self, p_recv: *mut c_void, frame: &mut NDIlib_video_frame_v2_t, timeout_ms: u32) -> i32 {
        if p_recv.is_null() {
            return NDILIB_FRAME_TYPE_NONE;
        }
        unsafe {
            (self.fn_recv_capture_v2)(p_recv, frame, std::ptr::null_mut(), std::ptr::null_mut(), timeout_ms)
        }
    }

    pub fn free_video_frame(&self, p_recv: *mut c_void, frame: &mut NDIlib_video_frame_v2_t) {
        if !p_recv.is_null() && !frame.p_data.is_null() {
            unsafe { (self.fn_recv_free_video_v2)(p_recv, frame) };
        }
    }
}

impl Drop for NdiLib {
    fn drop(&mut self) {
        unsafe {
            (self.fn_destroy)();
        }
    }
}
