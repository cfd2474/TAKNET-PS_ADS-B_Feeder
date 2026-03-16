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
