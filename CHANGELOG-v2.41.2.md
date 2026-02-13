# TAKNET-PS v2.41.2 Release Notes

**Release Date:** February 9, 2026  
**Type:** Feature Release  
**Focus:** WiFi Configuration Management

---

## 🎯 What's New

### 📶 WiFi Configuration in Settings Tab

**Complete WiFi management directly from the Settings page!**

Users can now:
- 🔍 **Scan for available WiFi networks** - See all visible networks with signal strength
- ➕ **Add networks from scan results** - Click any network, enter password, done
- ✍️ **Manually enter SSIDs** - Pre-configure networks for remote deployment sites
- 📋 **View configured networks** - See all saved WiFi configurations
- 🗑️ **Remove networks** - Delete unwanted WiFi configurations

---

## ✨ Key Features

### 1. Network Scanning

**Scan Button:**
- Click "🔍 Scan WiFi Networks"
- Displays all visible networks
- Shows signal strength (📶 Strong, 📱 Weak, 📉 Very Weak)
- Shows security type (WPA2, WPA, WEP, Open)
- Sorted by signal strength (best first)

**Network Display:**
```
MyHomeWiFi                    📶
Signal: 85% • WPA2

Office_Guest                  📶  
Signal: 72% • WPA2

Neighbors_Network             📱
Signal: 45% • WPA2
```

**Click any network** → Enter password → Added!

---

### 2. Manual Network Entry

**For Remote Sites:**
- Toggle to "Manual entry (for remote sites)"
- Enter SSID that's not currently in range
- Enter password
- Select security type (WPA2/WPA3, WPA, WEP, Open)
- Click "➕ Add Network"

**Use Cases:**
- Pre-configure before deploying to remote location
- Add hidden networks
- Configure while preparing device offline

---

### 3. Saved Networks Management

**Configured Networks Section:**
- Shows all saved WiFi configurations
- Displays connection status (✓ Connected / Configured)
- Shows security type
- **Remove button** for each network

**Example Display:**
```
Configured Networks
━━━━━━━━━━━━━━━━━━━━━━━━━━━

HomeNetwork                    🗑️ Remove
✓ Connected • WPA2

Office_Secure                  🗑️ Remove
Configured • WPA2

Backup_Hotspot                 🗑️ Remove
Configured • WPA2
```

---

### 4. User Interface

**Location:** Settings tab → New "📶 WiFi Configuration" section

**Layout:**
1. **Configured Networks** (top)
   - List of saved networks
   - Remove buttons

2. **Add New Network** (bottom)
   - Toggle: Scan vs Manual
   - Scan section with results
   - Manual entry form

**Smart Features:**
- Password visibility toggle (👁️)
- Security type auto-detection for scanned networks
- Signal strength indicators
- Sorted by signal strength
- Duplicate detection

---

## 🔧 Technical Implementation

### Frontend Changes

**Modified:** `web/templates/settings.html`

**Added HTML Section:**
- WiFi Configuration card with two tabs
- Saved networks list (dynamic)
- Scan/Manual toggle
- Available networks display
- Manual entry form
- Remove buttons for each network

**Added JavaScript Functions:**
```javascript
toggleWifiInputMode()          - Switch scan/manual modes
loadSavedWifiNetworks()        - Load configured networks
scanWifiNetworks()             - Scan for available networks
selectWifiNetwork()            - Handle network selection
addWifiNetwork()               - Add network (scan selection)
addManualWifiNetwork()         - Add network (manual entry)
removeWifiNetwork()            - Remove saved network
togglePasswordVisibility()      - Show/hide password
```

---

### Backend Changes

**Modified:** `web/app.py`

**Added API Endpoints:**

#### 1. `GET /api/wifi/scan`
Scans for available WiFi networks

**Returns:**
```json
{
  "success": true,
  "networks": [
    {
      "ssid": "MyNetwork",
      "signal": 85,
      "security": "WPA2"
    }
  ]
}
```

**Implementation:**
- Uses `nmcli` (NetworkManager CLI) on modern Raspberry Pi OS
- Falls back to `iwlist scan` if nmcli unavailable
- Parses output and returns sorted list
- Top 20 networks by signal strength
- 30 second timeout

#### 2. `GET /api/wifi/saved`
Lists saved WiFi network configurations

**Returns:**
```json
{
  "success": true,
  "networks": [
    {
      "ssid": "HomeNetwork",
      "connected": true,
      "security": "WPA2"
    }
  ]
}
```

**Implementation:**
- Uses `nmcli connection show` for saved connections
- Falls back to parsing `/etc/wpa_supplicant/wpa_supplicant.conf`
- Shows connection status for each network

#### 3. `POST /api/wifi/add`
Adds a new WiFi network configuration

**Request:**
```json
{
  "ssid": "NetworkName",
  "password": "password123",
  "security": "WPA2"
}
```

**Returns:**
```json
{
  "success": true,
  "message": "WiFi network added successfully"
}
```

**Implementation:**
- Uses `nmcli dev wifi connect` for adding networks
- Falls back to editing wpa_supplicant.conf
- Supports open networks (no password)
- Automatically connects to network
- Restarts wpa_supplicant service

#### 4. `POST /api/wifi/remove`
Removes a WiFi network configuration

**Request:**
```json
{
  "ssid": "NetworkName"
}
```

**Returns:**
```json
{
  "success": true,
  "message": "WiFi network removed successfully"
}
```

**Implementation:**
- Uses `nmcli connection delete` to remove
- Falls back to manual editing of wpa_supplicant.conf
- Removes entire network block for SSID
- Restarts wpa_supplicant service

---

## 🎬 Usage Examples

### Example 1: Add Home WiFi

```
1. Go to Settings tab
2. Scroll to "WiFi Configuration"
3. Click "🔍 Scan WiFi Networks"
4. Wait 10-15 seconds for scan
5. See list of available networks
6. Click "HomeNetwork_5G" (85% signal)
7. Enter password in prompt
8. Click OK
9. Success! Network added and connected
```

---

### Example 2: Pre-Configure for Remote Site

```
1. Go to Settings tab
2. WiFi Configuration section
3. Toggle to "Manual entry (for remote sites)"
4. Enter SSID: "FactoryFloor_WiFi"
5. Enter password: "factory2024!"
6. Select security: "WPA2/WPA3 (Recommended)"
7. Click "➕ Add Network"
8. Success! Network configured (will connect when in range)
```

---

### Example 3: Remove Old Network

```
1. Go to Settings tab
2. WiFi Configuration → Configured Networks
3. See "OldOffice_WiFi" in list
4. Click "🗑️ Remove" button
5. Confirm removal
6. Success! Network removed
```

---

## 📊 Platform Compatibility

**Supported Systems:**
- Raspberry Pi OS (Bookworm) - Uses nmcli ✅
- Raspberry Pi OS (Bullseye) - Uses nmcli ✅
- Raspberry Pi OS (Buster) - Falls back to wpa_supplicant ✅
- Older systems - Uses wpa_supplicant fallback ✅

**Network Managers:**
- NetworkManager (nmcli) - Primary method
- wpa_supplicant - Fallback method
- Both methods fully supported

**WiFi Interfaces:**
- wlan0 (built-in) ✅
- wlan1 (USB adapter) ✅
- Other interfaces - Auto-detected

---

## 🔐 Security

**Password Handling:**
- Passwords stored in system WiFi configuration
- Not accessible via web interface after saving
- Standard Linux WiFi security applies
- Password visibility toggle for convenience

**Permissions:**
- Requires sudo for network modifications
- Web service runs with appropriate permissions
- Network configuration files properly secured

---

## 🚀 Installation

**Included in fresh installations:**
```bash
curl -fsSL https://raw.githubusercontent.com/USERNAME/taknet-ps/main/install/install.sh | sudo bash
```

WiFi configuration automatically available in Settings tab!

---

## ✅ Verification

After installation/update:

```bash
# 1. Open web interface
# Visit: http://taknet-ps.local/settings

# 2. Scroll to WiFi Configuration section
# Should see new card with "📶 WiFi Configuration"

# 3. Test scan
# Click "🔍 Scan WiFi Networks"
# Should see available networks after 10-15 seconds

# 4. Test manual entry
# Toggle to "Manual entry"
# Should see SSID/password form

# 5. Test saved networks
# Should see "Configured Networks" list at top
```

---

## 💡 FAQ

### Q: Can I configure WiFi before connecting to the device?
**A:** Yes! Use manual entry to pre-configure networks. The device will connect when in range.

### Q: What if my network is hidden?
**A:** Use manual entry mode. Hidden networks won't appear in scan results.

### Q: Can I add multiple networks?
**A:** Yes! Add as many as you need. The device will automatically connect to the strongest available network.

### Q: What if scan doesn't find my network?
**A:** 1) Make sure you're in range, 2) Try scanning again, 3) Use manual entry as fallback.

### Q: Can I change network priority?
**A:** Currently networks are prioritized by signal strength automatically. Manual priority coming in future update.

### Q: What happens if I remove the connected network?
**A:** The device will disconnect and try to connect to another saved network if available.

### Q: Does this work with both 2.4GHz and 5GHz networks?
**A:** Yes! Both frequencies are supported (if your WiFi hardware supports them).

---

## 🐛 Bug Fixes

No bugs fixed in this release - pure feature addition!

---

## 📦 Files Modified

```
web/templates/settings.html         (added WiFi configuration section)
  → Added HTML for WiFi management UI
  → Added JavaScript functions for WiFi operations
  
web/app.py                           (added WiFi API endpoints)
  → Added /api/wifi/scan endpoint
  → Added /api/wifi/saved endpoint
  → Added /api/wifi/add endpoint
  → Added /api/wifi/remove endpoint
  → NetworkManager and wpa_supplicant support
```

---

## 🎯 What's Included from Previous Versions

### From v2.41.1
- ✅ "Enable All" button for accountless feeds
- ✅ Popup feedback for FlightAware setup
- ✅ Popup feedback for FR24 setup

### From v2.41.0
- ✅ Docker image pre-download during installation
- ✅ FlightAware MLAT timing notice
- ✅ Location verification instructions

### Core Features
- ✅ Complete ADS-B feeder system
- ✅ Web-based configuration
- ✅ Multiple feed support
- ✅ Tailscale VPN integration
- ✅ tar1090 map interface

---

## 📞 Support

**New Feature:** WiFi Configuration  
**Location:** Settings tab  
**Documentation:** This changelog + README.md

**Troubleshooting:**
```bash
# Check WiFi hardware
iwconfig

# Check NetworkManager status
systemctl status NetworkManager

# Check wpa_supplicant status  
systemctl status wpa_supplicant

# Manual scan test
sudo nmcli dev wifi list

# Check logs
journalctl -u adsb-web.service -n 100
```

---

**Version:** 2.41.2  
**Build Date:** 2026-02-09  
**Status:** Production Ready  
**Breaking Changes:** None  
**New Feature:** WiFi Configuration ✨
