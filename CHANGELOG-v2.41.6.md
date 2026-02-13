# TAKNET-PS v2.41.6 Release Notes

**Release Date:** February 9, 2026  
**Type:** Bug Fix Release  
**Focus:** FlightAware Modal Auto-Dismiss

---

## 🐛 Bug Fix

### FlightAware Modal Stays Visible After Toggle

**Issue:** When toggling FlightAware feed on/off, the status modal doesn't auto-dismiss - it stays on screen until manually closed.

**Fixed:** Added auto-dismiss timeout to FlightAware toggle function

**Implementation:**
```javascript
if (data.success) {
    updateStatusModal(`FlightAware feed ${statusTextPast} successfully`, 'success');
    // Auto-dismiss after 1.5 seconds
    setTimeout(() => {
        hideStatusModal();
    }, 1500);
}
```

**Now consistent with:**
- FlightRadar24 toggle (auto-dismiss)
- ADSBHub toggle (auto-dismiss)
- All other modal operations

---

## ✨ What's Included from Previous Versions

### From v2.41.5
- ✅ ADSBHub button disabled until key entered
- ✅ ADSBHub toggle validates key
- ✅ ADSBHub Docker pre-download
- ✅ Updated user note with 🛡️

### From v2.41.4
- ✅ ADSBHub feed support
- ✅ Station key configuration

### From v2.41.3
- ✅ WiFi UX improvements
- ✅ Manual WiFi entry

---

## 📦 Files Modified

```
web/templates/feeds-account-required.html
  → Added auto-dismiss to togglePiawareEnabled()
  → Success: 1.5 second timeout
  → Error: 2 second timeout

VERSION
  → Updated to 2.41.6

web/app.py
  → VERSION = "2.41.6"
```

---

## ✅ Verification

Test FlightAware toggle:
1. Go to FlightAware section
2. Toggle feed on/off
3. Modal should show: "Enabling..." → "Enabled successfully!" [✓]
4. Modal auto-dismisses after 1.5 seconds
5. Same for disable: "Disabling..." → "Disabled successfully!" [✓]

---

**Version:** 2.41.6  
**Build Date:** 2026-02-09  
**Status:** Production Ready  
**Breaking Changes:** None  
**Bug Fixes:** FlightAware modal auto-dismiss ✓

**Total Feeders:** 8 (5 accountless + 3 account-required)
