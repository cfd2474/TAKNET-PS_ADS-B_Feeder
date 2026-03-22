#!/usr/bin/env python3
"""
TAKNET-PS Mobile mode GPS daemon (FEEDER_DEPLOYMENT_MODE=mobile only).

- When GPS speed indicates motion: pause TAKNET_PS_MLAT (MLAT) and restart ultrafeeder.
- After motion, when speed stays in the stationary band for STATIONARY_SECONDS (drift-tolerant):
  sync FEEDER_LAT/LONG/ALT_M from GPS, resume MLAT, restart ultrafeeder.
- When not in motion, if GPS differs from configured FEEDER_LAT/LONG by more than
  DRIFT_FROM_FEEDER_RESYNC_M, resync .env from GPS (feeder position used for MLAT).
- Large jumps between consecutive GPS fixes (> POSITION_JUMP_M) reset the stationary timer.

After a reboot, .env may still have MLAT paused with no in-memory motion flag; in that case
we arm awaiting_stationary_sync so a parked 60s hold can still sync coords and resume MLAT.
"""

from __future__ import annotations

import json
import math
import os
import subprocess
import sys
import time
from pathlib import Path

ENV_FILE = Path("/opt/adsb/config/.env")
CONFIG_BUILDER = "/opt/adsb/scripts/config_builder.py"
STATE_DIR = Path("/opt/adsb/var")
STATE_FILE = STATE_DIR / "mobile-mode-state.json"
LOOP_INTERVAL_SEC = 2.0
STATIONARY_SECONDS = 60.0
MOTION_MS = 1.0
DRIFT_STATIONARY_MAX_MS = 1.2
POSITION_JUMP_M = 40.0
# When not in motion, if GPS differs from configured FEEDER_LAT/LONG by more than this, resync .env from GPS.
DRIFT_FROM_FEEDER_RESYNC_M = 30.0
RESTART_COOLDOWN_SEC = 45.0


def read_env() -> dict[str, str]:
    env: dict[str, str] = {}
    if not ENV_FILE.exists():
        return env
    with open(ENV_FILE) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                env[k.strip()] = v.strip()
    return env


def write_env(env: dict[str, str]) -> None:
    lines = [f"{k}={v}\n" for k, v in env.items()]
    with open(ENV_FILE, "w") as f:
        f.writelines(lines)


def rebuild_config() -> bool:
    r = subprocess.run(
        [sys.executable, CONFIG_BUILDER],
        cwd="/opt/adsb/config",
        capture_output=True,
        text=True,
        timeout=120,
    )
    return r.returncode == 0


def restart_ultrafeeder() -> bool:
    r = subprocess.run(
        ["systemctl", "restart", "ultrafeeder"],
        capture_output=True,
        text=True,
        timeout=180,
    )
    return r.returncode == 0


def parse_feeder_lat_lon(env: dict[str, str]) -> tuple[float, float] | None:
    """Return configured FEEDER_LAT/LONG if both parse as floats."""
    try:
        raw_lat = env.get("FEEDER_LAT", "").strip()
        raw_lon = env.get("FEEDER_LONG", "").strip()
        if not raw_lat or not raw_lon:
            return None
        return float(raw_lat), float(raw_lon)
    except (TypeError, ValueError):
        return None


def apply_gps_coords_to_env(env: dict[str, str], lat: float, lon: float, alt_m: object) -> int:
    """Set FEEDER_LAT/LONG/ALT_M from GPS and resume MLAT in .env. Returns altitude used (m)."""
    try:
        alt_int = int(round(float(alt_m))) if alt_m is not None else int(env.get("FEEDER_ALT_M", "0") or "0")
    except (TypeError, ValueError):
        alt_int = int(env.get("FEEDER_ALT_M", "0") or "0")
    env["FEEDER_LAT"] = f"{lat:.5f}"
    env["FEEDER_LONG"] = f"{lon:.5f}"
    env["FEEDER_ALT_M"] = str(alt_int)
    env["TAKNET_PS_MLAT_ENABLED"] = "true"
    return alt_int


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r_earth = 6371000.0
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r_earth * math.asin(math.sqrt(a))


def parse_gpspipe_tpv() -> dict | None:
    try:
        r = subprocess.run(
            ["timeout", "3", "gpspipe", "-w", "-n", "20"],
            capture_output=True,
            text=True,
            timeout=5,
            cwd="/opt/adsb/scripts",
            env={**os.environ},
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    last_tpv = None
    for line in (r.stdout or "").strip().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
            if obj.get("class") == "TPV":
                last_tpv = obj
        except json.JSONDecodeError:
            continue
    if not last_tpv:
        return None
    lat = last_tpv.get("lat")
    lon = last_tpv.get("lon")
    if lat is None or lon is None:
        return None
    out = {
        "lat": float(lat),
        "lon": float(lon),
        "alt": last_tpv.get("alt"),
        "speed": last_tpv.get("speed"),
        "mode": last_tpv.get("mode") or 0,
    }
    if out["speed"] is not None:
        try:
            out["speed"] = float(out["speed"])
        except (TypeError, ValueError):
            out["speed"] = None
    return out


def write_state(payload: dict) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    try:
        with open(STATE_FILE, "w") as f:
            json.dump(payload, f, indent=2)
    except OSError:
        pass


def main() -> None:
    stationary_accum = 0.0
    last_lat: float | None = None
    last_lon: float | None = None
    last_restart = 0.0
    # After motion we pause MLAT; only then do we count 60s toward GPS resync
    awaiting_stationary_sync = False

    while True:
        time.sleep(LOOP_INTERVAL_SEC)
        env = read_env()
        if env.get("FEEDER_DEPLOYMENT_MODE", "stationary").strip().lower() != "mobile":
            write_state(
                {
                    "active": False,
                    "message": "Stationary deployment mode — daemon idle",
                    "in_motion": False,
                    "stationary_seconds": 0,
                    "stationary_target_seconds": STATIONARY_SECONDS,
                    "awaiting_stationary_sync": False,
                    "mlat_paused": env.get("TAKNET_PS_MLAT_ENABLED", "true").lower() != "true",
                }
            )
            stationary_accum = 0.0
            awaiting_stationary_sync = False
            continue

        # Reboot / cold start: MLAT may still be false in .env from last session while
        # awaiting_stationary_sync was lost in RAM — arm the stationary hold so we can
        # resume without another motion event first.
        if env.get("TAKNET_PS_MLAT_ENABLED", "true").lower() != "true":
            awaiting_stationary_sync = True

        tpv = parse_gpspipe_tpv()
        mlat_on = env.get("TAKNET_PS_MLAT_ENABLED", "true").lower() == "true"

        if not tpv:
            write_state(
                {
                    "active": True,
                    "message": "No GPS fix",
                    "in_motion": None,
                    "stationary_seconds": round(stationary_accum, 1),
                    "stationary_target_seconds": STATIONARY_SECONDS,
                    "awaiting_stationary_sync": awaiting_stationary_sync,
                    "mlat_paused": not mlat_on,
                }
            )
            continue

        speed = tpv.get("speed")
        lat, lon = tpv["lat"], tpv["lon"]

        if last_lat is not None and last_lon is not None:
            jump = haversine_m(last_lat, last_lon, lat, lon)
            if jump > POSITION_JUMP_M:
                stationary_accum = 0.0
        last_lat, last_lon = lat, lon

        if speed is None:
            write_state(
                {
                    "active": True,
                    "message": "GPS fix without speed — hold timer paused",
                    "in_motion": None,
                    "stationary_seconds": round(stationary_accum, 1),
                    "stationary_target_seconds": STATIONARY_SECONDS,
                    "awaiting_stationary_sync": awaiting_stationary_sync,
                    "mlat_paused": not mlat_on,
                }
            )
            continue

        abs_speed = abs(float(speed))
        in_motion = abs_speed > MOTION_MS

        # --- In motion: pause MLAT, arm post-stop sync ---
        if in_motion:
            stationary_accum = 0.0
            awaiting_stationary_sync = True
            if mlat_on:
                env["TAKNET_PS_MLAT_ENABLED"] = "false"
                write_env(env)
                now = time.time()
                if now - last_restart >= RESTART_COOLDOWN_SEC and rebuild_config():
                    if restart_ultrafeeder():
                        last_restart = now
                mlat_on = False
            write_state(
                {
                    "active": True,
                    "message": "In motion — MLAT paused",
                    "in_motion": True,
                    "stationary_seconds": 0,
                    "stationary_target_seconds": STATIONARY_SECONDS,
                    "awaiting_stationary_sync": True,
                    "speed_mps": round(abs_speed, 2),
                    "mlat_paused": True,
                }
            )
            continue

        now = time.time()

        # Not in motion: large drift vs configured feeder (MLAT position) — resync coords from GPS
        fed = parse_feeder_lat_lon(env)
        if fed is not None:
            drift_from_feeder_m = haversine_m(fed[0], fed[1], lat, lon)
            if drift_from_feeder_m > DRIFT_FROM_FEEDER_RESYNC_M:
                alt_m = tpv.get("alt")
                alt_int = apply_gps_coords_to_env(env, lat, lon, alt_m)
                write_env(env)
                awaiting_stationary_sync = False
                stationary_accum = 0.0
                if now - last_restart >= RESTART_COOLDOWN_SEC and rebuild_config():
                    if restart_ultrafeeder():
                        last_restart = now
                write_state(
                    {
                        "active": True,
                        "message": "Position drift vs configured feeder — resynced from GPS",
                        "in_motion": False,
                        "stationary_seconds": 0,
                        "stationary_target_seconds": STATIONARY_SECONDS,
                        "awaiting_stationary_sync": False,
                        "speed_mps": round(abs_speed, 2),
                        "mlat_paused": False,
                        "drift_from_feeder_m": round(drift_from_feeder_m, 1),
                        "last_sync_lat": round(lat, 5),
                        "last_sync_lon": round(lon, 5),
                        "last_sync_alt_m": alt_int,
                    }
                )
                continue

        # Not in motion: drift-tolerant stationary band
        if abs_speed <= DRIFT_STATIONARY_MAX_MS:
            if awaiting_stationary_sync:
                stationary_accum += LOOP_INTERVAL_SEC
        else:
            stationary_accum = max(0.0, stationary_accum - LOOP_INTERVAL_SEC * 0.5)

        now = time.time()

        # --- 60s stationary after motion: sync coords, resume MLAT ---
        if awaiting_stationary_sync and stationary_accum >= STATIONARY_SECONDS:
            alt_m = tpv.get("alt")
            alt_int = apply_gps_coords_to_env(env, lat, lon, alt_m)
            write_env(env)
            awaiting_stationary_sync = False
            stationary_accum = 0.0

            if now - last_restart >= RESTART_COOLDOWN_SEC and rebuild_config():
                if restart_ultrafeeder():
                    last_restart = now

            write_state(
                {
                    "active": True,
                    "message": "Location synced from GPS — MLAT resumed",
                    "in_motion": False,
                    "stationary_seconds": 0,
                    "stationary_target_seconds": STATIONARY_SECONDS,
                    "awaiting_stationary_sync": False,
                    "speed_mps": round(abs_speed, 2),
                    "mlat_paused": False,
                    "last_sync_lat": round(lat, 5),
                    "last_sync_lon": round(lon, 5),
                    "last_sync_alt_m": alt_int,
                }
            )
            continue

        # Waiting for 60s hold (after motion)
        if awaiting_stationary_sync:
            write_state(
                {
                    "active": True,
                    "message": "Stopped — holding stationary before GPS sync",
                    "in_motion": False,
                    "stationary_seconds": round(stationary_accum, 1),
                    "stationary_target_seconds": STATIONARY_SECONDS,
                    "awaiting_stationary_sync": True,
                    "speed_mps": round(abs_speed, 2),
                    "mlat_paused": True,
                }
            )
            continue

        # Parked / idle (no pending sync after motion)
        write_state(
            {
                "active": True,
                "message": "Mobile mode — parked (no sync pending)",
                "in_motion": False,
                "stationary_seconds": 0,
                "stationary_target_seconds": STATIONARY_SECONDS,
                "awaiting_stationary_sync": False,
                "speed_mps": round(abs_speed, 2),
                "mlat_paused": not mlat_on,
            }
        )


if __name__ == "__main__":
    main()
