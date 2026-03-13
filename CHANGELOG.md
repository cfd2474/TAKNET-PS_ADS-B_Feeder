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
