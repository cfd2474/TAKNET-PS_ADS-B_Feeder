# Feeder Web API Reference (for Aggregator Tunnel Proxy)

When the aggregator proxies the feeder UI through the tunnel (e.g. `https://aggregator/feeder/<feeder_id>/...`), **all requests must be forwarded to the feeder with the same path**. The feeder Flask app serves everything under `/` and `/api/...`. The aggregator must **not** assume or rewrite paths; it should forward the request path as-is (minus the `/feeder/<feeder_id>` prefix) to the feeder.

**Critical:** The browser will send requests **relative to the current page**. If the user is at `https://aggregator/feeder/92882-test/` then a fetch to `/api/network-quality` will go to `https://aggregator/api/network-quality` (origin + path), **not** to `https://aggregator/feeder/92882-test/api/network-quality`. So the aggregator must either:
1. **Rewrite HTML/JS** so that API calls use a relative base (e.g. `./api/...` or a prefix like `/feeder/92882-test/api/...`), or
2. **Route by path** so that requests to `https://aggregator/api/...` when the user came from a feeder page are forwarded to the correct feeder’s tunnel (e.g. by session or referer). The usual approach is (1): rewrite the document so that every `/api/...` and `/static/...` becomes `/feeder/<feeder_id>/api/...` and `/feeder/<feeder_id>/static/...`.

Below is the **complete list of feeder routes** so the aggregator can ensure every path is proxied and nothing is assumed.

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

### GPS
| Path | Method | Behavior |
|------|--------|----------|
| `/api/gps/check` | GET | Quick GPS check (e.g. gpsd). |
| `/api/gps/start` | POST | Start background GPS acquisition (JSON optional). |
| `/api/gps/status` | GET | Progress/result of GPS acquisition. |
| `/api/gps/coordinates` | GET | Legacy single-shot GPS coordinates. |

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
| `/api/service/<service_name>/state` | GET | State of one service (ultrafeeder, fr24, piaware, etc.). |
| `/api/service/<service_name>/restart` | POST | Restart one service. |
| `/api/service/<service_name>/status` | GET | Status of one service. |

### System & updates
| Path | Method | Behavior |
|------|--------|----------|
| `/api/system/version` | GET | Current version, latest version, update_available, update_priority, release_info. |
| `/api/system/update` | POST | Start system update (runs updater script). |
| `/api/system/update/status` | GET | Update progress (is_updating, log). |
| `/api/system/update/schedule` | POST | Schedule overnight update (priority 2). |
| `/api/system/update/schedule/status` | GET | Whether an update is scheduled. |
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

These must be proxied with the same path so that when the page is at `/feeder/<feeder_id>/...`, links like `/static/css/style.css` are rewritten to `/feeder/<feeder_id>/static/css/style.css` and then proxied to the feeder as `GET /static/css/style.css`.

---

## Frontend calls that must reach the feeder

The dashboard and other pages call these; **all must be proxied to the feeder** (with path as above), not served by the aggregator:

- **Dashboard:** `/api/status`, `/api/taknet-ps/stats`, `/api/power-status`, `/api/network-quality`, `/api/sdr/status`
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

1. **Path prefix:** When serving the feeder UI at `/feeder/<feeder_id>/`, rewrite all links, form actions, and fetch URLs so that `/api/...` and `/static/...` become `/feeder/<feeder_id>/api/...` and `/feeder/<feeder_id>/static/...`.
2. **Forward path:** When proxying to the feeder, send the path **without** the `/feeder/<feeder_id>` prefix (e.g. request to `/feeder/92882-test/api/network-quality` → send to feeder as `GET /api/network-quality`).
3. **Do not implement feeder APIs on the aggregator.** Every path in the tables above is implemented **only on the feeder**; the aggregator should proxy them to the connected feeder’s tunnel and return the feeder’s response unchanged (including status codes and headers).
