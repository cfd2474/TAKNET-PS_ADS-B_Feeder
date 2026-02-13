# TAKNET-PS v2.46.0 - MLAT Stability & UX Improvements

## 🎯 What's New

**Zero-Configuration MLAT Stability** - The installer now automatically prevents FlightAware "clock unstable" errors!

---

## ✨ Key Features

### 1. Automatic MLAT Safeguards

The installer now **automatically configures** everything needed for stable MLAT:

- ✅ **CPU frequency locked** (force_turbo=1)
- ✅ **Performance governor** enabled
- ✅ **NTP time sync** configured
- ✅ **USB power management** optimized
- ✅ **All settings persist** across reboots

**Result:** MLAT works perfectly from first boot, no manual fixes needed!

---

### 2. Improved Setup Wizard

**Clearer feeder name instructions:**
- Removed confusing zip code example
- Added clear explanation of zip code prefix behavior
- Explained IP-based zip code detection
- Clarified purpose of zip codes

---

## 📦 Installation

### Fresh Installation (Recommended)

```bash
curl -fsSL https://raw.githubusercontent.com/cfd2474/feeder_test/main/install/install.sh | sudo bash
```

**That's it!** MLAT stability is automatic.

---

**Version:** 2.46.0  
**Release Date:** 2026-02-09  
**MLAT Stability:** Automatic! 🎉

See CHANGELOG-v2.46.0.md for complete details.
