# TAKNET-PS v2.41.4 Release Notes

**Release Date:** February 9, 2026  
**Type:** Feature Release  
**Focus:** ADSBHub Feed Support

---

## 🎯 What's New

### 📡 ADSBHub Feed Support

**New account-required feeder added!**

Join the ADSBHub community network and share your ADS-B data with researchers, developers, and aviation enthusiasts worldwide.

**Features:**
- ✅ Station key configuration
- ✅ Enable/disable toggle
- ✅ Status monitoring
- ✅ Consistent UX with FR24 and FlightAware
- ✅ Docker container management

---

## ✨ ADSBHub Configuration

### Access

**Settings Page:**
Settings → Feed Selection → Account-Required Feeds → ADSBHub

**Card Layout:**
```
╔═══════════════════════════════════╗
║ ADSBHub              [Active]     ║
║ Share your ADS-B data with the    ║
║ ADSBHub community network         ║
╠═══════════════════════════════════╣
║ ☑ Enable ADSBHub Feed             ║
║ Toggle to start/stop feeding      ║
║───────────────────────────────────║
║ ADSBHub Station Key               ║
║ [Enter your station key    ]      ║
║                                   ║
║ [Save & Enable ADSBHub]           ║
╚═══════════════════════════════════╝
```

---

### Setup Process

**Step 1: Get Your Station Key**

1. Visit [ADSBHub How to Feed](https://www.adsbhub.org/howtofeed.php)
2. Sign up for a new station or log in
3. Configure your station:
   - **Feeder Type:** Linux
   - **Mode:** Client
   - **Protocol:** SBS
4. Your station key will be provided
5. Existing users: Find key on Settings page

**Step 2: Configure in TAKNET-PS**

1. Go to Settings → Feed Selection → Account-Required Feeds
2. Scroll to ADSBHub section
3. Enter your station key
4. Click "Save & Enable ADSBHub"
5. Wait for confirmation: "ADSBHub feed enabled successfully!"

**Step 3: Verify**

- Status badge shows "Active"
- Toggle checkbox is checked
- Data starts flowing to ADSBHub

---

## 🔧 Technical Implementation

### Frontend Changes

**Modified:** `web/templates/feeds-account-required.html`

**Added HTML Section:**
- ADSBHub configuration card
- Station key input field
- Enable/disable toggle
- Setup button
- Status badge
- Info box about ADSBHub

**User Note Above Station Key Field:**
```html
To sign up for an ADSBHub station key go to ADSBHub how to feed, 
setting your station up as feeder type "Linux" in "Client" mode, 
feeding via the "SBS" protocol. This will get you your station key. 
Existing users can find their station key on the Settings page of 
the ADSBHub site.
```

**Added JavaScript Functions:**
```javascript
toggleADSBHubEnabled(enabled)  - Toggle feed on/off
setupADSBHub()                  - Configure station key
```

---

### Backend Changes

**Modified:** `web/app.py`

**Added API Endpoints:**

#### 1. `POST /api/feeds/adsbhub/setup`
Configure ADSBHub with station key

**Request:**
```json
{
  "station_key": "your-station-key-here"
}
```

**Response:**
```json
{
  "success": true,
  "message": "ADSBHub feed configured successfully"
}
```

**Process:**
1. Validates station key
2. Updates .env file with key
3. Sets ADSBHUB_ENABLED=true
4. Starts ADSBHub Docker container
5. Returns success/error

#### 2. `POST /api/feeds/adsbhub/toggle`
Toggle ADSBHub feed on/off

**Request:**
```json
{
  "enabled": true
}
```

**Response:**
```json
{
  "success": true,
  "message": "ADSBHub feed enabled"
}
```

**Process:**
1. Updates ADSBHUB_ENABLED in .env
2. Starts (enabled=true) or stops (enabled=false) container
3. Returns success/error

**Updated Route:**
- `feeds_account_required()` - Added ADSBHub status checking

---

### Docker Configuration

**Modified:** `config/docker-compose.yml`

**Added Container:**
```yaml
adsbhub:
  image: ghcr.io/sdr-enthusiasts/docker-adsbexchange:latest
  container_name: adsbhub
  hostname: adsbhub
  restart: unless-stopped
  networks:
    - adsb_net
  environment:
    - BEASTHOST=ultrafeeder
    - BEASTPORT=30005
    - ADSBHUB_STATION_KEY=${ADSBHUB_STATION_KEY}
    - ADSBHUB_SERVER=data.adsbhub.org
    - MLAT=no
  tmpfs:
    - /run:exec,size=64M
    - /var/log
  depends_on:
    - ultrafeeder
```

**Configuration:**
- Uses ADSBExchange Docker image (supports ADSBHub)
- Connects to ultrafeeder via Beast protocol (port 30005)
- Sends data to data.adsbhub.org
- Station key from environment variable
- MLAT disabled (ADSBHub doesn't use MLAT currently)

---

### Environment Variables

**Added to `.env`:**
```bash
ADSBHUB_STATION_KEY=      # Station key from ADSBHub.org
ADSBHUB_ENABLED=false     # Enable/disable ADSBHub feed
```

---

## 🎬 User Workflows

### Workflow: Setup ADSBHub Feed

```
USER ACTION                SYSTEM RESPONSE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1. Get station key        → Visit ADSBHub.org
   from ADSBHub.org         Sign up as Linux/Client/SBS
                            Receive station key

2. Enter station key      → [Enter in TAKNET-PS field]
   in TAKNET-PS             

3. Click "Save &          → Modal: "Configuring ADSBHub feed..."
   Enable ADSBHub"          [spinner animation]

4. System processes       → API: POST /api/feeds/adsbhub/setup
                            Updates .env with key
                            Starts Docker container

5. See success            → Modal: "ADSBHub feed enabled successfully!" [✓]
                            Auto-dismiss after 2 seconds
                            Status badge → "Active"
                            Toggle → Checked

6. Data flows            → Container connects to ultrafeeder
                            Feeds data to data.adsbhub.org
```

---

### Workflow: Toggle ADSBHub Feed

```
USER ACTION                SYSTEM RESPONSE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1. Click toggle           → Modal: "Enabling ADSBHub feed..." [spinner]
   checkbox

2. System processes       → API: POST /api/feeds/adsbhub/toggle
                            Updates ADSBHUB_ENABLED=true
                            Starts container

3. See success            → Modal: "ADSBHub feed enabled successfully!" [✓]
                            Auto-dismiss after 1.5 seconds
                            Status badge → "Active"

To disable: Uncheck toggle → "Disabling..." → Stops container → "Inactive"
```

---

## 📊 Comparison with Other Feeders

| Feature | FlightRadar24 | FlightAware | ADSBHub |
|---------|---------------|-------------|---------|
| **Setup** | Email or Key | Feeder ID | Station Key |
| **Registration** | Auto via email | Generate UUID | Manual signup |
| **Protocol** | Beast | Beast | SBS (via Beast) |
| **MLAT** | Yes | Yes | No |
| **Benefits** | Business plan | Enterprise access | Community data |
| **Status** | ✅ Implemented | ✅ Implemented | ✅ NEW! |

---

## 🎯 What's Included from Previous Versions

### From v2.41.3
- ✅ WiFi configuration UX improvements
- ✅ Manual WiFi entry for remote setup
- ✅ Custom password modal
- ✅ Real-time status feedback

### From v2.41.2
- ✅ WiFi configuration in Settings tab
- ✅ Network scanning
- ✅ Manual SSID entry

### From v2.41.1
- ✅ "Enable All" button for feeds
- ✅ Popup feedback improvements

### Core Features
- ✅ Complete ADS-B feeder system
- ✅ Multiple feed support (now 8 total!)
- ✅ Tailscale VPN integration
- ✅ tar1090 map interface
- ✅ WiFi configuration

---

## 📦 Files Modified

```
web/templates/feeds-account-required.html
  → Added ADSBHub configuration section
  → Added station key field with user note
  → Added JavaScript functions for ADSBHub

web/app.py
  → Added /api/feeds/adsbhub/setup endpoint
  → Added /api/feeds/adsbhub/toggle endpoint
  → Updated feeds_account_required() route

config/docker-compose.yml
  → Added adsbhub container configuration
  → Connects via Beast protocol
  → Feeds to data.adsbhub.org
```

---

## ✅ Verification

After installation/update:

### Test 1: Access ADSBHub Configuration
```bash
# 1. Open web interface
# Visit: http://taknet-ps.local/feeds

# 2. Click "Account-Required Feeds"
# Should see three feeders now:
# - FlightRadar24
# - FlightAware
# - ADSBHub (NEW!)

# 3. Scroll to ADSBHub section
# Should see configuration card with:
# - Enable toggle
# - Station key field
# - Setup button
# - User note about registration
```

### Test 2: Configure ADSBHub
```bash
# 1. Get station key from ADSBHub.org
# Sign up as Linux/Client/SBS

# 2. Enter station key in TAKNET-PS
# Paste into "ADSBHub Station Key" field

# 3. Click "Save & Enable ADSBHub"
# Should see: "Configuring ADSBHub feed..." [spinner]
# Then: "ADSBHub feed enabled successfully!" [✓]

# 4. Verify status
# Status badge should show "Active"
# Toggle should be checked

# 5. Check container
docker ps | grep adsbhub
# Should show running container
```

### Test 3: Toggle ADSBHub Feed
```bash
# 1. Uncheck toggle
# Should see: "Disabling ADSBHub feed..."
# Then: "ADSBHub feed disabled successfully!"
# Status badge → "Inactive"

# 2. Check toggle again
# Should see: "Enabling ADSBHub feed..."
# Then: "ADSBHub feed enabled successfully!"
# Status badge → "Active"

# 3. Verify container status
docker ps | grep adsbhub  # When enabled
docker ps -a | grep adsbhub  # When disabled
```

---

## 💡 About ADSBHub

**What is ADSBHub?**
ADSBHub is a community-driven ADS-B data aggregator that:
- Collects flight data from volunteers worldwide
- Distributes real-time data to researchers and developers
- Provides open access to aviation enthusiasts
- Supports academic and commercial research

**Why Feed ADSBHub?**
- Support the aviation research community
- Contribute to open data initiatives
- Help improve flight tracking coverage
- Join a global network of aviation enthusiasts

**Data Usage:**
Your data helps power:
- Academic research projects
- Aviation safety studies
- Flight tracking applications
- Statistical analysis tools

---

## 🐛 Bug Fixes

No bugs fixed in this release - pure feature addition!

---

## 📞 Support

**New Feeder:** ADSBHub  
**Setup Guide:** https://www.adsbhub.org/howtofeed.php  
**Station Type:** Linux / Client / SBS  
**Protocol:** Beast (via ultrafeeder) → SBS (to ADSBHub)

**Troubleshooting:**
```bash
# Check ADSBHub container status
docker ps | grep adsbhub

# Check ADSBHub logs
docker logs adsbhub

# Verify station key in .env
grep ADSBHUB /opt/adsb/config/.env

# Restart ADSBHub container
docker compose -f /opt/adsb/config/docker-compose.yml restart adsbhub
```

---

**Version:** 2.41.4  
**Build Date:** 2026-02-09  
**Status:** Production Ready  
**Breaking Changes:** None  
**New Feature:** ADSBHub Feed Support ✨

**Total Feeders:** 8
- TAKNET-PS (accountless)
- adsb.fi (accountless)
- adsb.lol (accountless)
- airplanes.live (accountless)
- ADSBexchange (accountless)
- FlightRadar24 (account required) ✅
- FlightAware (account required) ✅
- ADSBHub (account required) ✅ NEW!
