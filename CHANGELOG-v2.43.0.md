# TAKNET-PS v2.43.0 Release Notes

**Release Date:** February 9, 2026  
**Type:** Complete Clean Package  
**Status:** Production Ready  

---

## 🎯 What's New in v2.43.0

### Complete ADSBHub Support

**docker-compose.yml:**
- ✅ ADSBHub container definition
- ✅ Uses docker-adsbexchange image
- ✅ Connects to ultrafeeder via Beast protocol
- ✅ Sends to data.adsbhub.org

**env-template:**
- ✅ PIAWARE_ENABLED and PIAWARE_FEEDER_ID variables
- ✅ ADSBHUB_ENABLED and ADSBHUB_STATION_KEY variables

**Web Interface:**
- ✅ ADSBHub configuration page
- ✅ Station key input with validation
- ✅ Enable/disable toggle
- ✅ Modal feedback with auto-dismiss
- ✅ Complete user instructions

---

## 🛠️ Manual Fix Script Included

**fix-adsbhub.sh** - Adds ADSBHub to existing installations

**Features:**
- ✓ Creates backup before modifying files
- ✓ Adds adsbhub service to docker-compose.yml
- ✓ Adds environment variables to .env
- ✓ Validates YAML syntax
- ✓ Downloads Docker image
- ✓ Complete in 2-3 minutes

**Usage:**
```bash
sudo bash fix-adsbhub.sh
```

---

## 📋 Version Consistency

All version references updated to 2.43.0:
- ✓ VERSION file
- ✓ web/app.py (VERSION = "2.43.0")
- ✓ install/install.sh (Installer v2.43.0)
- ✓ README.md
- ✓ CHANGELOG (this file)

---

## 🎯 Supported Feeders (8 Total)

### Accountless Feeds (5)
- TAKNET-PS
- adsb.fi
- adsb.lol
- airplanes.live
- ADSBexchange

### Account-Required Feeds (3)
- FlightRadar24
- FlightAware
- ADSBHub ← NEW in v2.41.4, FIXED in v2.43.0

---

## 🔧 Installation Options

### Option 1: Fresh Install via GitHub

```bash
# 1. Push to GitHub
tar -xzf taknet-ps-complete-v2.43.0-github.tar.gz
cd taknet-ps-complete-v2.43.0-github
git init && git add . && git commit -m "v2.43.0"
git remote add origin https://github.com/cfd2474/feeder_test.git
git push -f origin main

# 2. Install on Pi
curl -fsSL https://raw.githubusercontent.com/cfd2474/feeder_test/main/install/install.sh | sudo bash
```

**Time:** 15-20 minutes  
**Result:** Complete clean installation  

### Option 2: Manual Fix on Existing System

```bash
# Copy fix-adsbhub.sh to Pi
scp fix-adsbhub.sh pi@YOUR_PI:~/

# Run the fix
ssh pi@YOUR_PI
sudo bash fix-adsbhub.sh
```

**Time:** 2-3 minutes  
**Result:** ADSBHub added to existing system  

---

## 🐛 Bug Fixes

### ADSBHub "no such service" Error

**Problem:** Users getting "Failed to start ADSBHub: no such service: adsbhub"

**Root Cause:** docker-compose.yml on Pi missing adsbhub service

**Why:** Installer downloads from GitHub; old GitHub files didn't have adsbhub

**Fix:** 
1. Package includes complete docker-compose.yml with adsbhub ✓
2. Manual fix script adds it directly to existing installations ✓
3. Clear documentation explains the issue ✓

### Missing Environment Variables

**Problem:** env-template missing PIAWARE and ADSBHUB variables

**Fix:** All variables now included in env-template ✓

### FlightAware Modal

**Fixed:** Modal now auto-dismisses after enable/disable (1.5s success, 2s error)

---

## 📦 Package Contents

```
taknet-ps-complete-v2.43.0-github.tar.gz (130 KB)
├── README.md                    ← Complete documentation
├── CHANGELOG-v2.43.0.md        ← This file
├── VERSION                      ← 2.43.0
├── fix-adsbhub.sh              ← Manual fix script
├── install/install.sh           ← Main installer
├── config/docker-compose.yml    ← With adsbhub
├── config/env-template          ← With all variables
├── web/app.py                   ← v2.43.0
├── web/templates/               ← All templates
└── ... (complete system files)
```

---

## ✅ Verification

### Check adsbhub in docker-compose.yml

```bash
grep -c "^  adsbhub:" /opt/adsb/config/docker-compose.yml
# Should output: 1
```

### Check environment variables

```bash
grep -E "PIAWARE|ADSBHUB" /opt/adsb/config/.env
# Should show all 4 variables
```

### Test in web interface

1. Open http://taknet-ps.local
2. Settings → Feed Selection → Account-Required Feeds
3. Enter ADSBHub station key
4. Click "Save & Enable ADSBHub"
5. Success! ✓

---

## 🎯 Timeline

### v2.41.4 (Initial)
- Added ADSBHub support to package
- Users reported "no such service" errors

### v2.41.5-v2.41.7
- Various fixes attempted
- Issue persisted

### v2.41.8
- Complex auto-detection added
- Broke installations (nginx page)

### v2.42.0
- Reverted to simple approach
- Issue still present (GitHub not updated)

### v2.43.0 (Current)
- Complete clean package
- Manual fix script included ✓
- All version numbers consistent ✓
- Comprehensive documentation ✓
- TWO clear installation paths ✓

---

## 📞 Support

**If still getting "no such service: adsbhub" error:**

```bash
# Check what's on your Pi
grep "^  [a-z].*:" /opt/adsb/config/docker-compose.yml

# If adsbhub is missing, run the fix
sudo bash fix-adsbhub.sh
```

---

## ✨ Summary

**Version 2.43.0 is the complete, clean package with:**
- ✅ ADSBHub support fully integrated
- ✅ Manual fix script for existing systems
- ✅ Clear documentation and instructions
- ✅ All version numbers consistent
- ✅ Two installation options
- ✅ Ready to deploy!

**No editing required - everything is configured for cfd2474/feeder_test**

---

**Version:** 2.43.0  
**Build Date:** 2026-02-09  
**Status:** Production Ready  
**Breaking Changes:** None  
**Action Required:** None - Deploy as-is! 🚀
