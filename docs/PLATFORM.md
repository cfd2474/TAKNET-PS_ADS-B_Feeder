# Platform Requirements

## Target Platform

**TAKNET-PS ADSB Feeder is designed specifically for:**

### Operating System
- **Raspberry Pi OS Lite 64-bit (Bookworm)**
- Released: October 2023
- Debian version: 12 (Bookworm)
- Architecture: arm64 (64-bit)

**Download:** [https://www.raspberrypi.com/software/operating-systems/](https://www.raspberrypi.com/software/operating-systems/)

### Why Bookworm?
- Latest stable Raspberry Pi OS
- arm64 architecture (better performance)
- Docker 24+ support
- Modern kernel (6.1+)
- Python 3.11+
- systemd 252+

---

## Hardware Requirements

### Minimum
- **Raspberry Pi 3B+**
- 1GB RAM
- 16GB microSD card
- RTL-SDR dongle
- 2.5A power supply
- Network connection (Ethernet or WiFi)

### Recommended
- **Raspberry Pi 4 (2GB+)** or **Raspberry Pi 5**
- 32GB+ microSD card (Class 10)
- 3A+ power supply
- Ethernet connection (more stable)
- Active cooling (heatsink or fan)

### RTL-SDR
- RTL2832U chipset
- R820T/R820T2 tuner
- 1090 MHz antenna
- USB 2.0 or 3.0

**Tested Devices:**
- RTL-SDR Blog V3
- FlightAware Pro Stick
- FlightAware Pro Stick Plus

---

## Network Requirements

### Internet Connection
- **Download:** 5+ Mbps (for Docker images)
- **Upload:** 1+ Mbps (for feeding)
- **Latency:** <100ms preferred
- **Data:** ~1-5GB/month (varies by location)

### Ports Used
- **80** - HTTP (Nginx)
- **5000** - Web UI (Flask)
- **8080** - Aircraft map (tar1090)
- **8754** - FR24 interface
- **30001-30005** - Beast data feeds
- **30104** - MLAT client
- **30105** - MLAT results

### WiFi Requirements
- 2.4GHz or 5GHz support
- WPA2/WPA3 encryption supported
- Open networks supported (for hotspot)

---

## Software Dependencies

### Automatically Installed
The installer handles all dependencies:

**System Packages:**
- docker.io
- docker-compose
- python3 (3.11+)
- python3-flask
- python3-pip
- nginx
- avahi-daemon
- avahi-utils
- hostapd
- dnsmasq
- rtl-sdr
- vnstat
- iptables
- wget
- curl

**Docker Images:**
- ghcr.io/sdr-enthusiasts/docker-adsb-ultrafeeder:latest
- ghcr.io/sdr-enthusiasts/docker-flightradar24:latest

---

## Disk Space

### Installation
- **Base OS:** ~2GB
- **Docker images:** ~1GB
- **Application:** ~50MB
- **Total minimum:** 4GB

### Runtime
- **Logs:** ~100MB/day (auto-rotated)
- **vnstat data:** ~10MB (30 days)
- **Docker containers:** ~1-2GB
- **Recommended free space:** 8GB+

---

## Memory Usage

### Typical Usage
- **OS + Services:** ~300MB
- **Docker (Ultrafeeder):** ~150MB
- **Docker (FR24):** ~50MB
- **Web UI (Flask):** ~30MB
- **Nginx:** ~10MB
- **Total:** ~550MB

### Swap Recommended
- Raspberry Pi 3: 1GB swap
- Raspberry Pi 4: 512MB swap
- Raspberry Pi 5: No swap needed

---

## CPU Requirements

### Load Average
- Idle: 0.2-0.5
- Normal operation: 0.5-1.0
- Peak (startup): 2.0-3.0

### CPU Cores
- Raspberry Pi 3: 4 cores @ 1.2GHz (adequate)
- Raspberry Pi 4: 4 cores @ 1.5GHz (recommended)
- Raspberry Pi 5: 4 cores @ 2.4GHz (excellent)

---

## Installation Time

### Fresh Install
- **OS imaging:** 5-10 minutes
- **First boot:** 2-3 minutes
- **Installer script:** 10-15 minutes
- **Network config:** 2-3 minutes
- **Docker pull:** 5-10 minutes (varies by connection)
- **Total:** ~30-45 minutes

### Initial Setup Wizard
- **SDR configuration:** 2-3 minutes
- **Location setup:** 1-2 minutes
- **Optional configuration:** 2-5 minutes
- **Service start:** 2-4 minutes
- **Total:** ~10-15 minutes

---

## Network Configuration

### Static IP (Recommended)
Configure in Raspberry Pi OS:
```bash
sudo nmtui
# Or edit /etc/dhcpcd.conf
```

### DHCP (Default)
- Works out of the box
- May change IP on reboot
- Use mDNS (taknet-ps.local) for consistency

### WiFi Configuration
- Configured via installer
- Or via hotspot captive portal
- Or manually in `/etc/wpa_supplicant/wpa_supplicant.conf`

---

## Tested Configurations

### ✅ Fully Tested

| Model | OS | Status | Notes |
|-------|----|----|-------|
| Pi 4 (2GB) | Bookworm 64-bit | ✅ Excellent | Recommended |
| Pi 4 (4GB) | Bookworm 64-bit | ✅ Excellent | Best performance |
| Pi 4 (8GB) | Bookworm 64-bit | ✅ Excellent | Overkill but works |
| Pi 5 (4GB) | Bookworm 64-bit | ✅ Excellent | Fastest |

### ⚠️ Should Work

| Model | OS | Status | Notes |
|-------|----|----|-------|
| Pi 3B+ | Bookworm 64-bit | ⚠️ Adequate | Slower, but functional |
| Pi 3B | Bookworm 64-bit | ⚠️ Adequate | Minimum viable |

### ❌ Not Supported

| Model | OS | Status | Notes |
|-------|----|----|-------|
| Pi Zero/Zero W | Any | ❌ Too slow | Insufficient CPU |
| Pi 2 | Any | ❌ Too old | No arm64 support |
| Any | 32-bit OS | ❌ Wrong arch | Requires 64-bit |
| Any | Bullseye or older | ❌ Too old | Requires Bookworm |

---

## Performance Expectations

### Aircraft Reception
- **Urban area:** 50-150 aircraft
- **Suburban area:** 100-250 aircraft
- **Rural area:** 50-150 aircraft (varies greatly)
- **Range:** 100-250 miles (depends on antenna/elevation)

### Web UI
- Dashboard refresh: 10 seconds
- Map update: 1 second
- Configuration changes: Immediate

### System Responsiveness
- SSH login: <1 second
- Web page load: <2 seconds
- Service restart: 10-30 seconds

---

## Pre-Installation Checklist

### Before Starting

- [ ] Raspberry Pi 3B+ or newer
- [ ] 16GB+ microSD card (Class 10)
- [ ] RTL-SDR dongle with antenna
- [ ] Fresh Raspberry Pi OS Bookworm 64-bit
- [ ] Internet connection available
- [ ] Static IP configured (optional)
- [ ] TAKNET-PS credentials (optional)
- [ ] Tailscale auth key (optional)
- [ ] FlightRadar24 key (optional)

### First Boot Recommendations

```bash
# Update system first
sudo apt update
sudo apt upgrade -y
sudo reboot

# Then run installer
curl -fsSL https://raw.githubusercontent.com/cfd2474/feeder_test/main/install/install.sh | sudo bash
```

---

## Troubleshooting Platform Issues

### Docker Won't Start
```bash
# Check Docker status
sudo systemctl status docker

# Enable Docker
sudo systemctl enable docker
sudo systemctl start docker
```

### Insufficient Memory
```bash
# Check memory
free -h

# Enable swap if needed
sudo dphys-swapfile setup
sudo dphys-swapfile swapon
```

### CPU Throttling
```bash
# Check throttling
vcgencmd get_throttled

# If throttled:
# - Improve cooling
# - Check power supply
# - Reduce overclock
```

### WiFi Issues
```bash
# Check WiFi interface
iwconfig

# Scan networks
sudo iwlist wlan0 scan

# Check driver
dmesg | grep -i wifi
```

---

**Platform:** Raspberry Pi OS Bookworm 64-bit  
**Last Updated:** January 25, 2026
