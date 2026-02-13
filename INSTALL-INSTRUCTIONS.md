# TAKNET-PS v2.27.2 Installation Instructions

**Package:** taknet-ps-complete-v2.27.2-full
**Version:** 2.27.2
**Date:** February 3, 2026

---

## 🚀 QUICK INSTALL (Recommended)

### For Fresh Raspberry Pi Installation:

```bash
# Download and run installer
curl -fsSL https://raw.githubusercontent.com/[your-repo]/main/install/install.sh | sudo bash
```

**Note:** Update the URL above with your actual GitHub repository path.

---

## 📦 MANUAL INSTALLATION FROM THIS PACKAGE

### Prerequisites:
- Raspberry Pi OS Lite (64-bit recommended)
- Internet connection
- RTL-SDR device connected

### Installation Steps:

```bash
# 1. Extract package
cd /tmp
tar -xzf taknet-ps-complete-v2.27.2-full.tar.gz
cd taknet-ps-complete-v2.27.2-full

# 2. Run installer script
sudo bash install/install.sh
```

The installer will:
- Install all required packages
- Set up Docker and services
- Install web interface
- Configure systemd services
- Start the setup wizard

---

## 🔄 UPGRADING FROM OLDER VERSION

### If you have v2.8.x or earlier:

```bash
# Stop services
sudo systemctl stop adsb-web ultrafeeder

# Extract upgrade package
cd /tmp
tar -xzf taknet-ps-complete-v2.27.2-full.tar.gz
cd taknet-ps-complete-v2.27.2-full

# Copy all files
sudo cp web/app.py /opt/adsb/web/
sudo cp web/templates/*.html /opt/adsb/web/templates/
sudo cp web/static/js/*.js /opt/adsb/web/static/js/
sudo cp web/static/css/*.css /opt/adsb/web/static/css/
sudo cp scripts/config_builder.py /opt/adsb/scripts/
sudo cp config/env-template /opt/adsb/config/
sudo cp config/docker-compose.yml /opt/adsb/config/

# Rebuild configuration
sudo python3 /opt/adsb/scripts/config_builder.py

# Restart services
sudo systemctl restart adsb-web
sudo systemctl restart ultrafeeder

# Clear browser cache (Ctrl+Shift+R)
```

---

## 📋 WHAT'S INCLUDED

### Web Application:
- **web/app.py** - Flask application (v2.27.2)
- **web/templates/** - All HTML templates including feeds.html
- **web/static/** - CSS and JavaScript files

### Configuration:
- **config/env-template** - Environment variables template
- **config/docker-compose.yml** - Docker services configuration

### Scripts:
- **scripts/config_builder.py** - Configuration builder
- **install/install.sh** - Main installation script

### Documentation:
- **README.md** - Main documentation
- **CHANGELOG.md** - Version history
- **RELEASE-NOTES-*.md** - Release notes for each version

---

## ✨ KEY FEATURES IN v2.27.2

### 1. Simplified Setup Wizard (3 steps)
- Step 1: SDR Configuration
- Step 2: Location & System Info
- Step 3: Tailscale VPN

### 2. Dedicated Feeds Page
All feed configuration in one place:
- TAKNET-PS Server (with MLAT control)
- FlightRadar24
- Airplanes.Live
- adsb.fi
- adsb.lol

### 3. Clean Settings Page
System configuration only:
- Location settings
- SDR settings
- Tailscale VPN settings

### 4. New Domains
- Primary: secure.tak-solutions.com
- Fallback: adsb.tak-solutions.com

---

## 🌐 ACCESS WEB INTERFACE

After installation:

**Local Access:**
```
http://taknet-ps.local:5001
```

**IP Address:**
```
http://[raspberry-pi-ip]:5001
```

### Default Pages:
- Dashboard: http://taknet-ps.local:5001/
- Feeds: http://taknet-ps.local:5001/feeds
- Settings: http://taknet-ps.local:5001/settings
- Logs: http://taknet-ps.local:5001/logs
- Map: http://taknet-ps.local:5001/map

---

## 🐛 TROUBLESHOOTING

### "Internal Server Error" on /feeds page:
```bash
# Verify feeds route exists
grep "@app.route('/feeds')" /opt/adsb/web/app.py

# If not found, redeploy app.py
sudo cp web/app.py /opt/adsb/web/
sudo systemctl restart adsb-web
```

### Services not starting:
```bash
# Check service status
sudo systemctl status adsb-web
sudo systemctl status ultrafeeder

# View logs
sudo journalctl -u adsb-web -n 50
sudo journalctl -u ultrafeeder -n 50
```

### Wizard not accessible:
```bash
# Check if setup is completed
cat /opt/adsb/config/.setup_complete

# If exists but you want to re-run wizard
sudo rm /opt/adsb/config/.setup_complete
sudo systemctl restart adsb-web
```

---

## 📞 SUPPORT

For issues, questions, or feature requests:
1. Check the documentation in the `docs/` folder
2. Review CHANGELOG.md for known issues
3. Check GitHub issues (if available)

---

## 📄 LICENSE

[Your license information here]

---

**Version:** v2.27.2  
**Release Date:** February 3, 2026  
**Package:** taknet-ps-complete-v2.27.2-full.tar.gz
