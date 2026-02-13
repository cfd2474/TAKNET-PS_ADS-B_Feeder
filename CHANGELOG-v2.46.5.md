# TAKNET-PS v2.46.5 Release Notes

**Release Date:** February 10, 2026  
**Type:** Bug Fix  
**Previous Version:** v2.46.4

---

## 🐛 Bug Fix

### Dashboard JavaScript Error (Non-Breaking)

**Issue:**
- Console error on dashboard: `TypeError: Cannot set properties of null (setting 'innerHTML')`
- Error occurred in `dashboard.js` line 70 every 10 seconds
- Caused by attempting to update non-existent `active-feeds` element
- **Did not affect functionality** - purely a console error

**Root Cause:**
- `updateStatus()` function tried to update `active-feeds` div
- This element was removed in earlier dashboard redesign
- Feeds now displayed in server-rendered table (`feed-table-body`)
- Legacy code remained that referenced old structure

**Fix Applied:**
```javascript
// Before (Line 68-76):
const feedsContainer = document.getElementById('active-feeds');
if (data.feeds && data.feeds.length > 0) {
    feedsContainer.innerHTML = ...  // Error: feedsContainer is null
}

// After (Line 67-76):
const feedsContainer = document.getElementById('active-feeds');
if (feedsContainer && data.feeds && data.feeds.length > 0) {
    feedsContainer.innerHTML = ...  // Safe: checks for null first
}
```

**Result:**
- ✅ No more console errors
- ✅ Dashboard functions normally
- ✅ Clean browser console

---

## 📦 Files Changed

**web/static/js/dashboard.js:**
- Line 68: Added null check for `feedsContainer`
- Prevents TypeError when element doesn't exist
- No functional changes to dashboard behavior

**VERSION:**
- Updated from 2.46.4 → 2.46.5

---

## ⚙️ Technical Details

**Why This Element Doesn't Exist:**

The current dashboard uses a sophisticated feed status table with:
- Enable/disable status per aggregator
- Real-time data flow indicators (+/-)
- MLAT status indicators (+/-)
- Color-coded health checkmarks
- Server-side rendered via Jinja templates

The old `active-feeds` div was a simple list that has been obsolete since the table-based feed display was implemented.

**Why We Kept the Code:**

Rather than removing the feed update logic entirely, we added a null check. This ensures:
1. No errors if element is missing
2. Forward compatibility if element is added back
3. Minimal code change = minimal risk
4. Clean separation of concerns

---

## 🔄 Upgrade from v2.46.4

**Changes Summary:**
- Single line fix in JavaScript
- No configuration changes
- No database migrations
- No service restarts required
- Safe to skip if v2.46.4 working

**Should You Upgrade?**

**Upgrade if:**
- ✅ Console errors bother you
- ✅ Running monitoring tools that flag JS errors
- ✅ Want a clean console for debugging

**Can skip if:**
- Dashboard working normally
- Not concerned about console errors
- Waiting for next feature release

---

## ✅ Verification

**After upgrade, check:**

1. **Dashboard loads:**
   - Visit dashboard
   - Verify all cards display
   - Check feed table shows correctly

2. **Console clean:**
   - Open browser DevTools (F12)
   - Go to Console tab
   - Wait 10 seconds
   - **Verify:** No "Cannot set properties of null" errors

3. **Auto-refresh works:**
   - Watch container status
   - Should update every 10 seconds
   - No errors in console

---

## 📋 Complete Feature Set (Unchanged)

All v2.46.4 features remain:
- ✅ MLAT stability with CPU frequency lock
- ✅ WiFi hotspot with captive portal
- ✅ Tailscale pre-installed
- ✅ Simplified Tailscale modal
- ✅ WiFi connection progress updates
- ✅ Dashboard network mode detection
- ✅ Smooth modal transitions
- ✅ Auto-closing modals

---

## 🚀 Installation

**New Installation:**
```bash
curl -fsSL https://raw.githubusercontent.com/cfd2474/feeder_test/main/install/install.sh | sudo bash
```

**Verify Version:**
```bash
cat /opt/adsb/VERSION
# Should show: 2.46.5
```

**Manual Verification:**
```bash
# Check for the fix
grep -A 2 "Update feeds" /opt/adsb/web/static/js/dashboard.js
# Should show: if (feedsContainer && data.feeds...
```

---

## 📝 Summary

**What changed:** One line fix in dashboard.js  
**Why:** Prevent console errors from legacy code  
**Impact:** Clean console, no functional changes  
**Urgency:** Low - cosmetic fix only  

**Status:** ✅ Tested, ready to deploy

---

**Previous:** v2.46.4 - Modal UX fixes  
**Current:** v2.46.5 - Dashboard console error fix  
**Next:** TBD
