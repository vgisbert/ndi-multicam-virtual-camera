use std::net::{SocketAddr, TcpStream};
use std::time::{Duration, Instant};
use windows::Win32::NetworkManagement::IpHelper::SendARP;

pub fn resolve_mac_address(ip_str: &str) -> String {
    if let Ok(ip) = ip_str.parse::<std::net::Ipv4Addr>() {
        let octets = ip.octets();
        let dest_ip = u32::from_be_bytes(octets);

        let mut mac: [u8; 6] = [0; 6];
        let mut mac_len: u32 = 6;

        unsafe {
            let res = SendARP(dest_ip, 0, mac.as_mut_ptr() as *mut _, &mut mac_len);
            if res == 0 {
                return format!(
                    "{:02X}:{:02X}:{:02X}:{:02X}:{:02X}:{:02X}",
                    mac[0], mac[1], mac[2], mac[3], mac[4], mac[5]
                );
            }
        }
    }

    // Synthetic fallback based on IP
    let parts: Vec<&str> = ip_str.split('.').collect();
    if parts.len() == 4 {
        let o0 = parts[0].parse::<u8>().unwrap_or(192);
        let o1 = parts[1].parse::<u8>().unwrap_or(168);
        let o2 = parts[2].parse::<u8>().unwrap_or(9);
        let o3 = parts[3].parse::<u8>().unwrap_or(1);
        return format!("02:00:{:02X}:{:02X}:{:02X}:{:02X}", o0, o1, o2, o3);
    }
    "02:00:00:00:00:01".into()
}

pub fn probe_tcp_port(ip: &str, port: u16, timeout_ms: u64) -> Option<f32> {
    let addr_str = format!("{}:{}", ip, port);
    if let Ok(addr) = addr_str.parse::<SocketAddr>() {
        let t0 = Instant::now();
        if let Ok(_stream) = TcpStream::connect_timeout(&addr, Duration::from_millis(timeout_ms)) {
            let elapsed = t0.elapsed().as_secs_f32() * 1000.0;
            return Some(elapsed.max(1.0));
        }
    }
    None
}
