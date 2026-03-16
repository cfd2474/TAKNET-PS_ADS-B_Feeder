# System Update Checks & NetBird Config — API Reference for Aggregator

This document describes how the feeder implements **system update checks** and **NetBird VPN status/config**. Use it when proxying the feeder UI (e.g. via tunnel) so the aggregator understands request/response shapes, semantics, and UI behavior.

---

## 1. System Update Checks

### 1.1 Where the feeder gets version info

- **Current version (on device):** Read from file `/opt/adsb/VERSION` (plain text, e.g. `2.59.44`).
- **Latest version (remote):** Fetched from a fixed URL:
  - `https://raw.githubusercontent.com/cfd2474/TAKNET-PS_ADS-B_Feeder/main/version.json`
- **Version format:** `X.Y.Z` (e.g. `2.59.44`). Comparison is numeric (major, minor, patch); shorter forms like `2.47` are treated as `2.47.0`.

### 1.2 Remote `version.json` shape

The feeder expects JSON from the URL above. Example:

```json
{
  "version": "2.59.44",
  "release_date": "2026-03-15",
  "release_name": "Tunnel log visibility",
  "download_url": "https://raw.githubusercontent.com/.../install/install.sh",
  "changelog_url": "https://raw.githubusercontent.com/.../CHANGELOG.md",
  "minimum_version": "2.40.0",
  "breaking_changes": false,
  "release_notes": "Short description of the release.",
  "update_priority": 3
}
```

**Fields used by the feeder:**

| Field | Type | Meaning |
|-------|------|--------|
| `version` | string | Latest release version (e.g. `2.59.44`). |
| `update_priority` | number | **1** = apply update immediately; **2** = schedule for 02:00 overnight; **3** = alert only (show “Update Now” button). Default if missing: **3**. Invalid values are treated as 3. |
| `release_notes` | string | Shown in the Settings UI when an update is available. |

Other fields (e.g. `release_date`, `download_url`, `changelog_url`) are returned to the client in `release_info` but do not change feeder logic.

### 1.3 API: Get version and update availability

**Request**

- **Path:** `GET /api/system/version`
- **Headers:** None required.
- **Body:** None.

**Response (200, JSON)**

- **Success (fetched remote version):**

```json
{
  "success": true,
  "current_version": "2.59.44",
  "latest_version": "2.59.45",
  "update_available": true,
  "update_priority": 3,
  "release_info": { ... }
}
```

- **Success (could not reach GitHub):** `update_available` is `false`, `latest_version` may be `"unknown"`, optional `error` string (e.g. `"Could not check for updates"`), `update_priority` defaults to `3`.
- **Error (e.g. 500):** `success: false`, `error` string.

**Semantics**

- The feeder compares `current_version` (from `/opt/adsb/VERSION`) with `latest_version` (from remote `version.json`) numerically. If `latest_version` > `current_version`, `update_available` is `true`.
- The **Settings** page calls this on load (“Check for Updates”) and uses `update_priority` to decide behavior (see below).

### 1.4 API: Schedule overnight update (priority 2)

Used when an update has **priority 2**. The feeder creates a flag file so a cron job runs the updater at 02:00 local time.

**Request**

- **Path:** `POST /api/system/update/schedule`
- **Headers:** `Content-Type: application/json` (body may be empty).
- **Body:** Optional `{}` or omitted.

**Response (200, JSON)**

```json
{
  "success": true,
  "message": "Update scheduled for 02:00 overnight"
}
```

**Behavior**

- Creates `/opt/adsb/var/scheduled-update` (flag file).
- Cron at `0 2 * * *` runs `/opt/adsb/scripts/run-scheduled-update.sh`, which checks for this flag and, if present, runs the updater and then removes the flag.

### 1.5 API: Check if overnight update is scheduled

**Request**

- **Path:** `GET /api/system/update/schedule/status`
- **Body:** None.

**Response (200, JSON)**

```json
{
  "success": true,
  "scheduled": true
}
```

- `scheduled: true` if `/opt/adsb/var/scheduled-update` exists; otherwise `scheduled: false`.
- Settings page uses this on load to show the “Update scheduled for 02:00 overnight” banner.

### 1.6 API: Start update now

**Request**

- **Path:** `POST /api/system/update`
- **Body:** Optional `{}` or omitted.

**Response (200, JSON)**

- **Started:**

```json
{
  "success": true,
  "message": "Update started",
  "log_file": "/tmp/taknet_update.log"
}
```

- **Already running (409):** `success: false`, `message: "Update already in progress"`.
- **Updater missing (404):** `success: false`, `message: "Updater script not found"`.

**Behavior**

- Creates lock `/tmp/taknet_update.lock`, runs `/opt/adsb/scripts/updater.sh` in the background (via sudo), logs to `/tmp/taknet_update.log`. The HTTP response returns immediately.

### 1.7 API: Update progress (polling)

**Request**

- **Path:** `GET /api/system/update/status`
- **Body:** None.

**Response (200, JSON)**

```json
{
  "success": true,
  "is_updating": true,
  "log": "last 50 lines of /tmp/taknet_update.log\n..."
}
```

- `is_updating` is `true` while `/tmp/taknet_update.lock` exists.
- The Settings page polls this after calling `POST /api/system/update` to drive the update progress modal and detect when the update (and reboot) have finished.

### 1.8 How the Settings UI uses update checks

1. **On load**
   - Calls `GET /api/system/version` (triggers “Check for Updates” logic).
   - Calls `GET /api/system/update/schedule/status` to show/hide the “scheduled for 02:00” banner.

2. **When user clicks “Check for Updates”**
   - Calls `GET /api/system/version`.
   - If `update_available` and **priority 1:** does not show “Update Now”; instead calls the same flow as “Update Now” (schedule modal then `POST /api/system/update`) so the update starts immediately.
   - If **priority 2:** does not show “Update Now”; calls `POST /api/system/update/schedule` and shows the “Update scheduled for 02:00 overnight” banner.
   - If **priority 3:** shows “Update Now” button; user confirms then `POST /api/system/update`, then polling on `GET /api/system/update/status`.

3. **After “Update Now” (or priority 1)**
   - Modal shows progress; frontend polls `GET /api/system/update/status` until `is_updating` is false (or user navigates away).

**Summary for aggregator (update checks)**

- Proxy `GET /api/system/version`, `GET /api/system/update/schedule/status`, `POST /api/system/update/schedule`, `POST /api/system/update`, `GET /api/system/update/status` with the **same path** as on the feeder (path rewriting as in the main feeder API reference).
- Do not alter `update_priority` or `release_info`; the feeder and its UI rely on them.
- The feeder itself fetches `version.json` from GitHub; the aggregator does not need to serve it unless it is replacing or caching that URL.

---

## 2. NetBird Config & Status

NetBird is the VPN client used to connect the feeder to the TAKNET-PS management network. The feeder exposes status and enable/disable via REST; there is no separate “config check” endpoint beyond status and the env vars below.

### 2.1 Config and management URL

- **Management URL:** Hardcoded in the feeder: `https://netbird.tak-solutions.com`. The user does not set this in the UI; they only provide a **setup key**.
- **Env vars (in `/opt/adsb/config/.env`):**
  - `NETBIRD_ENABLED` — `true` or `false` (reflects whether NetBird is intended to be on).
  - `NETBIRD_SETUP_KEY` — Setup key for enrollment (set when enabling).
  - `NETBIRD_MANAGEMENT_URL` — Set by the feeder to the hardcoded URL when enabling.

So “NetBird config” in practice means: **enabled** flag, **setup key** (and implicitly the fixed management URL). Status is determined by running the `netbird` binary (see below).

### 2.2 API: NetBird status

**Request**

- **Path:** `GET /api/netbird/status`
- **Body:** None.

**Response (200, JSON)**

When NetBird is **not** installed:

```json
{
  "installed": false,
  "connected": false,
  "message": "NetBird not installed"
}
```

When NetBird **is** installed:

```json
{
  "installed": true,
  "connected": true,
  "enabled": true,
  "ip": "100.64.0.1",
  "message": "Connected"
}
```

Or when installed but disconnected:

```json
{
  "installed": true,
  "connected": false,
  "enabled": true,
  "ip": null,
  "message": "Not connected"
}
```

**Fields**

| Field | Type | Meaning |
|-------|------|--------|
| `installed` | boolean | Whether the `netbird` binary is available on the feeder. |
| `connected` | boolean | Whether the feeder considers NetBird connected to the management server (and has an IP). |
| `enabled` | boolean | Value of `NETBIRD_ENABLED` from `.env` (`true`/`false`). |
| `ip` | string or null | NetBird/VPN IP (e.g. on `wt0`). CIDR suffix stripped. `null` if not connected. |
| `message` | string | `"Connected"`, `"Not connected"`, `"NetBird not installed"`, or error/timeout message. |

**How the feeder determines `connected`**

1. Run `netbird status --json`; if output is valid JSON, parse for management state (e.g. `managementState.connected` or `management.connected`) and for IP (`netbirdIp`, `localPeerState.ip`, or `ip`).
2. If JSON is missing or unhelpful, run `netbird status` (plain text) and look for the line `Management: Connected` and for `NetBird IP: <ip>`.
3. If still not connected, check interface `wt0` with `ip addr show wt0`; if there is an `inet` address, treat as connected and use that as `ip`.

So “config check” for NetBird is effectively: call `GET /api/netbird/status` and use `installed`, `enabled`, `connected`, and `ip`.

### 2.3 API: Enable NetBird (enroll and connect)

**Request**

- **Path:** `POST /api/netbird/enable`
- **Headers:** `Content-Type: application/json`
- **Body:**

```json
{
  "setup_key": "your-setup-key-here"
}
```

**Response (200, JSON)**

- **Success:**

```json
{
  "success": true,
  "message": "NetBird connected successfully"
}
```

- **Failure (e.g. bad key or not installed):**

```json
{
  "success": false,
  "message": "NetBird enrollment failed: <stderr output>"
}
```

or `"Setup key is required"`, `"NetBird not installed"`, or timeout message.

**Behavior**

- Writes `NETBIRD_MANAGEMENT_URL`, `NETBIRD_SETUP_KEY`, and `NETBIRD_ENABLED=true` to `.env`.
- Runs: `netbird up --setup-key <key> --management-url https://netbird.tak-solutions.com --disable-dns --allow-server-ssh --enable-ssh-root --hostname <MLAT_SITE_NAME>` (hostname from env).
- On success: rebuilds config (e.g. `config_builder.py`), restarts main services so the feeder uses the VPN path to the aggregator.
- On failure: sets `NETBIRD_ENABLED=false` in `.env`.

### 2.4 API: Disable NetBird

**Request**

- **Path:** `POST /api/netbird/disable`
- **Body:** Optional `{}` or omitted.

**Response (200, JSON)**

```json
{
  "success": true,
  "message": "NetBird disconnected"
}
```

**Behavior**

- Sets `NETBIRD_ENABLED=false` in `.env`.
- Runs `netbird down` if the binary exists.
- Rebuilds config and restarts services so the feeder falls back to the public (non-VPN) path.

### 2.5 Restarting NetBird service

The feeder can restart the NetBird systemd service via the generic service-restart API:

- **Path:** `POST /api/services/restart`
- **Body:** `{ "service": "netbird" }`

(See main feeder API reference for full request/response.)

### 2.6 Summary for aggregator (NetBird)

- Proxy `GET /api/netbird/status`, `POST /api/netbird/enable`, `POST /api/netbird/disable` with the **same path** as on the feeder.
- **Status** is the only “config check” endpoint: it reports `installed`, `enabled`, `connected`, and `ip`. There is no separate “config” endpoint for NetBird; config is derived from `.env` and from running `netbird status` (and optionally `ip addr show wt0`).
- Management URL is fixed; the aggregator does not need to supply it. Only the setup key is user-defined when enabling.

---

## 3. Proxying reminder

When the aggregator proxies the feeder (e.g. under `/feeder/<feeder_id>/`):

- Forward requests so the feeder receives the **same path** it would see when accessed directly (e.g. the feeder must see `/api/system/version`, not `/api/system/version` with a different prefix).
- If the browser is sent rewritten URLs (e.g. `/feeder/<id>/api/...`), the aggregator must strip the prefix and forward the path the feeder expects (e.g. `/api/...`).

For the full list of routes and path-rewriting rules, see **AGGREGATOR_FEEDER_API_REFERENCE.md**.
