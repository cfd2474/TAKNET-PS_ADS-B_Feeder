# TAKNET-PS v2.41.3 Release Notes

**Release Date:** February 9, 2026  
**Type:** Bug Fix + UX Enhancement  
**Focus:** WiFi Configuration UX Improvements

---

## 🎯 What's Fixed

### 🐛 Bug Fixes

**1. Manual WiFi Entry for Remote Setup**
- **Problem:** Manual entry tried to connect immediately, failed if network not in range
- **Error:** "No network with SSID 'Network Name' found"
- **Solution:** Manual entry now saves configuration without attempting connection
- **Benefit:** Perfect for pre-configuring devices before deploying to remote sites

**Before:**
```
Manual Entry: "FactoryWiFi" + password
→ System tries to connect
→ Network not in range
→ Error: "No network found"
→ Configuration not saved ✗
```

**After:**
```
Manual Entry: "FactoryWiFi" + password  
→ System saves configuration only
→ Success: "WiFi configuration saved (will connect when in range)"
→ Configuration saved for later ✓
```

---

### ✨ UX Enhancements

**2. Custom Password Modal**
- **Problem:** Browser prompt() was ugly, didn't match interface
- **Solution:** Beautiful custom modal with formatted display
- **Features:**
  - Shows network name prominently
  - Displays signal strength and security type
  - Password visibility toggle
  - Cancel and Connect buttons
  - Enter key support

**Before:**
```
[Browser Prompt]
Enter password for "MyNetwork"

Security: WPA2
Signal: 85%

[    Password field    ]
[ Cancel ]  [ OK ]
```

**After:**
```
╔══════════════════════════════════╗
║  Connect to WiFi Network         ║
╠══════════════════════════════════╣
║  MyHomeWiFi                      ║
║  WPA2 • Signal: 85%              ║
║                                  ║
║  WiFi Password                   ║
║  [●●●●●●●●●●●●●●●●●●] 👁️         ║
║                                  ║
║  [Cancel]  [Connect]             ║
╚══════════════════════════════════╝
```

**3. Status Feedback Modal**
- **Problem:** No feedback during connection/save, user doesn't know what's happening
- **Solution:** Real-time status modal with spinner and clear messages
- **Shows:**
  - "Connecting to WiFi network..." with spinner
  - "Saving WiFi configuration..." with spinner  
  - "Connected successfully!" with ✓ (auto-dismiss 2s)
  - "WiFi configuration saved!" with ✓ (auto-dismiss 2s)
  - Error messages with ✗ (auto-dismiss 3s)

**Status Flow:**
```
Scan Selection:
1. Enter password in modal
2. Click "Connect"
3. Show: "Connecting to WiFi network..." [spinner]
4. Show: "Connected successfully!" [✓]
5. Auto-dismiss, network appears in saved list

Manual Entry:
1. Enter SSID + password
2. Click "Add Network"
3. Show: "Saving WiFi configuration..." [spinner]
4. Show: "WiFi configuration saved (will connect when in range)" [✓]
5. Auto-dismiss, configuration appears in saved list

Remove Network:
1. Click "Remove" button
2. Confirm removal
3. Show: "Removing WiFi network..." [spinner]
4. Show: "WiFi network removed successfully!" [✓]
5. Auto-dismiss, network disappears from list
```

---

## 🔧 Technical Implementation

### Backend Changes

**Modified:** `web/app.py`

**Updated `/api/wifi/add` Endpoint:**

Added `saveOnly` parameter to control behavior:
- `saveOnly: false` (default) - Try to connect immediately (scan selection)
- `saveOnly: true` - Save configuration without connecting (manual entry)

**Implementation:**

```python
save_only = data.get('saveOnly', False)

if save_only:
    # Just create connection profile without connecting
    # Uses: nmcli connection add (not dev wifi connect)
    # Result: "WiFi configuration saved (will connect when in range)"
else:
    # Try to connect immediately
    # Uses: nmcli dev wifi connect
    # Result: "Connected to WiFi network successfully"
```

**nmcli Commands:**

```bash
# Save only (manual entry - remote setup)
sudo nmcli connection add \
  type wifi \
  con-name "FactoryWiFi" \
  ifname wlan0 \
  ssid "FactoryWiFi" \
  -- \
  wifi-sec.key-mgmt wpa-psk \
  wifi-sec.psk "password123"

# Connect immediately (scan selection)
sudo nmcli dev wifi connect "MyNetwork" password "password123"
```

**Fallback Support:**
- wpa_supplicant method also updated
- Saves configuration to wpa_supplicant.conf
- Restarts wpa_cli service
- Works on older Raspberry Pi OS versions

---

### Frontend Changes

**Modified:** `web/templates/settings.html`

**Added CSS:**
```css
/* WiFi Status Modal Styles */
.status-modal .modal-content { ... }
.status-spinner { 
    animation: spin 1s linear infinite;
}
.status-icon { font-size: 60px; }
.status-message { ... }
```

**Added HTML Modals:**

1. **WiFi Password Modal** - Custom password entry
2. **WiFi Status Modal** - Progress feedback with spinner

**Added JavaScript Functions:**

| Function | Purpose |
|----------|---------|
| `showWifiStatus(message, showSpinner)` | Display status modal |
| `hideWifiStatus()` | Hide status modal |
| `showWifiSuccess(message)` | Show success with ✓ |
| `showWifiError(message)` | Show error with ✗ |
| `closeWifiPasswordModal()` | Close password modal |
| `toggleWifiModalPassword()` | Show/hide password |
| `confirmWifiPassword()` | Submit password |

**Updated Functions:**

| Function | Change |
|----------|--------|
| `selectWifiNetwork()` | Opens custom modal instead of prompt() |
| `addWifiNetwork()` | Added saveOnly parameter, shows status |
| `addManualWifiNetwork()` | Uses saveOnly=true, shows status |
| `removeWifiNetwork()` | Shows status instead of alerts |

**Keyboard Support:**
- Enter key in password modal → Submit
- Enter key in manual SSID → Focus password
- Enter key in manual password → Submit form

---

## 🎬 User Experience Comparison

### Scenario 1: Connect to Visible Network

**v2.41.2 (Before):**
```
1. Click network
2. See browser prompt
3. Enter password
4. Click OK
5. [Wait silently...]
6. Network appears several seconds later
   (User doesn't know what happened)
```

**v2.41.3 (After):**
```
1. Click network
2. See beautiful modal with network info
3. Enter password (with visibility toggle)
4. Click Connect or press Enter
5. See "Connecting to WiFi network..." with spinner
6. See "Connected successfully!" with ✓
7. Auto-dismiss, network appears in saved list
   (User knows exactly what happened)
```

---

### Scenario 2: Pre-configure for Remote Site

**v2.41.2 (Before):**
```
1. Toggle to Manual Entry
2. Enter "FactoryWiFi"
3. Enter password
4. Click "Add Network"
5. Error: "No network with SSID 'FactoryWiFi' found"
6. Configuration NOT saved ✗
   (Feature completely broken)
```

**v2.41.3 (After):**
```
1. Toggle to Manual Entry
2. Enter "FactoryWiFi"  
3. Enter password
4. Click "Add Network" or press Enter
5. See "Saving WiFi configuration..." with spinner
6. See "WiFi configuration saved (will connect when in range)" with ✓
7. Configuration appears in saved list
   (Works perfectly for remote setup!)
```

---

### Scenario 3: Remove Network

**v2.41.2 (Before):**
```
1. Click Remove
2. Confirm
3. Browser alert: "✓ WiFi network removed"
4. Click OK
5. Network disappears
```

**v2.41.3 (After):**
```
1. Click Remove
2. Confirm
3. See "Removing WiFi network..." with spinner
4. See "WiFi network removed successfully!" with ✓
5. Auto-dismiss, network disappears
   (Smoother, no extra click needed)
```

---

## 📊 Before vs After

| Aspect | v2.41.2 | v2.41.3 |
|--------|---------|---------|
| **Manual entry** | Tries to connect, fails if not in range | Saves config without connecting |
| **Password input** | Browser prompt (ugly) | Custom modal (beautiful) |
| **Connection feedback** | Silent, no status | Spinner + clear messages |
| **Success feedback** | Alert (requires click) | Auto-dismiss status modal |
| **Error feedback** | Alert (requires click) | Auto-dismiss status modal |
| **Keyboard support** | None | Enter key throughout |
| **Remote setup** | Broken ✗ | Works perfectly ✓ |

---

## ✅ Verification

After installation/update:

### Test 1: Manual Entry (Remote Setup)
```bash
# 1. Go to Settings → WiFi Configuration
# 2. Toggle to "Manual entry (for remote sites)"
# 3. Enter SSID: "TestNetwork99" (doesn't exist)
# 4. Enter password: "test123"
# 5. Click "Add Network"
# 6. Should see: "Saving WiFi configuration..."
# 7. Should see: "WiFi configuration saved (will connect when in range)"
# 8. Should appear in Configured Networks list
# SUCCESS: Configuration saved even though network not in range!
```

### Test 2: Custom Password Modal
```bash
# 1. Go to Settings → WiFi Configuration  
# 2. Click "Scan WiFi Networks"
# 3. Click any network from results
# 4. Should see: Beautiful modal (not browser prompt)
# 5. Should show: Network name, signal, security
# 6. Should have: Password visibility toggle
# 7. Press Enter or click Connect
# 8. Should see: Status modal with spinner
# SUCCESS: Custom modal looks professional!
```

### Test 3: Status Feedback
```bash
# 1. Add network (scan or manual)
# 2. Should immediately see status modal
# 3. Should show spinner while processing
# 4. Should show success/error message
# 5. Should auto-dismiss
# 6. Should NOT require clicking OK
# SUCCESS: Clear feedback throughout!
```

---

## 🐛 Bug Status

| Issue | Status | Fix |
|-------|--------|-----|
| Manual entry fails for remote setup | ✅ Fixed | Added saveOnly mode |
| Ugly browser prompt | ✅ Fixed | Custom modal |
| No connection feedback | ✅ Fixed | Status modal with spinner |
| Silent success/failure | ✅ Fixed | Auto-dismiss notifications |

---

## 📦 Files Modified

```
web/app.py
  → Updated /api/wifi/add endpoint
  → Added saveOnly parameter
  → Different behavior for scan vs manual

web/templates/settings.html
  → Added WiFi password modal HTML
  → Added WiFi status modal HTML
  → Added CSS for modals and spinner
  → Updated JavaScript functions
  → Added keyboard event listeners
```

---

## 🎯 What's Included from Previous Versions

### From v2.41.2
- ✅ WiFi configuration in Settings tab
- ✅ Network scanning
- ✅ Manual SSID entry
- ✅ Saved networks management

### From v2.41.1
- ✅ "Enable All" button for feeds
- ✅ Popup feedback improvements

### From v2.41.0
- ✅ Docker image pre-download
- ✅ FlightAware MLAT docs

---

## 💡 Usage Tips

**For On-Site Setup:**
1. Use "Scan for networks" mode
2. Click network → Enter password → Done!
3. Status shows connection progress
4. Success notification confirms connection

**For Remote Setup:**
1. Use "Manual entry (for remote sites)" mode
2. Enter SSID and password for destination site
3. Status shows "Saving configuration..."
4. Success: "Will connect when in range"
5. Deploy device to site, auto-connects!

**Keyboard Shortcuts:**
- Password modal: Enter to connect
- Manual SSID: Enter to jump to password
- Manual password: Enter to submit

---

## 📞 Support

**Fixed Issues:**
- Manual WiFi entry for remote sites
- Professional password entry UI
- Real-time status feedback
- Auto-dismiss success messages

**Troubleshooting:**
```bash
# Test manual entry saves config
sudo nmcli connection show

# Should see saved connections even if not connected
# Look for your manually entered SSIDs
```

---

**Version:** 2.41.3  
**Build Date:** 2026-02-09  
**Status:** Production Ready  
**Breaking Changes:** None  
**Bug Fixes:** Manual WiFi entry, UX improvements ✨
