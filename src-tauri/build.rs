fn main() {
    let mut windows = tauri_build::WindowsAttributes::new();
    let temp_ico = std::path::PathBuf::from(r"C:\Users\super\.cargo\vcam_icon.ico");
    if std::path::Path::new("icons/icon.ico").exists() {
        let _ = std::fs::copy("icons/icon.ico", &temp_ico);
        windows = windows.window_icon_path(&temp_ico);
    }

    let attrs = tauri_build::Attributes::new().windows_attributes(windows);
    tauri_build::try_build(attrs).expect("failed to run tauri-build");
}
