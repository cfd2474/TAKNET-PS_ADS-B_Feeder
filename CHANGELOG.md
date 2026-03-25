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
