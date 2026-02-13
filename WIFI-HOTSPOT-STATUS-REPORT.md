# WiFi Hotspot & Captive Portal - Status Report

## 🔍 Current Status: **MOSTLY WORKING** ⚠️

The automatic WiFi hotspot with captive portal functionality IS present in v2.46.0, but there's a **critical bug** that needs to be fixed.

---

## ✅ What's Working

### 1. **WiFi Hotspot Manager** ✓

**Location:** `/opt/adsb/wifi-manager/`

**Components Installed:**
- ✅ `check-connection.sh` - Checks internet connectivity
- ✅ `start-hotspot.sh` - Starts hotspot mode
- ✅ `stop-hotspot.sh` - Stops hotspot and starts WiFi
- ✅ `network-monitor.sh` - Background monitoring process

---

### 2. **Captive Portal** ✓

**Location:** `/opt/adsb/captive-portal/`

**Features:**
- ✅ WiFi network scanning (`iwlist wlan0 scan`)
- ✅ Network selection interface
- ✅ Password input for secured networks
- ✅ Configuration saved to `/etc/wpa_supplicant/wpa_supplicant.conf`
- ✅ Automatic reboot after configuration
- ✅ Captive portal detection for Android/iOS/Windows

**Captive Portal Routes:**
- ✅ `/` - Main configuration page
- ✅ `/generate_204` - Android detection
- ✅ `/hotspot-detect.html` - iOS detection
- ✅ `/connecttest.txt` - Windows detection
- ✅ `/api/scan` - AJAX WiFi scan
- ✅ `/api/connect` - AJAX WiFi connection

**Runs on:** Port 8888  
**DNS Hijacking:** All DNS queries → 192.168.4.1  
**HTTP Redirect:** All HTTP → 192.168.4.1:8888

---

### 3. **Background Monitoring** ✓

**Service:** `network-monitor.service`

**Monitoring Logic:**
1. ✅ Waits 60 seconds after boot for stabilization
2. ✅ Checks connectivity every 30 seconds when connected
3. ✅ Checks every 10 seconds when in hotspot mode
4. ✅ Checks every 10 seconds when WiFi is retrying

**States:**
- `connected` - Internet available
- `wifi_retry` - WiFi configured but not connected (5-minute timeout)
- `hotspot` - Hotspot mode active

**Behavior:**
```
┌─────────────────────────────────────┐
│  Boot / Start                       │
└────────────┬────────────────────────┘
             │
             v
   ┌─────────────────────┐
   │ Check Connection    │
   └─────────┬───────────┘
             │
      ┌──────┴──────┐
      │             │
      v             v
   Internet?     No Internet?
      │             │
      │             v
      │      WiFi Configured?
      │             │
      │       ┌─────┴─────┐
      │       │           │
      │      Yes         No
      │       │           │
      │       v           v
      │   Wait 5 min   Start Hotspot
      │       │           │
      │       v           │
      │   Connected?      │
      │       │           │
      │    ┌──┴──┐        │
      │    │     │        │
      │   Yes   No        │
      │    │     │        │
      v    v     v        v
   Connected  Hotspot  Hotspot
      │         │        │
      └─────────┴────────┘
             │
             v
      Continue Monitoring
```

---

### 4. **Hotspot Configuration** ✓

**SSID:** `TAKNET-PS.local`  
**Password:** None (open network)  
**IP Range:** 192.168.4.1/24  
**DHCP:** 192.168.4.2 - 192.168.4.20  
**Channel:** 6  
**Mode:** 802.11g

**DNS Configuration:**
- Wildcard: All domains → 192.168.4.1
- Android: `connectivitycheck.gstatic.com` → 192.168.4.1
- iOS: `captive.apple.com` → 192.168.4.1
- Windows: `msftconnecttest.com` → 192.168.4.1
- Firefox: `detectportal.firefox.com` → 192.168.4.1

---

## 🐛 **CRITICAL BUG FOUND**

### Problem: wpa_supplicant Masked on Installation

**Location:** `install/install.sh` line 1031

```bash
# Mask wpa_supplicant to prevent conflicts
systemctl mask wpa_supplicant 2>/dev/null || true
```

**Impact:**

1. ✅ Fresh install → wpa_supplicant is **masked**
2. ✅ No WiFi config → Hotspot starts (works correctly)
3. ✅ User configures WiFi via captive portal
4. ✅ System reboots
5. ❌ **wpa_supplicant is still masked** → Won't start automatically
6. ❌ network-monitor detects WiFi config exists
7. ❌ Waits 5 minutes expecting connection
8. ❌ Connection never happens (wpa_supplicant not running!)
9. ❌ After 5 minutes → Goes back to hotspot mode
10. ❌ **User is stuck in a loop!**

---

### Why This Happens

**The Logic:**
- `wpa_supplicant` is masked to prevent conflicts with network-monitor
- When hotspot stops, `stop-hotspot.sh` unmasks wpa_supplicant
- **BUT** the first boot after WiFi config, hotspot hasn't been stopped yet!
- So wpa_supplicant is still masked and can't connect

**Root Cause:**
The assumption was that after configuring WiFi and rebooting, the system would:
1. Detect WiFi config exists
2. wpa_supplicant would auto-start (but it's masked!)
3. Connection would succeed

**What Actually Happens:**
1. Detect WiFi config exists
2. wpa_supplicant is masked → doesn't start
3. No connection possible
4. Timeout → back to hotspot

---

## 🔧 Required Fix

### Solution 1: Don't Mask wpa_supplicant Initially (Recommended)

**Change line 1031 in install/install.sh:**

```bash
# OLD (buggy):
systemctl mask wpa_supplicant 2>/dev/null || true

# NEW (fixed):
# Don't mask wpa_supplicant - network-monitor will manage it
systemctl disable wpa_supplicant 2>/dev/null || true
```

**Why this works:**
- `disable` prevents auto-start, but allows manual start
- network-monitor can start/stop it as needed
- After WiFi config + reboot, network-monitor can start wpa_supplicant

---

### Solution 2: Unmask in WiFi Retry Logic

**Add to network-monitor.sh before wifi_retry state:**

```bash
1)
    # WiFi configured but not connected - RETRY LOGIC
    CURRENT_STATE=$(cat "$STATE_FILE" 2>/dev/null || echo "unknown")
    
    # ENSURE WPA_SUPPLICANT IS UNMASKED AND RUNNING
    systemctl unmask wpa_supplicant 2>/dev/null || true
    systemctl enable wpa_supplicant 2>/dev/null || true  
    systemctl restart wpa_supplicant 2>/dev/null || true
    
    if [ "$CURRENT_STATE" = "wifi_retry" ]; then
        # Already retrying, check elapsed time
        ...
```

**Why this works:**
- When WiFi config is detected, immediately unmask and start wpa_supplicant
- Gives wpa_supplicant 5 minutes to connect
- If it fails, then go to hotspot

---

### Solution 3: Unmask During WiFi Configuration

**Change captive portal connect_wifi function:**

```python
def connect_wifi(ssid, password=''):
    """Configure WiFi connection"""
    try:
        # ... configure wpa_supplicant.conf ...
        
        # Unmask and enable wpa_supplicant BEFORE rebooting
        subprocess.run(['systemctl', 'unmask', 'wpa_supplicant'], check=False)
        subprocess.run(['systemctl', 'enable', 'wpa_supplicant'], check=False)
        subprocess.Popen(['bash', '-c', 'sleep 5 && reboot'])
        return True
```

**Why this works:**
- WiFi is configured
- wpa_supplicant is unmasked before reboot
- After reboot, wpa_supplicant can auto-start
- Connection can succeed

---

## 📊 Recommended Fix: **Solution 1** (Simplest)

**Change one line in install.sh:**

```bash
# Line 1031
# BEFORE:
systemctl mask wpa_supplicant 2>/dev/null || true

# AFTER:  
systemctl disable wpa_supplicant 2>/dev/null || true
```

**Testing Required:**
1. Fresh install on Raspberry Pi
2. Boot → hotspot should start (no internet, no WiFi config)
3. Connect to TAKNET-PS.local
4. Configure WiFi via captive portal
5. System reboots
6. **wpa_supplicant should start and connect**
7. Verify internet access
8. Verify hotspot stopped

**Expected Result:**
- ✅ WiFi connects successfully
- ✅ No more hotspot loop
- ✅ Background monitoring continues
- ✅ If WiFi fails later, hotspot starts again

---

## 📋 Current Files Status

### Files Present in v2.46.0:

**Scripts:**
- ✅ `/opt/adsb/wifi-manager/check-connection.sh`
- ✅ `/opt/adsb/wifi-manager/start-hotspot.sh`
- ✅ `/opt/adsb/wifi-manager/stop-hotspot.sh`
- ✅ `/opt/adsb/wifi-manager/network-monitor.sh`
- ✅ `/opt/adsb/captive-portal/portal.py`

**Services:**
- ✅ `/etc/systemd/system/network-monitor.service`
- ✅ `/etc/systemd/system/captive-portal.service`

**Config:**
- ✅ `/etc/hostapd/hostapd.conf`
- ✅ `/etc/dnsmasq.conf` (created by start-hotspot.sh)
- ✅ `/etc/wpa_supplicant/wpa_supplicant.conf` (created by captive portal)

**Templates:**
- ✅ `/opt/adsb/captive-portal/templates/portal.html`
- ⚠️ `/opt/adsb/wifi-manager/templates/wifi-setup.html` (downloaded from GitHub)

**State Files:**
- `/var/run/network-monitor-state` (runtime state)
- `/var/run/wifi-retry-start` (retry timer)
- `/var/log/network-monitor.log` (monitoring log)

---

## 🎯 Test Plan (After Fix)

### Test Case 1: Fresh Install, No Internet, No WiFi

**Setup:** Fresh Pi, no Ethernet, no WiFi configured

**Expected:**
1. Boot completes
2. After 60 seconds, network-monitor detects no internet
3. Hotspot starts: TAKNET-PS.local
4. Captive portal active on 192.168.4.1:8888
5. User can connect and configure WiFi

**Status:** ✅ Should work (existing behavior)

---

### Test Case 2: Configure WiFi via Captive Portal

**Setup:** Connected to hotspot, user configures WiFi

**Expected:**
1. User scans WiFi networks
2. Selects network, enters password
3. Config saved to wpa_supplicant.conf
4. **wpa_supplicant is unmasked**
5. System reboots
6. After boot, wpa_supplicant starts
7. Connects to configured WiFi
8. network-monitor detects internet
9. Hotspot stops
10. Normal operation resumes

**Status:** ❌ Currently broken (wpa_supplicant masked)  
**After Fix:** ✅ Should work

---

### Test Case 3: WiFi Connection Lost

**Setup:** Running normally with WiFi connection

**Expected:**
1. WiFi connection drops (router off, out of range, etc.)
2. network-monitor detects no internet
3. Waits 5 minutes for reconnection
4. If no reconnection, starts hotspot
5. User can reconfigure WiFi

**Status:** ❌ Partially broken (if wpa_supplicant gets masked somehow)  
**After Fix:** ✅ Should work

---

### Test Case 4: Ethernet as Backup

**Setup:** WiFi fails, but Ethernet is connected

**Expected:**
1. WiFi fails to connect
2. network-monitor detects internet via Ethernet
3. Hotspot does NOT start
4. Normal operation continues on Ethernet

**Status:** ✅ Should work (existing behavior)

---

### Test Case 5: Bad WiFi Password

**Setup:** User enters wrong password via captive portal

**Expected:**
1. Config saved with bad password
2. System reboots
3. wpa_supplicant starts but can't authenticate
4. Waits 5 minutes
5. No connection → starts hotspot again
6. User can try again with correct password

**Status:** ❌ Currently broken (wpa_supplicant masked)  
**After Fix:** ✅ Should work

---

## 📝 Summary

### What's Working ✅
- WiFi hotspot creation
- Captive portal web interface
- WiFi network scanning
- Password configuration
- DNS hijacking for captive portal detection
- Background monitoring service
- Internet connectivity checking
- Automatic hotspot start when no internet

### What's Broken ❌
- **wpa_supplicant is masked** → WiFi can't connect after configuration
- Users get stuck in hotspot loop

### The Fix 🔧
**One line change in install.sh:**
```bash
# Line 1031
systemctl disable wpa_supplicant 2>/dev/null || true  # instead of 'mask'
```

### Next Steps 🚀
1. Apply the fix to install.sh
2. Increment version to v2.46.1
3. Test on fresh Raspberry Pi
4. Verify WiFi connection works
5. Verify hotspot fallback works
6. Deploy to GitHub

---

## 🎯 Conclusion

The WiFi hotspot with captive portal functionality **IS implemented** and **MOSTLY works**, but has a critical bug that prevents WiFi connection after initial configuration.

**The bug is easy to fix** (one line change) and has been identified.

After the fix:
- ✅ Fresh install → Hotspot mode
- ✅ User configures WiFi → Connects successfully
- ✅ WiFi fails → Hotspot mode
- ✅ Ethernet available → No hotspot needed
- ✅ Background monitoring → Always running

**Ready to fix and deploy!** 🚀

---

**Document Version:** 1.0  
**Date:** 2026-02-09  
**Package:** v2.46.0  
**Issue:** wpa_supplicant masked bug  
**Fix Status:** Identified, ready to implement
