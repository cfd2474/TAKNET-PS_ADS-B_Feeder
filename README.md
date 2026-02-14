# TAKNET-PS ADS-B Feeder

**Tactical Awareness Kit Network - Public Safety**  
**For Enhanced Tracking**

**Current Version: 2.48.2**

A comprehensive ADS-B aircraft tracking solution designed for distributed deployment with centralized aggregation. Built for public safety, emergency services, and aviation tracking networks.

---

## 🎯 Overview

TAKNET-PS is an independently developed project focused on delivering free, low-latency ADS-B data to public safety users worldwide. This comprehensive feeder system combines real-time aircraft tracking with a professional web interface, supporting multiple aggregator feeds and providing detailed statistics for emergency services and aviation tracking networks.

### Key Features

- **🌐 Web-Based Interface** - Complete configuration and monitoring through browser
- **📡 Multiple Aggregators** - Feed to TAKNET-PS Server, FlightAware, FlightRadar24, ADSBHub, and more
- **📊 Real-Time Statistics** - Built-in graphs1090 for performance monitoring
- **🗺️ Local Map** - tar1090 web map on port 8080
- **🔒 Secure VPN** - Tailscale integration for secure connections
- **📶 WiFi Hotspot** - Captive portal for easy initial configuration
- **🔄 Auto-Updates** - One-click updates from web interface

---

## 📋 Requirements

### Hardware

**Minimum:**
- Raspberry Pi 3B (2GB RAM)
- RTL-SDR dongle (RTL2832U chipset)
- ADS-B antenna (1090 MHz)
- MicroSD card (16GB minimum, 32GB recommended)
- Power supply (5V/2.5A for Pi 3B)

**Recommended:**
- Raspberry Pi 4 (4GB+ RAM)
- FlightAware Pro Stick Plus (or similar with LNA/filter)
- Quality outdoor antenna with proper mounting
- Ethernet connection (more stable than WiFi)
- Power supply (5V/3A USB-C for Pi 4)

### Software

- **Raspberry Pi OS Lite 64-bit (Bookworm)** - Required for dependencies
- Internet connection (for installation and updates)
- Modern web browser (Chrome, Firefox, Safari, Edge)

---

## 🚀 Quick Start

### One-Line Installation

```bash
curl -fsSL https://raw.githubusercontent.com/cfd2474/TAKNET-PS_ADS-B_Feeder/main/install/install.sh | sudo bash
```

### Installation Steps

1. **Flash Raspberry Pi OS Lite 64-bit (Bookworm)** to SD card
2. **Connect SDR** and antenna
3. **Run installer** (command above - this will take 5-10 minutes!)
4. **Access web interface** at `http://taknet-ps.local` or `http://[raspberry-pi-ip]`
5. **Complete setup wizard**

The installer handles:
- Docker installation
- Container configuration
- Web interface setup
- Service registration
- Nginx reverse proxy
- WiFi hotspot (if configured)

### First-Time Setup

After installation completes:

1. Navigate to `http://taknet-ps.local` or `http://[raspberry-pi-ip]`
2. Follow the setup wizard:
   - **SDR Configuration** - Auto-detect dongles and assign functions (1090 MHz, 978 MHz)
   - **Location & Name** - Enter latitude, longitude, altitude, and feeder name

3. After setup wizard completes:
   - **Feed Selection** - Navigate to Feed Selection tab to choose aggregators
   - **Tailscale VPN** (optional) - Navigate to Settings tab to configure secure connection

---

## 📡 System Architecture

### Core Components

**ultrafeeder** - Main ADS-B aggregation container
- Receives data from readsb/dump1090
- Forwards to multiple aggregators
- Provides data to tar1090 and graphs1090
- Handles MLAT processing

**readsb** - Software-defined radio decoder
- Decodes 1090 MHz ADS-B signals
- Processes Mode S messages
- Outputs to ultrafeeder

**tar1090** - Web map interface
- Real-time aircraft display
- Multiple layer options
- Historical track playback
- Accessible on port 8080

**graphs1090** - Statistics and performance
- Signal quality metrics
- Message rate graphs
- Range analysis
- CPU/memory monitoring

**Flask Web App** - Configuration interface
- Feeder management
- Service monitoring
- Update system
- Settings control

---

## 🌐 Web Interface

Access at `http://taknet-ps.local` or `http://[feeder-ip]`

### Navigation Tabs

- **Dashboard** - System status, feed health, statistics
- **Feed Selection** - Enable/disable aggregators
- **Settings** - Location, network, Tailscale, updates
- **Map** - Opens tar1090 (port 8080) in new tab
- **Statistics** - Opens graphs1090 in new tab
- **About** - System information and version

### Dashboard Features

**System Status Card:**
- Core Service (ultrafeeder status)
- Location (coordinates, altitude, timezone)
- Network (hostname, connection type, internet status)

**Feed Status Table:**
- Enabled/disabled state for each aggregator
- Connection health indicators
- Quick enable/disable toggles

---

## 📶 Supported Aggregators

### Account-Free Feeds

- **TAKNET-PS Server** - Primary aggregation server
- **Airplanes.Live** - Community aggregator
- **adsb.fi** - Finnish ADS-B network
- **adsb.lol** - Community network

### Account-Required Feeds

- **FlightRadar24** - Commercial tracking service
- **FlightAware** (PiAware) - Flight tracking platform
- **ADSBHub** - Community data exchange

### Configuration

Each aggregator can be:
- Enabled/disabled via toggle buttons
- Configured with account credentials
- Monitored for connection health
- Tested for connectivity

---

## 🔒 Tailscale VPN Integration

### Features

- Secure encrypted connection to TAKNET-PS Server
- Automatic failback to public internet
- Simple one-button setup
- No port forwarding required
- DNS-friendly hostname generation

### Obtaining an Auth Key

**IMPORTANT:** You must use an approved TAKNET-PS auth key to communicate securely with the aggregator service.

**Contact for Auth Key:**
- Email: **Michael.Leckliter@yahoo.com**
- Subject: "TAKNET-PS Auth Key Request"
- Include: Your name, location, and intended use

Standard Tailscale auth keys will NOT work with the TAKNET-PS aggregation network. Only approved keys provided by the network administrator will establish secure connectivity.

### Setup Process

1. Obtain approved Tailscale auth key (contact above)
2. Navigate to **Settings** → **Tailscale VPN**
3. Enter auth key
4. Click **Enable & Connect**
5. Wait for connection (5-10 seconds)
6. Verify connection shows IP and hostname

### Hostname Sanitization

The system automatically:
- Converts feeder name to DNS-safe format
- Prepends zip code (from location or coordinates)
- Removes special characters
- Example: "Corona Feeder #1" → "92882-corona-feeder-1"

---

## 📍 Location Configuration

### Setting Your Location

**Via Web Interface:**
1. Navigate to **Settings** → **Location**
2. Enter coordinates:
   - Latitude (DD.DDDDD format, e.g., 33.55390)
   - Longitude (DD.DDDDD format, e.g., -117.21390)
   - Altitude (meters, whole number)
3. Select timezone
4. Optional: Enter zip/postal code
5. **Provide a feeder name** that describes your station (e.g., "Corona Rooftop Feeder", "Downtown Fire Station")
6. Click **Apply Changes & Restart Ultrafeeder**

**Important:** Accurate location is critical for:
- MLAT positioning calculations
- Coverage analysis
- Proper data attribution
- Statistics accuracy

---

## 🔄 Updates

### Web Interface Method (Recommended)

1. Navigate to **Settings** → **System Updates**
2. Click **Check for Updates**
3. If update available, click **Update Now**
4. Wait for progress bar to complete
5. System restarts automatically

### Manual Update Method

```bash
curl -fsSL https://raw.githubusercontent.com/cfd2474/TAKNET-PS_ADS-B_Feeder/main/install/install.sh | sudo bash -s -- --update
```

### Update Process

Updates preserve:
- Location settings
- Aggregator configurations
- Feed selections
- Network settings
- Tailscale connection

Updates replace:
- Web interface files
- Docker compose configuration
- System scripts
- Static assets

---

## 📊 Performance Monitoring

### graphs1090 Access

Available at `http://[feeder-ip]:8080/graphs1090/?timeframe=24h`

**Available Metrics:**
- Aircraft positions tracked
- Message rate per second
- Signal strength distribution
- Max range over time
- CPU and memory usage
- Network throughput

**Timeframe Options:**
- 6h, 24h (default), 48h
- 7d, 30d, 90d, 365d

### Logs Access

Available at `http://taknet-ps.local/logs` or `http://[feeder-ip]/logs`

**Log Sources:**
- ultrafeeder (main service)
- readsb (SDR decoder)
- tar1090 (web map)
- graphs1090 (statistics)

---

## 🛠️ Troubleshooting

### SDR Not Detected

```bash
# Check USB devices
lsusb | grep RTL

# Check Docker can see device
docker exec ultrafeeder rtl_test -t
```

**Common Solutions:**
- Reseat USB connection
- Try different USB port
- Check power supply (need 5V/3A minimum)
- Verify RTL-SDR driver not blacklisted

### No Aircraft Showing

**Checklist:**
1. Verify SDR connected and recognized
2. Check antenna connection
3. Confirm location settings accurate
4. Verify ultrafeeder running: `docker ps`
5. Check logs for errors: Settings → System Updates → View Logs
6. Ensure 1090 MHz not blocked by local interference

### Tailscale Connection Issues

**Diagnosis:**
1. Settings → Tailscale VPN → Check status
2. Verify auth key is valid
3. Check internet connectivity
4. Review Tailscale connection logs

**Solutions:**
- Disable and re-enable with fresh auth key
- Check firewall not blocking UDP 41641
- Verify system time is accurate

### Update Failures

**Recovery Steps:**
```bash
# Re-run installer in update mode
curl -fsSL https://raw.githubusercontent.com/cfd2474/TAKNET-PS_ADS-B_Feeder/main/install/install.sh | sudo bash -s -- --update

# If that fails, check Docker
sudo systemctl status docker

# Restart Docker if needed
sudo systemctl restart docker
```

---

## 🔧 Advanced Configuration

### Manual Configuration Files

**Location:** `/opt/adsb/config/.env`

**Key Variables:**
```bash
FEEDER_LAT=33.55390
FEEDER_LONG=-117.21390
FEEDER_ALT_M=304
FEEDER_TZ=America/Los_Angeles
MLAT_SITE_NAME=92882-Corona-Feeder

# Aggregator enables
TAKNET_ENABLED=true
FR24_ENABLED=false
ADSBLOL_ENABLED=true
# ... etc
```

**After manual edits:**
```bash
cd /opt/adsb/config
sudo docker compose up -d
```

### Adding Custom Aggregators

Edit `/opt/adsb/config/docker-compose.yml`:

```yaml
- ULTRAFEEDER_CONFIG=
    # Add custom aggregator
    mlathub,custom.server.com,30005,beast_reduce_plus_out;
```

### WiFi Hotspot Configuration

**Files:**
- `/opt/adsb/wifi-manager/check-connection.sh`
- `/etc/systemd/system/wifi-manager.service`

**Hotspot Details:**
- SSID: `TAKNET-PS-Setup`
- Portal: `http://192.168.50.1`

---

## 📂 Directory Structure

```
/opt/adsb/
├── config/
│   ├── docker-compose.yml
│   └── .env
├── scripts/
│   ├── config_builder.py
│   └── updater.sh
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
│       └── taknet-ps_shield.png
├── wifi-manager/
│   └── check-connection.sh
├── VERSION
└── version.json
```

---

## 🌐 Network Ports

| Port | Service | Purpose |
|------|---------|---------|
| 80 | Nginx/Flask Web | Main web interface (redirects to SSL if configured) |
| 8080 | tar1090 | Map display |
| 8080 | graphs1090 | Statistics (subpath) |
| 30005 | readsb | Beast output |
| 30104 | MLAT | Multilateration |

**Firewall Note:** Only port 80 needs to be accessible from your network for normal operation. Access the web interface without specifying a port number.

---

## 🔐 Security Considerations

### Web Interface Access

- No authentication by default
- Runs on local network only
- Use Tailscale for remote access
- Consider firewall rules for exposure

### Tailscale Benefits

- Encrypted VPN tunnel
- No exposed ports
- Certificate-based auth
- Centralized access control

### Best Practices

1. Keep system updated
2. Use strong WiFi passwords
3. Enable Tailscale for remote access
4. Regularly review aggregator connections
5. Monitor logs for anomalies

---

## 💖 Supporting the Project

TAKNET-PS is an independently developed, free service providing low-latency ADS-B data to public safety users worldwide. If you find this project valuable, please consider supporting continued development and operation.

**To support:**
- Navigate to the **About** tab in your feeder's web interface
- Find donation and support information
- Your contributions help maintain servers, develop new features, and expand coverage

---

## 📞 Support

### Getting Help

**Documentation:**
- This README
- In-app About page
- Web interface tooltips

**Community:**
- GitHub Issues: [Report bugs/request features](https://github.com/cfd2474/TAKNET-PS_ADS-B_Feeder/issues)

**Direct Support:**
- Email: michael.leckliter@yahoo.com
- For Tailscale auth keys and network access

---

## 📝 Version Information

**Current Version:** 2.47.35  
**Release Date:** February 13, 2026  
**Minimum Version:** 2.40.0

### Recent Improvements

- TAKNET-PS shield logo on dashboard
- Redesigned status section with color-coded panels
- Statistics tab added to navigation
- Automated logo installation
- Improved Tailscale integration
- ADSBHub toggle button (matches other feeds)
- Removed clutter from UI

---

## 🏗️ Technical Stack

- **OS:** Raspberry Pi OS Lite 64-bit (Bookworm) - Required
- **Container:** Docker / Docker Compose
- **Core Service:** ghcr.io/sdr-enthusiasts/docker-adsb-ultrafeeder
- **Web Framework:** Python Flask
- **Web Server:** Nginx (reverse proxy)
- **Map:** tar1090
- **Graphs:** graphs1090
- **VPN:** Tailscale
- **Frontend:** HTML, CSS, JavaScript

---

## 📜 License

This project is designed for public safety and community use. See repository for license details.

---

## 🙏 Acknowledgments

- **SDR-Enthusiasts** - For excellent docker-adsb-ultrafeeder container
- **wiedehopf** - For tar1090 and graphs1090
- **FlightAware** - For PiAware integration
- **Tailscale** - For seamless VPN solution
- **ADS-B Community** - For continued support and development

---

## 🚀 Quick Reference

### Essential Commands

```bash
# Check system status
docker ps

# View logs
docker logs ultrafeeder

# Restart services
cd /opt/adsb/config && docker compose restart

# Update system
curl -fsSL https://raw.githubusercontent.com/cfd2474/TAKNET-PS_ADS-B_Feeder/main/install/install.sh | sudo bash -s -- --update

# Check version
cat /opt/adsb/VERSION
```

### Essential URLs

- Web Interface: `http://taknet-ps.local` or `http://[feeder-ip]`
- Map: `http://[feeder-ip]:8080`
- Statistics: `http://[feeder-ip]:8080/graphs1090/`
- Logs: `http://taknet-ps.local/logs`

---

**TAKNET-PS ADS-B Feeder**  
*Tactical Awareness Kit Network - Public Safety*  
*For Enhanced Tracking*
