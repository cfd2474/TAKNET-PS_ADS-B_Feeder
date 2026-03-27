# Feeder Web API Reference (for Aggregator Tunnel Proxy)

When the aggregator proxies the feeder UI through the tunnel (e.g. `https://aggregator/feeder/<feeder_id>/...`), requests must reach the feeder with paths the **local stack** understands.

**Local stack (not Flask-only):** On the feeder, **nginx** listens on port **80** and proxies to:

- **Flask** (port 5000): HTML pages, `/api/...`, `/static/...`
- **tar1090 / graphs1090** (port 8080): paths like `/map/...`, `/graphs1090`, `/data/`, `/db2/`, `/tracks/`, `/tar1090/` (see tunnel routing below)
- **FR24** (port 8754): `/fr24/...` and root-absolute **`/logo.png`**, **`/monitor.json`** (nginx `location` on port 80)
- **PiAware** (port 8082): `/piaware/...`

The tunnel client forwards to **`:80`** (dashboard) or **`:8080`** (tar1090) and **strips one** `/feeder/<feeder_id>/` prefix from the path when present, so the feeder sees `/api/...`, `/static/...`, `/logo.png`, etc. The aggregator may send either prefixed or already-stripped paths; stripping is idempotent.

**Critical:** The browser will send requests **relative to the current page**. If the user is at `https://aggregator/feeder/92882-test/` then a fetch to `/api/network-quality` will go to `https://aggregator/api/network-quality` (origin + path), **not** to `https://aggregator/feeder/92882-test/api/network-quality`. So the aggregator must either:
1. **Rewrite HTML/JS** so that API calls use a relative base (e.g. `./api/...` or a prefix like `/feeder/92882-test/api/...`), or
2. **Route by path** so that requests to `https://aggregator/api/...` when the user came from a feeder page are forwarded to the correct feeder’s tunnel (e.g. by session or referer). The usual approach is (1): rewrite the document so that every `/api/...` and `/static/...` becomes `/feeder/<feeder_id>/api/...` and `/feeder/<feeder_id>/static/...`.

Below is the **complete list of feeder routes** so the aggregator can ensure every path is proxied and nothing is assumed.

### FR24 web UI (`/fr24/`) — third-party absolute paths

The FlightRadar24 container serves HTML that references **`/logo.png`** and **`/monitor.json`** at the **site origin** (not under `/fr24/`). In the tunnel context that means the browser may request:

- `https://<aggregator>/logo.png` and `https://<aggregator>/monitor.json` (no `/feeder/<id>/` prefix).

Those requests **must** be routed to the **same feeder tunnel** that is serving the FR24 page (same as you do for `/api/...` and `/static/...` at the origin). If they hit the aggregator without a feeder binding, they will **404**.

If the aggregator instead prefixes all proxied paths (e.g. `https://<aggregator>/feeder/<id>/logo.png`), the feeder tunnel client **strips** one `/feeder/<id>/` segment before calling the local nginx, so **`/feeder/<id>/logo.png`** becomes **`/logo.png`** on the feeder and matches nginx → FR24.

---

## Tunnel routing (feeder tunnel client)

The aggregator should send these on each proxied HTTP request (WebSocket tunnel `request` message):

| Mechanism | Purpose |
|-----------|---------|
| **`X-Tunnel-Target: dashboard`** | Force nginx/Flask on **127.0.0.1:80** (default for most paths). |
| **`X-Tunnel-Target: tar1090`** | Force **127.0.0.1:8080** (map, graphs1090, aircraft data paths). |
| **Path fallback** (if header absent) | Paths starting with `/graphs1090`, `/data/`, `/db2/`, `/tracks/`, `/tar1090/`, or exactly **`/`** go to **tar1090**; everything else to **dashboard** (`:80`). |

**Note:** A tunneled request whose path is exactly **`/`** (e.g. after stripping `/feeder/<id>/`) hits **tar1090 :8080**, not the Flask UI. Deep-link the web app with **`/dashboard`**, **`/setup`**, etc. Use **`X-Tunnel-Target: dashboard`** if you must forward **`/`** to nginx/Flask on **:80**.

Use **`X-Tunnel-Target`** when the path alone is ambiguous (e.g. you forward a shortened path).

---

## Page routes (HTML)

| Path | Method | Behavior |
|------|--------|----------|
| `/` | GET | Redirect to `/setup` or `/dashboard` depending on config |
| `/setup` | GET | Setup wizard (location, GPS, etc.) |
| `/setup/sdr` | GET | SDR configuration step |
| `/loading` | GET | Loading/status page during first setup |
| `/dashboard` | GET | Main dashboard |
| `/feeds` | GET | Feed selection page |
| `/feeds/account-required` | GET | Account-required feeds page |
| `/settings` | GET | Settings page |
| `/logs` | GET | Logs page |
| `/about` | GET | About page |
| `/taknet-ps-status` | GET | TAKNET-PS status page |

---

## API routes (JSON; must be proxied with same path)

### Config & status
| Path | Method | Behavior |
|------|--------|----------|
| `/api/config` | GET | Returns full .env-derived config (JSON). |
| `/api/config` | POST | Save config (JSON body: key-value updates). Returns `{success, message}`. |
| `/api/status` | GET | System status: docker, feeds list, configured flag, service_states. |
| `/api/network-status` | GET | Internet reachability, primary IP, hostname. |
| `/api/network-quality` | GET | Ping-based quality: good/moderate/poor, packet_loss, avg_rtt_ms. |
| `/api/power-status` | GET | Power/throttling status (current_issue, past_issue, message). |
| `/api/dashboard/bootstrap` | GET | Aggregate JSON for dashboard load (status, network, power, SDR, TAKNET-PS). Does **not** include network-quality (loaded separately). |

### GPS
| Path | Method | Behavior |
|------|--------|----------|
| `/api/gps/check` | GET | Quick GPS check (e.g. gpsd). |
| `/api/gps/start` | POST | Start background GPS acquisition (JSON optional). |
| `/api/gps/status` | GET | Progress/result of GPS acquisition. |
| `/api/gps/coordinates` | GET | Legacy single-shot GPS coordinates. |
| `/api/gps/apply-location` | POST | Apply GPS-derived location to config. |

### SDR (single-SDR legacy)
| Path | Method | Behavior |
|------|--------|----------|
| `/api/sdr/status` | GET | SDR status. |
| `/api/sdr/detect` | GET | Detect SDR devices. |
| `/api/sdr/configure` | POST | Configure SDR (JSON body). |

### SDR (multi-SDR / Phase B)
| Path | Method | Behavior |
|------|--------|----------|
| `/api/sdrs/detect` | GET | Detect SDRs (SoapySDR etc.). |
| `/api/sdrs/current-config` | GET | Current SDR configuration. |
| `/api/sdrs/gain-options/<driver>` | GET | Gain options for driver (e.g. rtlsdr). |
| `/api/sdrs/configure` | POST | Configure SDRs (JSON body). |

### Mobile / misc
| Path | Method | Behavior |
|------|--------|----------|
| `/api/mobile/status` | GET | Mobile feeder mode status (when UI exposes that card). |

### Feeds (toggles & setup)
| Path | Method | Behavior |
|------|--------|----------|
| `/api/feeds/toggle` | POST | Toggle a feed (JSON: feed name, enabled). |
| `/api/feeds/fr24/status` | GET | FR24 status. |
| `/api/feeds/fr24/setup` | POST | FR24 setup (e.g. key). |
| `/api/feeds/fr24/test` | POST | Test FR24. |
| `/api/feeds/fr24/register` | POST | Register FR24. |
| `/api/feeds/fr24/diagnostics` | GET | FR24 diagnostics. |
| `/api/feeds/fr24/toggle` | POST | Toggle FR24. |
| `/api/feeds/piaware/status` | GET | PiAware status. |
| `/api/feeds/piaware/setup` | POST | PiAware setup. |
| `/api/feeds/piaware/toggle` | POST | Toggle PiAware. |
| `/api/feeds/adsbhub/status` | GET | ADSBHub status. |
| `/api/feeds/adsbhub/setup` | POST | ADSBHub setup. |
| `/api/feeds/adsbhub/toggle` | POST | Toggle ADSBHub. |

### TAKNET-PS
| Path | Method | Behavior |
|------|--------|----------|
| `/api/taknet-ps/connection` | GET | Connection method, host, NetBird status. |
| `/api/taknet-ps/stats` | GET | Feed status (e.g. ultrafeeder connection to aggregator). |

### Tailscale
| Path | Method | Behavior |
|------|--------|----------|
| `/api/tailscale/install` | POST | Install/update Tailscale (optional auth_key, hostname). |
| `/api/tailscale/status` | GET | Tailscale status. |
| `/api/tailscale/progress` | GET | Install progress. |
| `/api/tailscale/enable` | POST | Enable Tailscale (JSON body). |
| `/api/tailscale/disable` | POST | Disable Tailscale. |

### NetBird
| Path | Method | Behavior |
|------|--------|----------|
| `/api/netbird/status` | GET | NetBird status. |
| `/api/netbird/enable` | POST | Enable NetBird (e.g. setup_key). |
| `/api/netbird/disable` | POST | Disable NetBird. |

### WiFi
| Path | Method | Behavior |
|------|--------|----------|
| `/api/wifi/scan` | GET | Scan for WiFi networks. |
| `/api/wifi/saved` | GET | Saved WiFi networks. |
| `/api/wifi/add` | POST | Add WiFi network (JSON). |
| `/api/wifi/remove` | POST | Remove WiFi network. |
| `/api/wifi/status` | GET | WiFi status. |
| `/api/wifi/enable` | POST | Enable WiFi. |
| `/api/wifi/disable` | POST | Disable WiFi. |

### Services
| Path | Method | Behavior |
|------|--------|----------|
| `/api/service/restart` | POST | Restart main service (ultrafeeder); JSON body optional. |
| `/api/service/ready` | GET | Service ready state. |
| `/api/service/progress` | GET | Service install/restart progress. |
| `/api/service/<service_name>/state` | GET | High-level state for a service (used by UI for docker-backed services, etc.). |
| `/api/service/<service_name>/restart` | POST | Restart one service. Valid `service_name`: `ultrafeeder`, `fr24`, `piaware`, `netbird`, `tailscale`, `tunnel-client`. |
| `/api/service/<service_name>/status` | GET | Running or not. Valid `service_name`: `ultrafeeder`, `fr24`, `piaware`, `tailscale`, `tunnel-client` (not `netbird`; use NetBird APIs for VPN state). |

### System & updates
| Path | Method | Behavior |
|------|--------|----------|
| `/api/system/version` | GET | Current version, latest version, update_available, update_priority, release_info. |
| `/api/system/update` | POST | Start system update (runs updater script). |
| `/api/system/update/status` | GET | Update progress (is_updating, log). |
| `/api/system/update/schedule` | POST | Schedule overnight update (priority 2). |
| `/api/system/update/schedule/status` | GET | Whether an update is scheduled. |
| `/api/system/periodic-reboot/settings` | POST | Configure periodic reboot (JSON body). |
| `/api/system/reboot` | POST | Reboot the device (after short delay). |

### Logs & other
| Path | Method | Behavior |
|------|--------|----------|
| `/api/logs/<source>` | GET | Log stream for a given source (e.g. ultrafeeder). |
| `/api/dump978/status` | GET | dump978 status. |
| `/api/dump978/enable` | POST | Enable dump978. |
| `/api/dump978/disable` | POST | Disable dump978. |
| `/api/fr24/activate` | POST | Activate FR24. |

---

## Static assets

| Path | Behavior |
|------|----------|
| `/static/<path>` | CSS, JS, images (e.g. `/static/css/style.css`, `/static/js/dashboard.js`, `/static/taknetlogo.png`). |

These must be proxied with the same path so that when the page is at `/feeder/<feeder_id>/...`, links like `/static/css/style.css` are rewritten to `/feeder/<feeder_id>/static/css/style.css` and then proxied to the feeder as `GET /static/css/style.css` (tunnel strips prefix → `/static/...`).

## Nginx-only paths on port 80 (not Flask)

Proxied like everything else; tunnel target should be **dashboard** (`:80`):

| Path | Behavior |
|------|----------|
| `/fr24/`, `/fr24/...` | FR24 web UI (upstream 8754). |
| `/piaware/`, `/piaware/...` | PiAware / FlightAware UI (upstream 8082). |
| `/map`, `/map/...` | tar1090 (upstream 8080); may also use **`X-Tunnel-Target: tar1090`** if you forward without `/map` prefix. |
| `/logo.png`, `/monitor.json` | FR24 assets (see FR24 section above). |

---

## Frontend calls that must reach the feeder

The dashboard and other pages call these; **all must be proxied to the feeder** (with path as above), not served by the aggregator:

- **Dashboard:** `/api/dashboard/bootstrap` (primary load), `/api/network-quality` (on-demand modal), `/api/mobile/status` (if card present), `/api/service/restart` (ultrafeeder restart button); polled/derived data comes from bootstrap aggregates where applicable
- **Settings:** `/api/config`, `/api/gps/check`, `/api/gps/start`, `/api/gps/status`, `/api/tailscale/*`, `/api/netbird/*`, `/api/wifi/*`, `/api/sdrs/*`, `/api/service/*`, `/api/system/*`
- **Feeds:** `/api/feeds/toggle`, `/api/feeds/fr24/*`, `/api/feeds/piaware/*`, `/api/feeds/adsbhub/*`
- **Setup:** `/api/config`, `/api/gps/*`; setup wizard may call `POST /api/setup` (if present; otherwise setup may use `POST /api/config` with a specific body)
- **Logs:** `/api/logs/<source>`
- **TAKNET-PS status page:** `/api/taknet-ps/connection`, `/api/taknet-ps/stats`

If the aggregator returns 404 for these paths, the browser is requesting them at the **aggregator origin** (e.g. `https://adsb.tak-solutions.com/api/network-quality`) instead of under the feeder path (`https://adsb.tak-solutions.com/feeder/92882-test_test_test/api/network-quality`). Fix by rewriting the document (HTML/JS) so that all such requests use the prefix `/feeder/<feeder_id>` before the path, then proxy that full path to the feeder (stripping the `/feeder/<feeder_id>` prefix when sending to the feeder).

---

## Request/response format

- **GET:** No body; query params as used by the feeder (e.g. for logs).
- **POST:** Usually `Content-Type: application/json`; body is JSON. Responses are typically `{"success": true|false, ...}` or a JSON object.
- **Errors:** 4xx/5xx may return HTML (e.g. Flask error page) or JSON; the frontend often expects JSON and parses it. If the aggregator returns an HTML error page for an API path, the client will fail with "Unexpected token '<'" (parsing HTML as JSON).

---

## Paths called by frontend but not defined on feeder (as of this doc)

These are requested by the feeder’s own HTML/JS; they may 404 on the feeder until implemented. The aggregator should **proxy them to the feeder** (same path); do not implement them on the aggregator.

- `POST /api/setup` — Setup wizard save (body: lat, lon, alt, tz, site_name). If 404, wizard may need to use `POST /api/config` instead.
- `GET /api/config/update` — Called from setup.js; may be legacy or alias. Proxy to feeder.

---

## Summary for aggregator

1. **Path prefix:** When serving the feeder UI at `/feeder/<feeder_id>/`, rewrite all links, form actions, and fetch URLs so that `/api/...` and `/static/...` become `/feeder/<feeder_id>/api/...` and `/feeder/<feeder_id>/static/...`. Include **origin-absolute** third-party paths such as **`/logo.png`** and **`/monitor.json`** (FR24), or route those URLs to the same feeder tunnel by session/cookie.
2. **Forward path:** Send paths to the tunnel either **with** or **without** the `/feeder/<feeder_id>/` prefix; the feeder tunnel client strips one prefix segment when present (e.g. `/feeder/92882-test/api/network-quality` → upstream `GET /api/network-quality`).
3. **Tunnel target:** Set **`X-Tunnel-Target: dashboard`** for Flask/nginx `:80`, **`X-Tunnel-Target: tar1090`** for raw tar1090/graphs1090 on `:8080` when path-based routing is insufficient.
4. **Do not implement feeder APIs on the aggregator.** Every path in the tables above is implemented **only on the feeder**; the aggregator should proxy them to the connected feeder’s tunnel and return the feeder’s response unchanged (including status codes and headers).
