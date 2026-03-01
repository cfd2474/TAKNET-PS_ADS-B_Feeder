# TAKNET-PS ADS-B Feeder

<p align="center">
  <img src="web/static/taknetlogo.png" alt="TAKNET-PS Logo" width="600">
</p>

**Tactical Awareness Kit Network - Public Safety**  
**For Enhanced Tracking**

**Current Version: 2.59.30**

A comprehensive ADS-B aircraft tracking solution designed for distributed deployment with centralized aggregation. Built for public safety, emergency services, and aviation tracking networks.

---

## 🎯 Overview

TAKNET-PS is an independently developed project focused on delivering free, low-latency ADS-B data to public safety users worldwide. This feeder system combines real-time aircraft tracking with a professional web interface, supporting multiple aggregator feeds and providing detailed statistics for emergency services and aviation tracking networks.

### Key Features

- **🌐 Web-Based Interface** - Complete configuration and monitoring through browser
- **📡 Multiple Aggregators** - Feed to TAKNET-PS Server, FlightAware, FlightRadar24, ADSBHub, ADSBExchange, and more
- **📊 Real-Time Statistics** - Built-in graphs1090 for performance monitoring
- **🗺️ Local Map** - tar1090 web map on port 8080
- **🔒 Dual VPN** - NetBird (primary aggregator connection) + Tailscale (optional personal remote access)
- **📶 WiFi Hotspot** - Captive portal for easy initial configuration
- **🔄 Auto-Updates** - One-click updates from web interface
- **📡 Universal SDR Detection** - SoapySDR-based detection supports RTL-SDR and compatible hardware

---

## 📋 Requirements

### Hardware

**Minimum:**
- Raspberry Pi 3B (1GB RAM)
- RTL-SDR dongle (RTL2832U chipset)
- ADS-B antenna (1090 MHz)
- MicroSD card (16GB minimum, 32GB recommended)
- Power supply (5V/2.5A for Pi 3B)

**Recommended:**
- Raspberry Pi 4 (4GB+ RAM)
- FlightAware Pro Stick Plus or similar (LNA + filter)
- Quality outdoor antenna with proper coax and mounting
- Ethernet connection (more stable than WiFi for MLAT)
- Power supply (5V/3A USB-C for Pi 4)

**Optional 978 MHz UAT (US Only):**
- Second RTL-SDR dongle
- **OR** FTDI-based Stratux UATRadio
- 978 MHz antenna

### Software

- **Raspberry Pi OS Lite 64-bit (Bookworm)** — Required
- Internet connection (installation and updates)
- Modern web browser (Chrome, Firefox, Safari, Edge)

---

## 🚀 Quick Start

### One-Line Installation

```bash
curl -fsSL https://raw.githubusercontent.com/cfd2474/TAKNET-PS_ADS-B_Feeder/main/install/install.sh | sudo bash
```

### Installation Steps

1. **Flash Raspberry Pi OS Lite 64-bit (Bookworm)** to SD card
2. **Connect SDR** and antenna before powering on
3. **Run installer** (command above — takes 5–10 minutes)
4. **Access web interface** at `http://taknet-ps.local` or `http://[raspberry-pi-ip]`
5. **Complete setup wizard**

The installer handles:
- Docker installation and image pre-download
- SoapySDR universal SDR detection tools
- NetBird VPN installation
- Tailscale VPN installation
- Web interface and Nginx reverse proxy
- Service registration (systemd)
- WiFi hotspot manager
- Aircraft data retention (24-hour limit)
- SSH access configuration for remote user

### First-Time Setup

After installation:

1. Navigate to `http://taknet-ps.local` or `http://[raspberry-pi-ip]`
2. Follow the setup wizard:
   - **SDR Configuration** — Auto-detect dongles via SoapySDR and assign functions (1090 MHz, 978 MHz)
   - **Location & Name** — Latitude, longitude, altitude, timezone, and feeder name
3. After wizard completes:
   - **Feed Selection** — Enable/disable aggregators
   - **Settings → NetBird VPN** — Connect to TAKNET-PS private network (recommended)
   - **Settings → Tailscale VPN** — Optional, for personal remote management

---

## 📡 System Architecture

### Core Components

**ultrafeeder** — Main ADS-B aggregation container
- Receives decoded data from readsb
- Forwards to multiple aggregators via ULTRAFEEDER_CONFIG
- Provides data to tar1090 and graphs1090
- Handles MLAT processing

**readsb** — Software-defined radio decoder
- Decodes 1090 MHz ADS-B and Mode S signals
- Outputs Beast format to ultrafeeder

**tar1090** — Web map interface
- Real-time aircraft display on port 8080
- Historical track playback
- Multiple map layers

**graphs1090** — Statistics and performance
- Signal quality metrics, message rate graphs
- Range analysis and CPU/memory monitoring

**Flask Web App** — Configuration interface
- Feeder setup and management
- Service monitoring and restart
- OTA update system
- VPN management (NetBird + Tailscale)

**NetBird** — Primary VPN (systemd service)
- Encrypted peer-to-peer tunnel to TAKNET-PS aggregator
- SSH access for remote user restricted to VPN addresses

---

## 🌐 Web Interface

Access at `http://taknet-ps.local` or `http://[feeder-ip]`

### Navigation Tabs

- **Dashboard** — System status, feed health, live statistics
- **Feed Selection** — Enable/disable aggregators
- **Settings** — Location, VPN, updates, service restarts
- **Map** — Opens tar1090 (port 8080) in new tab
- **Statistics** — Opens graphs1090 in new tab
- **About** — System information and version

### Dashboard — System Status Card

**Network section:**
- Hostname, machine name, connection type (Ethernet/WiFi), internet status
- **Connection Quality** — Good / Moderate / Poor with avg latency and packet loss (measured on page load)

**Location section:**
- Latitude, longitude, altitude, timezone

**SDR Devices section:**
- Auto-detected via SoapySDR on page load
- Columns: Index, Type, Serial, Use For, Gain, Bias Tee
- Read-only — configure via setup wizard or Settings

### Dashboard — Feed Status Table

| Indicator | Meaning |
|---|---|
| 🟢 Green ✓ | Feed active, MLAT active |
| 🟡 Amber ✓ | Feed active, MLAT down |
| 🔴 Red ✓ | Feed down |
| ⚫ Gray ✓ | Status unknown |

---

## 📶 Supported Aggregators

### Account-Free

| Aggregator | Notes |
|---|---|
| **TAKNET-PS Server** | Primary — encrypted via NetBird |
| **Airplanes.Live** | Community aggregator |
| **adsb.fi** | Finnish ADS-B network |
| **adsb.lol** | Community network |
| **ADSBExchange** | Unfiltered feed (UUID auto-generated) |

### Account-Required

| Aggregator | Notes |
|---|---|
| **FlightRadar24** | FR24 key required |
| **FlightAware** (PiAware) | Feeder ID required |
| **ADSBHub** | Station key required |

---

## 🔒 VPN Integration

| VPN | Role | Purpose |
|-----|------|---------|
| **NetBird** | Primary | Encrypted aggregator connection + SSH access |
| **Tailscale** | Optional | Personal remote management |

### Aggregator Routing

```
NetBird connected  →  vpn.tak-solutions.com:30004/30105
NetBird inactive   →  adsb.tak-solutions.com:30004/30105 (public fallback)
```

Tailscale is **not** used for aggregator routing.

### NetBird Setup

**Option 1 — Self-service (recommended):**
1. Visit [https://netbird.tak-solutions.com](https://netbird.tak-solutions.com)
2. Create a free account (email or Google sign-in)
3. Request will be approved by the administrator
4. Once approved, generate setup keys and manage unlimited devices at no cost

**Option 2 — Contact administrator:**
Michael Leckliter — [mike@tak-solutions.com](mailto:mike@tak-solutions.com)

**Connecting:**
1. **Settings → NetBird VPN**
2. Enter Management URL and Setup Key
3. Click **Connect**
4. Confirm status shows Connected with assigned IP

### Tailscale Setup

1. **Settings → Tailscale VPN**
2. Enter your personal Tailscale auth key
3. Click **Connect**

> **Migrating from TAKNET-PS Tailscale?** Once on NetBird, disconnect from the TAKNET-PS Tailscale network and reconnect with your own personal key — or leave Tailscale disconnected if NetBird covers your access needs.

### Feeder Hostname

Automatically formatted for VPN/MLAT registration:
- `"Corona Feeder #1"` → `"92882-corona-feeder-1"`

---

## 🔐 Remote SSH Access

| Setting | Value |
|---|---|
| Username | `remote` |
| Password | `adsb` |
| Network requirement | NetBird or Tailscale (100.x.x.x) |
| Permissions | Limited sudo for ADSB services |

```bash
# Connect via NetBird or Tailscale, then:
ssh remote@<vpn-ip>
```

SSH is blocked from the public internet. Only connections originating from `100.x.x.x` are accepted. This is configured automatically during install and verified on every update.

---

## 📍 Location Configuration

**Via Web Interface:**
1. **Settings → Location**
2. Enter latitude, longitude, altitude (meters), timezone, feeder name
3. Click **Apply Changes & Restart Ultrafeeder**

Accurate location is critical for MLAT, coverage analysis, and data attribution.

---

## 🔄 Updates

### Web Interface (Recommended)

**Settings → System Updates → Check for Updates → Update Now**

### Manual

```bash
curl -fsSL https://raw.githubusercontent.com/cfd2474/TAKNET-PS_ADS-B_Feeder/main/install/install.sh | sudo bash -s -- --update
```

### What Updates Preserve
Location, aggregator configs, feed selections, VPN credentials, network settings

### What Updates Replace
Web interface files, Docker Compose config, system scripts, static assets

---

## 📊 Performance Monitoring

**graphs1090:** `http://[feeder-ip]:8080/graphs1090/?timeframe=24h`

Timeframes: 6h, 24h, 48h, 7d, 30d, 90d, 365d

**Logs:** `http://taknet-ps.local/logs`

---

## 💾 Data Retention

Aircraft history is automatically purged after **24 hours** to prevent SD card fill-up.

- Cleanup runs hourly via cron (`/opt/adsb/scripts/cleanup-aircraft-data.sh`)
- Heatmap accumulation disabled
- Applied to `/opt/adsb/ultrafeeder/`

---

## 🛠️ Troubleshooting

### SDR Not Detected

```bash
# Detect SDR devices
SoapySDRUtil --find

# Check USB
lsusb | grep -i rtl

# Check from inside container
docker exec ultrafeeder SoapySDRUtil --find
```

Common fixes: reseat USB, try different port, check power supply (5V/3A min), verify `dvb_usb_rtl28xxu` is blacklisted.

### No Aircraft Showing

1. Verify SDR detected (`SoapySDRUtil --find`)
2. Check antenna and coax
3. Confirm location settings
4. Verify ultrafeeder running: `docker ps`
5. Check logs: Settings → Logs

### NetBird Issues

```bash
# Check status
netbird status

# Check logs
journalctl -u netbird --no-pager | tail -50
```

- Try **Settings → Restart Services → NetBird**
- Verify setup key is not expired
- If NetBird fails, feeder auto-falls back to public endpoint — data still flows

### Tailscale Issues

- Verify auth key is valid
- Check firewall not blocking UDP 41641
- Verify system time is accurate

### Update Failures

```bash
# Re-run update
curl -fsSL https://raw.githubusercontent.com/cfd2474/TAKNET-PS_ADS-B_Feeder/main/install/install.sh | sudo bash -s -- --update

# Check Docker
sudo systemctl status docker
sudo systemctl restart docker
```

---

## 🔧 Advanced Configuration

### Key `.env` Variables

**File:** `/opt/adsb/config/.env`

```bash
# Location
FEEDER_LAT=33.55390
FEEDER_LONG=-117.21390
FEEDER_ALT_M=304
FEEDER_TZ=America/Los_Angeles
MLAT_SITE_NAME=92882-Corona-Feeder

# TAKNET-PS aggregator
TAKNET_PS_ENABLED=true
TAKNET_PS_SERVER_HOST_VPN=vpn.tak-solutions.com
TAKNET_PS_SERVER_HOST_FALLBACK=adsb.tak-solutions.com
TAKNET_PS_SERVER_PORT=30004
TAKNET_PS_MLAT_PORT=30105

# SDR
SDR_1090_SERIAL=10901090
SDR_1090_GAIN=autogain

# Feed enables
FR24_ENABLED=false
ADSBFI_ENABLED=true
ADSBLOL_ENABLED=true
ADSBX_ENABLED=true
AIRPLANESLIVE_ENABLED=true
ADSBHUB_ENABLED=false
PIAWARE_ENABLED=false
```

After manual edits: `cd /opt/adsb/config && sudo docker compose up -d`

### Service Restarts

**Settings → Restart Services** — Available: Ultrafeeder, FlightRadar24, PiAware, NetBird, Tailscale

### WiFi Hotspot

SSID: `TAKNET-PS-Setup` | Portal: `http://192.168.50.1`

---

## 📂 Directory Structure

```
/opt/adsb/
├── config/
│   ├── docker-compose.yml
│   └── .env
├── scripts/
│   ├── config_builder.py
│   ├── updater.sh
│   └── cleanup-aircraft-data.sh
├── web/
│   ├── app.py
│   ├── templates/
│   │   ├── dashboard.html
│   │   ├── feeds.html
│   │   ├── settings.html
│   │   └── ...
│   └── static/
│       ├── css/
│       ├── js/
│       └── taknetlogo.png
├── wifi-manager/
│   └── check-connection.sh
├── VERSION
└── version.json
```

---

## 🌐 Network Ports

| Port | Service | Purpose |
|------|---------|---------|
| 80 | Nginx/Flask | Main web interface |
| 8080 | tar1090 / graphs1090 | Map and statistics |
| 30005 | readsb | Beast output (internal) |
| 30004 | TAKNET-PS aggregator | Outbound Beast feed |
| 30105 | TAKNET-PS MLAT | Outbound MLAT |
| 51820 UDP | NetBird / WireGuard | VPN tunnel |
| 41641 UDP | Tailscale | VPN tunnel (if used) |

Only port 80 needs to be accessible on your local network for normal operation.

---

## 🔐 Security

- Web interface runs on local network, no authentication by default
- SSH access for `remote` user restricted to VPN (100.x.x.x) — blocked from public internet
- Keep feeder updated for latest security patches
- Use strong WiFi password if hotspot is active

---

## 💖 Supporting the Project

TAKNET-PS is independently developed and free for public safety use. Navigate to the **About** tab in your feeder's web interface for donation and support information.

---

## 📞 Support

**GitHub Issues:** [https://github.com/cfd2474/TAKNET-PS_ADS-B_Feeder/issues](https://github.com/cfd2474/TAKNET-PS_ADS-B_Feeder/issues)

**Direct Contact:**
Michael Leckliter — [mike@tak-solutions.com](mailto:mike@tak-solutions.com)
*NetBird setup keys, network access, general support*

**NetBird Self-Service:**
[https://netbird.tak-solutions.com](https://netbird.tak-solutions.com) — Register, get approved, manage your own keys at no cost

---

## 📝 Version History

**Current Version:** 2.59.30
**Release Date:** February 28, 2026
**Minimum Supported Version:** 2.40.0

### v2.59.30 — Tailscale universal tailnet; version SOP & tar.gz
- **Tailscale any tailnet** — Status shows Connected for any tailnet; SSH from any device on that tailnet (no longer tied to tail4d77be.ts.net)
- **Version bump script** — `scripts/version-bump.sh` updates all version locations per SOP and builds a complete tar.gz every release

### v2.59.x — NetBird Integration & Dashboard Enhancements

- **NetBird as Primary VPN** — Aggregator routes via NetBird (`vpn.tak-solutions.com`) or falls back to public endpoint. Tailscale removed from aggregator routing entirely.
- **NetBird Self-Service** — Users register at `netbird.tak-solutions.com` without contacting admin
- **NetBird SSH Flags** — `--allow-server-ssh --enable-ssh-root` applied on install, verified on every update
- **SSH VPN-Only Access** — `remote` user (password: adsb) restricted to NetBird/Tailscale (`100.x.x.x`), blocked from public internet
- **Beast_out Feed** — TAKNET-PS feed changed from `beast_reduce_plus_out` to `beast_out` (full position data)
- **SoapySDR Detection** — SDR detection migrated from `rtl_test` to `SoapySDRUtil --find`
- **SDR Status on Dashboard** — System Status card shows detected SDR devices (Type, Serial, Use For, Gain, Bias Tee)
- **Connection Quality Indicator** — Dashboard shows Good/Moderate/Poor with latency and packet loss
- **Feed Checkmark Colors** — Green (good), Amber (MLAT down), Red (feed down), Gray (unknown)
- **24-Hour Data Retention** — Hourly cron purges aircraft data, heatmap disabled
- **NetBird in Restart Services** — NetBird added to service restart modal
- **NetBird Contact Info** — Settings page and README updated with self-service portal and contact
- **Installer Banner Version** — Banner reads from `INSTALLER_VERSION` variable, stays in sync with `VERSION` file
- **Logo** — TAKNET-PS logo across all pages

### v2.58.x — Dual-Tailscale Removal

- Removed private TAKNET-PS Tailscale network
- Single Tailscale instance reserved for personal/owner access
- Groundwork for NetBird integration

---

## 🏗️ Technical Stack

| Component | Technology |
|---|---|
| OS | Raspberry Pi OS Lite 64-bit (Bookworm) |
| Containers | Docker / Docker Compose |
| ADS-B Core | ghcr.io/sdr-enthusiasts/docker-adsb-ultrafeeder |
| Web Framework | Python Flask |
| Web Server | Nginx (reverse proxy) |
| Map | tar1090 |
| Graphs | graphs1090 |
| SDR Detection | SoapySDR (universal) |
| Primary VPN | NetBird |
| Reserve VPN | Tailscale (optional) |
| Frontend | HTML, CSS, JavaScript |

---

## 🙏 Acknowledgments

- **SDR-Enthusiasts** — docker-adsb-ultrafeeder container
- **wiedehopf** — tar1090 and graphs1090
- **FlightAware** — PiAware integration
- **NetBird** — Open-source WireGuard-based VPN
- **Tailscale** — VPN solution
- **ADS-B Community** — Continued support and development

---

## 🚀 Quick Reference

### Essential Commands

```bash
# System status
docker ps

# Ultrafeeder logs
docker logs ultrafeeder --tail 100

# Restart all services
cd /opt/adsb/config && docker compose restart

# NetBird status
netbird status

# Detect SDR devices
SoapySDRUtil --find

# Run update
curl -fsSL https://raw.githubusercontent.com/cfd2474/TAKNET-PS_ADS-B_Feeder/main/install/install.sh | sudo bash -s -- --update

# Check version
cat /opt/adsb/VERSION
```

### Essential URLs

| Resource | URL |
|---|---|
| Web Interface | `http://taknet-ps.local` or `http://[feeder-ip]` |
| Live Map | `http://[feeder-ip]:8080` |
| Statistics | `http://[feeder-ip]:8080/graphs1090/` |
| Logs | `http://taknet-ps.local/logs` |
| Global Map | `http://adsb.tak-solutions.com/tar1090/` |
| NetBird Portal | `https://netbird.tak-solutions.com` |

---

*TAKNET-PS ADS-B Feeder — Tactical Awareness Kit Network, Public Safety*
