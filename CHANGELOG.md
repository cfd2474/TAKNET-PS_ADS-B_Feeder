## v3.0.74 — 2026-04-14

### Fixed
- **UAT Force Toggle**: Fixed a logic error where the 'Force Enable UAT' override would fail to disable if it had previously been enabled.
- **Cleanup Logic**: Standardized the removal of compatibility environment variables and added explicit `docker compose stop/rm` for the `dump978` container when disabling the override.

---
## v3.0.73 — 2026-04-14

### Fixed
- **Dashboard Context**: Resolved a "Working outside of request context" error in the dashboard's Core Services panel. This was caused by worker threads attempting to access HTTP discovery headers without inherited context.
- **Tunnel Proxy Stability**: Ensured status worker threads are now fully context-aware for tunnel-prefixed environments.

---
## v3.0.72 — 2026-04-14

### Fixed
- **UAT Deployment Stability**: Fixed a final blocker where the `dump978` container failed to start during system boots and UI restarts due to Docker profile suppression.
- **Variable Compatibility**: Standardized internal naming between `DUMP978_DEVICE` and `SDR_978_DEVICE` across the configuration builder to ensure hardware-less force-enable mode works as intended.

---
## v3.0.71 — 2026-04-14

### Fixed
- **UAT Force Persistence**: Fixed a major bug where the 'Force Enable UAT' override would reset to disabled when saving other configuration settings.
- **Whitelist Synchronization**: Added `DUMP978_FORCE_OVERRIDE` to the security whitelist for config saves.
- **Status Reporting**: Updated the SDR configuration state machine to properly report the force-enable status during UI refreshes.
- **Container Deployment**: Fixed logic in `config_builder.py` to ensure the `dump978` container is created even without a local SDR assignment when forced (supporting networked UAT source scenarios).

---
## v3.0.70 — 2026-04-14

### Fixed
- **Web Tunnel Proxy Links**: Fixed an issue where clicking the community stats links (like adsb.fi, adsb.lol, airplanes.live) from a remote web session via `tak-solutions.com` would resulting in broken navigation / 404 errors. Handled by dynamically calculating and appending the `X-Forwarded-Prefix` HTTP header to all absolute URLs in `app.py` proxy logic.

---
## v3.0.69 — 2026-04-14

### Changed
- **Aggregator Upstream Error Reporting**: Improved the exception handling in the `stats_proxy` functionality to surface explicit `HTTPError` messages and target APIs directly to the user dashboard. This prevents intermittent upstream service failures (e.g. from `api.adsb.lol`) from appearing as localized application issues in the UI console.

---
## v3.0.68 — 2026-04-14

### Added
- **UAT (dump978) Override**: Added a new UI toggle switch within the SDR Devices section of the settings page. Users receiving UAT data from network sources can now force the `dump978-fa` daemon to run silently in the background, circumventing the standard behavior which safely disables it when a direct, local UAT radio is not explicitly selected in the table.

---
## v3.0.67 — 2026-04-14

### Fixed
- **Proxy Compatibility**: Isolated the aggressive deep proxy rewriting, gzip compression headers, and Referer masking strictly to the `airplanes.live` service. This restores original stable proxy block parsing for other aggregators (like `adsb.lol`) which were crashing or experiencing 500 errors due to the strict aggregator parsing rules introduced in v3.0.65.

---
## v3.0.66 — 2026-04-14

### Fixed
- **Airplanes.Live API Proxy Exception**: Extended the deep recursive proxy to explicitly route the API subdomain (`api.airplanes.live`) requests through the feeder. This fixes the final missing link for remote status checking where JavaScript `fetch()` calls to the API were still bypassing the proxy and testing the user's remote IP instead of the feeder.

---
## v3.0.65 — 2026-04-14

### Fixed
- **Deep Proxying for Airplanes.Live**: Implemented aggressive URL rewriting and header masking specifically for the `airplanes.live` status page. This version now scans and rewrites absolute URLs within HTML, JavaScript, and JSON responses, ensuring that background AJAX checks are correctly routed through the feeder's proxy. This resolves the "no beast connection found" error when viewing the dashboard from a remote connection.

---
## v3.0.64 — 2026-04-13

### Fixed
- **Dashboard 500 Error**: Emergency hotfix to restore critical module imports (`socket`, `urllib.request`, `uuid`) that were accidentally removed during the v3.0.63 cleanup. This resolves the Internal Server Error when loading the dashboard.

---
## v3.0.63 — 2026-04-13

### Fixed
- **Airplanes.Live Proxy**: Implemented `<base>` tag injection in the recursive proxy. This resolves the "No beast connection found" error by ensuring that background AJAX/Fetch requests for status data are correctly routed through the feeder's proxy, allowing the aggregator to see the feeder's public IP.

### Changed
- **Removed Aggregator Verification**: Removed the experimental "Verified" badge system in favor of existing local service health monitoring to eliminate confusing false-negative indicators.

---
## v3.0.62 — 2026-04-13

### Added
- **Native Aggregator Verification**: Implemented a server-side status check for community aggregators (**adsb.lol**, **adsb.fi**, **airplanes.live**, **adsbexchange**). The dashboard now displays a **✅ Verified** badge next to each service name if the feeder's backend confirms the aggregator is successfully receiving data from its IP. This provides a robust "Source of Truth" even when external dashboards are unreachable.

---
## v3.0.61 — 2026-04-13

### Fixed
- **Recursive Proxy Fix**: Upgraded the feeder status proxy to handle sub-paths and asset rewriting. This fixes the broken CSS/JS on the **airplanes.live** status page by routing all sub-resource requests back through the feeder, effectively bypassing CORS restrictions and ensuring a functional remote dashboard.

---
## v3.0.60 — 2026-04-13

### Added
- **Feeder Status Proxy**: Implemented a server-side proxy for community feeder status links (**adsb.lol**, **adsb.fi**, **airplanes.live**). This ensures that remote dashboard users see statistics correctly identified by the feeder's public IP, by routing the status request through the feeder's own backend.

---
## v3.0.59 — 2026-04-13

### Added
- **Remote Stats Support**: Implemented UUID-based deep links for **adsb.fi** and **adsb.lol**. This allows users to view their statistics even when accessing the dashboard remotely (e.g., via tunnel), by using the feeder's unique ID instead of browser IP detection.

---
## v3.0.58 — 2026-04-13

### Fixed
- **Service Status Indicators**: Fixed bug where community feeders (adsbx, adsbfi, etc.) were incorrectly showing as "Stopped" on the dashboard. They now correctly link to the `ultrafeeder` container status and show as "Running" when the engine is active.

---
## v3.0.57 — 2026-04-13

### Changed
- **ADSBExchange Link**: Reverted ADSBExchange stats link to the UUID-based pattern (`https://www.adsbexchange.com/api/feeders/?feed={uuid}`) for improved reliability over the IP-based detection page.

---
## v3.0.56 — 2026-04-13

### Added
- **Dashboard Network Stats**: Added the feeder's public IP address to the Network Status section of the dashboard for easier identification and external stats verification.

---
## v3.0.55 — 2026-04-13

### Changed
- **Community Feed Links**: Restored the legacy link patterns for ADSBExchange, adsb.fi, adsb.lol, and Airplanes.Live as confirmed working in version 3.0.04.

---
## v3.0.54 — 2026-04-13

### Changed
- **Community Feed Links**: Refined the links for adsb.fi, adsb.lol, and Airplanes.Live to use their respective IP-based "My Feed" detection pages (`https://adsb.fi/`, `https://my.adsb.lol`, and `https://airplanes.live/myfeed/`).

---
## v3.0.53 — 2026-04-13

### Fixed
- **Community Feeder Links**: Switched to using the unique `FEEDER_UUID` for status links to prevent 404 errors on adsb.lol, adsb.fi, and Airplanes.Live.
- **ADSBExchange Link Pattern**: Updated the ADSBExchange link to use the correct API pattern: `https://www.adsbexchange.com/api/feeders/?feed={uuid}`.

---
## v3.0.52 — 2026-04-13

### Fixed
- **Community Feed Status**: Resolved the "disconnected" issue for accountless feeders (adsbx, adsbfi, adsblol, airplaneslive) by implementing missing backend status logic.
- **Feeder-Specific Links**: Restored direct links to user-specific statistics pages on community networks by deriving the feeder ID from the `MLAT_SITE_NAME` configuration.

---
## v3.0.51 — 2026-04-13

### Fixed
- **Dashboard Stabilization**: Resolved a `NameError` in the bootstrap API that caused the dashboard to hang during initialization.
- **Performance**: Optimized Docker status polling by fetching all container states in a single call and reusing them across service health checks, significantly reducing dashboard load time and CPU overhead.
- **UI Error Handling**: Added robust error detection and reporting to the dashboard's core services grid to prevent silent failures.

---
## v3.0.50 — 2026-04-13

### Added
- **Core Services Dashboard**: Implemented a comprehensive 'Core Services' status section on the dashboard for real-time monitoring of all critical system containers and services.
- **Project Rules**: Established new persistent coding rules in `.antigravity/project_rules.md` for synchronized versioning and documentation standards.

### Changed
- Dashboard: Removed the redundant floating status indicator to declutter the UI.
- Backend: Updated Docker status tracking to include stopped containers for better visibility into offline services.

---
## v3.0.49 — 2026-04-12

### Changed
- Removed redundant version data from feeder and MLAT names; aggregator now processes version explicitly via the new registration field.

---
## v3.0.48 — 2026-04-12

### Changed
- Added dynamic version monitoring to tunnel_client.py to trigger automatic reconnection when software version changes.

---
## v3.0.47 — 2026-04-12

### Changed
- Updated tunnel_client.py to report software version during registration for better dashboard accuracy.

---
## v3.0.46 — 2026-04-12

### Added
- **FR24 UAT Key Support**: Added a dedicated field in the UI and backend support for optional FlightRadar24 UAT sharing keys (FR24KEY_UAT).

### Changed
- **UAT Restoration**: Fixed 978 MHz UAT data transmission by updating `dump978` to use `DUMP978_RTLSDR_DEVICE` for RTL-SDRs.
- **Data Blending**: Consolidated ADS-B and UAT data into a single unified stream to ensure complete tracking on the TAKNET-PS aggregator.
- **UI Integration**: Added `URL_978` and `ENABLE_978` to Ultrafeeder for local map visualization of UAT aircraft.

---
## v3.0.45 — 2026-04-10

### Changed
- UI: hide System Events card if empty

---
## v3.0.44 — 2026-04-10

### Changed
- **Header-Based CSP**: Pivoted to a robust, global `Content-Security-Policy: upgrade-insecure-requests` injection at the HTTP header level. This provides a universal fix for Mixed Content errors across all services, including Maps and Statistics, and correctly handles cached (304) and compressed (Gzip) traffic.
- **ID Sanitization**: Standardized naming logic to strictly preserve underscores (only spaces converted to hyphens).
- **Security**: Added `ProxyFix` middleware to the Flask web app to correctly propagate HTTPS protocols from the tunnel proxy.
- **Performance**: Restored full Gzip compression support for the web tunnel.

---
## v3.0.43 — 2026-04-10

### Changed
- **Regex Injection**: Hardened the then-current HTML CSP injection logic using case-insensitive regular expressions to handle indented tags (common on the Statistics page).
- **Audit Logging**: Added `[tunnel-csp]` and `[tunnel-proxy]` tags to system journal logs for better diagnostic visibility.
- **Protocol**: Increased WebSocket heartbeat stability with proactive 30s pongs.

---
## v3.0.42 — 2026-04-10

### Changed
- **Compression Fix**: Temporarily disabled local compression (`accept-encoding` stripping) to allow reliable HTML parsing for the (now retired) body-injection CSP method.

---
## v3.0.41 — 2026-04-10

### Changed
- **Universal CSP**: Implemented the first iteration of tunnel-level CSP injection to resolve browser security blocks on tar1090 (Maps) and graphs1090 (Stats).

---
## v3.0.40 — 2026-04-10

### Changed
- Made CSP conditional to restore direct IP access while maintaining tunnel security

---
## v3.0.39 — 2026-04-10

### Changed
- Resolved Mixed Content with CSP and fixed tunnel routing 404s

---
## v3.0.38 — 2026-04-10

### Changed
- Fixed Mixed Content and tunnel routing by migrating to path-relative URLs

---
## v3.0.37 — 2026-04-10

### Changed
- Fixed tunnel client to handle quoted values in .env file

---
## v3.0.36 — 2026-04-10

### Changed
- Aggregator-required tunnel protocol and ID mapping fixes

---
## v3.0.35 — 2026-04-10

### Changed
- Strict Web Tunnel ID sanitization and compliance

---
## v3.0.34 — 2026-04-10

### Changed
- Web Tunnel compliance: normalized feeder_id and synchronized dashboard port

---
## v3.0.33 — 2026-04-10

### Changed
- Implemented refresh modal and removed retrying badges from status table

---
## v3.0.32 — 2026-04-10

### Changed
- Fixed refresh button and added status cache-busting

---
## v3.0.31 — 2026-04-10

### Changed
- Fixed dashboard refresh button and improved watchdog state persistence

---
## v3.0.30 — 2026-04-10

### Changed
- Forced health recovery for ADSBHub and other community feeds in watchdog

---
## v3.0.29 — 2026-04-10

### Changed
- Marked ADSBHub MLAT as n/a and updated community feed stats

---
## v3.0.28 — 2026-04-10

### Changed
- Fixed false retrying status and improved healthwatchdog resilience

---
## v3.0.27 — 2026-04-10

### Changed
- Restored missing accountless feeds to the dashboard status table

---
## v3.0.26 — 2026-04-10

### Changed
- UI refinement for FR24 MLAT (n/a indicator and orange banner)

---
## v3.0.25 — 2026-04-10

### Changed
- Passed station coordinates (LAT, LON, ALT) to FR24 and PiAware containers to enable MLAT functionality.

---
## v3.0.24 — 2026-04-10

### Changed
- Fixed a stray closing brace in settings.html that was breaking the page's JavaScript logic.

---
## v3.0.23 — 2026-04-10

### Changed
- Fixed broken JavaScript references and removed orphaned Tailscale status functions in the settings page.

---
## v3.0.22 — 2026-04-10

### Changed
- Fixed a JavaScript bug in the settings page that prevented periodic reboot configuration from saving.

---
## v3.0.21 — 2026-04-10

### Changed
- Implemented proactive health monitoring for all feeds, automated container restarts, and safe system rebooting safeguards.

---
## v3.0.20 — 2026-04-10

### Changed
- Fix dump978 gain regression in config_builder.
- Implement security hardening with /api/config whitelist.
- Improve .env file safety with proper quoting and escaping.
- Document NetBird setup key security scope in updater.sh.

---
## v3.0.19 — 2026-03-26

### Changed
- Proxy PiAware root-absolute JS/CSS/font/img paths to port 8082 for tunnel; omit sub_filter (stock nginx). Doc aggregator notes.

---
## v3.0.18 — 2026-03-26

### Changed
- Strip /feeder/<id>/ prefix in tunnel client so /logo.png and /monitor.json hit nginx FR24 proxy. Document FR24 absolute paths for aggregator.

---
## v3.0.17 — 2026-03-26

### Changed
- Fix nginx failing to start: use conf.d map + add_header instead of server if { add_header } (invalid on stock Debian nginx). Run nginx -t before restart in install.

---
## v3.0.16 — 2026-03-26

### Changed
- FR24 HTTPS mixed-content workaround no longer uses nginx sub_filter (optional module). Explicitly proxies /logo.png and /monitor.json. Should prevent nginx start failure and restore tunnel (port 80) access.

---
## v3.0.15 — 2026-03-26

### Changed
- Fix local HTTP: only add CSP upgrade-insecure-requests when X-Forwarded-Proto is https (aggregator tunnel), avoiding https resource fetch refusals.

---
## v3.0.14 — 2026-03-26

### Changed
- Feeder nginx now upgrades insecure requests (CSP upgrade-insecure-requests) and rewrites FR24 root-relative /logo.png and /monitor.json to /fr24/... for tunneled HTTPS navigation.

---
## v3.0.13 — 2026-03-26

### Changed
- Expose /fr24 and /piaware on port 80 so aggregator tunnel dashboard target can open FR24 and FlightAware UIs.

---
## v2.59.69 — 2026-03-26

### Changed
- Patch nginx front-door so port 80 exposes canonical /fr24/ and /piaware/ for tunnel dashboard target; keeps tunnel routing compatible with aggregator links.

---
## v3.0.12 — 2026-03-26

### Changed
- Add FR24/PiAware live health probes to dashboard bootstrap and populate Data/MLAT columns (+/-) from feeder status payloads instead of container state alone.

---
## v3.0.11 — 2026-03-26

### Changed
- Fix service restart/status APIs to use Docker Compose for FR24 and PiAware instead of systemd, resolving failed restarts and stale status behavior.

---
## v3.0.10 — 2026-03-26

### Changed
- Add daily FR24/PiAware session refresh and adjust dashboard feed indicators to avoid reporting remote feed health based solely on container running state.

---
## v3.0.09 — 2026-03-26

### Changed
- Add daily FR24/PiAware session refresh and adjust dashboard feed indicators to avoid reporting remote feed health based solely on container running state.

---
## v3.0.08 — 2026-03-25

### Changed
- Updater now only auto-seeds/uses default NetBird key when no key exists and NetBird is disconnected; existing keys and active connections are left untouched during updates.

---
## v3.0.07 — 2026-03-25

### Changed
- Add TAKNET_FEEDER_MAC metadata support in Beast proxy (with MAC normalization/validation) and wire TAKNET_PS_FEEDER_MAC through config/env docs.

---
## v3.0.06 — 2026-03-25

### Changed
- Add TAKNET_FEEDER_MAC metadata support in Beast proxy (with MAC normalization/validation) and wire TAKNET_PS_FEEDER_MAC through config/env docs.

---
## v3.0.05 — 2026-03-25

### Changed
- Auto-seed NetBird setup key and enroll automatically after install/update so feeder VPN comes up without manual key entry.

---
## v3.0.04 — 2026-03-22

### Changed
- Transient update-restart console noise reduced and status polling hardening in settings.

---
## v3.0.03 — 2026-03-22

### Changed
- Dashboard SDR detection aligned with settings and updater lock handling hardened.

---
## v3.0.02 — 2026-03-22

### Changed
- UI/API restart-poll resilience improvements and additional mobile/dashboard/settings refinements.

---
## v3.0.01 — 2026-03-22

### Changed
- Release notes for auto-updater: main-branch transition complete; mobile feeder flow, dashboard tunnel restart action, settings deployment-mode UX updates, and updater reliability improvements.

---
## v3.0.0 — 2026-03-22

### Changed
- Major release: main-branch transition, mobile feeder workflow updates, and UI/runtime update reliability improvements.

---
## v2.59.68 — 2026-03-21

### Changed
- Set BIND_INTERFACE=0.0.0.0 for FR24 container so web UI works from NetBird/Tailscale (100.x) and other non-RFC1918 ranges.

---
## v2.59.67 — 2026-03-19

### Changed
- Claim key Register feeder flow with persistent submitted indicator; overnight rollout (update_priority 2).

---
## v2.59.66 — 2026-03-19

### Changed
- Persist a 'Claim submitted' indicator after Register feeder submission (localStorage) and remove old save/restart wording.

---
## v2.59.65 — 2026-03-19

### Changed
- Add Settings Register feeder button with strict claim key validation and wizard-style restart/redirect flow.

---
## v2.59.64 — 2026-03-19

### Changed
- docker compose up uses --remove-orphans so removed services (e.g. claim proxy) are cleaned up.

---
## v2.59.63 — 2026-03-19

### Changed
- Optional TAKNET_FEEDER_CLAIM line on Beast TCP when claim key is set (local proxy + Settings).

---
## v2.59.62 — 2026-03-19

### Changed
- Expose Update Now for priority 2 updates and clear scheduled flag when updating immediately.

---
## v2.59.61 — 2026-03-18

### Changed
- Show dismissal-required modal when saving periodic reboot; extend scheduler modifiers with weekly weekday + hourly on-the-hour.

---
## v2.59.60 — 2026-03-18

### Changed
- Add weekly day-of-week selector, enforce hourly on-the-hour, and allow editing the schedule while disabled.

---
## v2.59.59 — 2026-03-18

### Changed
- Add periodic reboot scheduling controls (disabled by default) with hourly/daily/weekly intervals and a selected time.

---
## v2.59.58 — 2026-03-17

### Changed
- ensure-tunnel-client.sh enables/starts tunnel when .env has aggregator URL; updater runs it; Settings restart tunnel + batch restart option.

---
## v2.59.57 — 2026-03-17

### Changed
- Longer bootstrap fetch timeout (90s) and one retry on abort; fixes AbortError on slow Pi/tunnel.

---
## v2.59.56 — 2026-03-17

### Changed
- Dashboard: connection quality removed as live metric; use Measure button and modal with on-demand ping.

---
## v2.59.55 — 2026-03-17

### Changed
- Connection quality no longer blocks bootstrap; /api/dashboard/bootstrap returns fast; quality via separate /api/network-quality after paint.

---
## v2.59.54 — 2026-03-17

### Changed
- Fix /api/dashboard/bootstrap: run SDR, TAKNET-PS stats, and network quality on main thread so Flask context works; widgets update correctly.

---
## v2.59.53 — 2026-03-17

### Changed
- Fix dashboard JS syntax and ensure widgets update via /api/dashboard/bootstrap; keep tunnel and polling improvements.

---
## v2.59.52 — 2026-03-17

### Changed
- Dashboard loads via single /api/dashboard/bootstrap; parallel backend checks; consolidated polling. Updater restarts tunnel-client.

---
## v2.59.51 — 2026-03-17

### Changed
- Feeder tunnel client routes requests by X-Tunnel-Target (dashboard vs tar1090) with path fallback; tar1090 to :8080, dashboard to app backend.

---
## v2.59.50 — 2026-03-16

### Changed
- Reverted Map and Statistics links to use direct http://<host>:8080 URLs (no origin-relative paths).

---
## v2.59.49 — 2026-03-16

### Changed
- Cursor rule: version updates go through review; user commits and pushes.

---
## v2.59.48 — 2026-03-16

### Changed
- Map and Statistics nav links use / and /graphs1090/?timeframe=24h so they work through aggregator tunnel (Host: feeder:8080).

---
## v2.59.47 — 2026-03-15

### Changed
- Tunnel registration sends host:port so aggregator can set Host header and proxy map/stats (tar1090, graphs1090) correctly.

---
## v2.59.46 — 2026-03-15

### Changed
- Tunnel registration sends host:port so aggregator can set Host header and proxy map/stats (tar1090, graphs1090) correctly.

---
## v2.59.45 — 2026-03-15

### Changed
- Tunnel registration includes host:port so aggregator proxy can set Host header for map/stats.

---
## v2.59.44 — 2026-03-15

### Changed
- Tunnel client flushes stderr after each log; service sets PYTHONUNBUFFERED=1 so journalctl shows output immediately.

---
## v2.59.43 — 2026-03-15

### Changed
- Tunnel client logs connect/register/errors to journalctl; writes /opt/adsb/var/tunnel-status.json; docs/TROUBLESHOOT-TUNNEL.md for feeder-side diagnostics.

---
## v2.59.42 — 2026-03-15

### Changed
- Reboot Device success message shown in a white box for readability.

---
## v2.59.41 — 2026-03-15

### Changed
- Tunnel service ensures websocket-client is installed before start (ExecStartPre); installer pip step more robust for updates.

---
## v2.59.40 — 2026-03-15

### Changed
- Settings: Reboot Device button; Dashboard: Remote Access Tunnel status (Running/Stopped/Disabled) and feeder ID in System Status.

---
## v2.59.39 — 2026-03-15

### Changed
- Feeder-side tunnel client for remote access by web address; enabled by default, connects to public aggregator host so access works without NetBird. Set TUNNEL_AGGREGATOR_URL= to disable.

---
## v2.59.38 — 2026-03-15

### Fixed
- Check GPS status: only report device present when device path exists (fixes false positive when GPS disconnected).

---
## v2.59.37 — 2026-03-15

### Added
- Check GPS status button and modal: detect gpsd running and GPS device present/connected.

---
## v2.59.36 — 2026-03-15

### Added
- USB GPS support at host level: gpsd and gpsd-clients installed with initial installer and on updates. "Get coordinates from GPS" in setup wizard and Settings → Location opens a modal that shows live status (satellites, accuracy), then coordinates and accuracy in meters with Accept / Try again / Cancel.

---
## v2.59.35 — 2026-03-14

### Changed
- Update priority levels: 1=immediate update, 2=overnight at 02:00, 3=alert only (default). Feeder auto-acts based on version.json update_priority.

---
## v2.59.34 — 2026-03-12

### Changed
- MLAT client name includes software version (name | vX.Y.Z) so aggregator can list feeder name and version; README documents format for aggregator.

---
## v2.59.33 — 2026-03-08

### Changed
- WiFi power save disabled on feeder to prevent connection drops to aggregators; persists across reboots and reinstalls (NetworkManager conf, systemd oneshot, network-monitor re-apply).

---
## v2.59.32 — 2026-02-28

### Changed
- Connection type and network output are driven only by NetBird; removed dead Tailscale import and clarified docstring in get_taknet_connection_status.

---
## v2.59.31 — 2026-02-28

### Changed
- NetBird management URL prefilled and hardcoded to https://netbird.tak-solutions.com. Contact email for setup key updated to mike@tak-solutions.com in Settings and README.

---
## v2.59.30 — 2026-02-28

### Changed
- Tailscale status and SSH work for any tailnet (no longer tied to tail4d77be.ts.net). Version bump script builds complete tar.gz per SOP.

---
