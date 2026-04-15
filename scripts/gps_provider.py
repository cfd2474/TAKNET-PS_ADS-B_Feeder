#!/usr/bin/env python3
"""
GPS provider abstraction for TAKNET-PS ADS-B Feeder.

Reads GPS_SOURCE / GPS_NETWORK_HOST / GPS_NETWORK_PORT / GPS_NETWORK_PROTOCOL
from .env and provides a uniform interface for all GPS consumers:

  - get-gps-coordinates.py   (one-shot coordinate grab)
  - app.py                   (web API GPS endpoints)
  - mobile-mode-gps.py       (mobile mode daemon)

Supported sources
-----------------
  usb      — local gpsd + USB receiver  (default, existing behaviour)
  network  — remote gpsd *or* raw NMEA-over-TCP
  disabled — no GPS hardware; manual coordinates only
"""

from __future__ import annotations

import json
import os
import re
import socket
import subprocess
import time
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# .env helpers
# ---------------------------------------------------------------------------

ENV_FILE = Path("/opt/adsb/config/.env")


def read_env(env_file: Path | None = None) -> dict[str, str]:
    """Read .env file and return as dict, handling optional quotes."""
    path = env_file or ENV_FILE
    env: dict[str, str] = {}
    if not path.exists():
        return env
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                k = k.strip()
                v = v.strip()
                # Strip matching quote pairs
                if len(v) >= 2 and (
                    (v[0] == '"' and v[-1] == '"')
                    or (v[0] == "'" and v[-1] == "'")
                ):
                    v = v[1:-1]
                    v = v.replace('\\"', '"')
                env[k] = v
    return env


# ---------------------------------------------------------------------------
# Source resolution
# ---------------------------------------------------------------------------


def get_gps_source(env: dict[str, str]) -> tuple[str, str | None, int, str]:
    """Return ``(source_type, host, port, protocol)`` from env config.

    *source_type* is one of ``usb``, ``network``, or ``disabled``.
    *protocol* is ``gpsd`` or ``nmea`` (only relevant when *source_type* is
    ``network``).
    """
    source = (env.get("GPS_SOURCE") or "usb").strip().lower()
    if source not in ("usb", "network", "disabled"):
        source = "usb"

    host: str | None = (env.get("GPS_NETWORK_HOST") or "").strip() or None
    try:
        port = int(env.get("GPS_NETWORK_PORT", "2947"))
    except (TypeError, ValueError):
        port = 2947

    protocol = (env.get("GPS_NETWORK_PROTOCOL") or "gpsd").strip().lower()
    if protocol not in ("gpsd", "nmea"):
        protocol = "gpsd"

    return source, host, port, protocol


# ---------------------------------------------------------------------------
# gpspipe command builder
# ---------------------------------------------------------------------------


def build_gpspipe_cmd(
    env: dict[str, str],
    n_lines: int = 20,
    timeout: int = 3,
) -> list[str] | None:
    """Build a ``gpspipe`` command list for the configured GPS source.

    Returns ``None`` when the source is ``disabled`` or ``network`` with
    the ``nmea`` protocol (the caller should use :func:`read_nmea_tcp`
    instead).
    """
    source, host, port, protocol = get_gps_source(env)

    if source == "disabled":
        return None

    if source == "network":
        if not host:
            return None
        if protocol == "nmea":
            # Raw NMEA is handled by read_nmea_tcp, not gpspipe
            return None
        # Remote gpsd — gpspipe accepts host:port as the last positional arg
        return [
            "timeout", str(timeout),
            "gpspipe", "-w", "-n", str(n_lines),
            f"{host}:{port}",
        ]

    # USB (local gpsd) — existing behaviour
    return [
        "timeout", str(timeout),
        "gpspipe", "-w", "-n", str(n_lines),
    ]


# ---------------------------------------------------------------------------
# NMEA sentence parser
# ---------------------------------------------------------------------------

def _nmea_dm_to_dd(dm_str: str, hemisphere: str) -> float | None:
    """Convert NMEA degrees+minutes (DDMM.MMMMM) to decimal degrees."""
    if not dm_str:
        return None
    try:
        # Find decimal point to split degrees from minutes
        dot = dm_str.index(".")
        degrees = int(dm_str[: dot - 2])
        minutes = float(dm_str[dot - 2 :])
        dd = degrees + minutes / 60.0
        if hemisphere in ("S", "W"):
            dd = -dd
        return round(dd, 5)
    except (ValueError, IndexError):
        return None


def parse_nmea_sentence(sentence: str) -> dict[str, Any] | None:
    """Parse a single NMEA sentence and return available fields.

    Supported sentences: ``$GPRMC``, ``$GNRMC``, ``$GPGGA``, ``$GNGGA``.
    Returns a partial dict — callers merge multiple sentences for a full fix.
    """
    sentence = sentence.strip()
    if not sentence.startswith("$"):
        return None

    # Validate checksum if present
    if "*" in sentence:
        body, _, cksum_str = sentence[1:].partition("*")
        try:
            expected = int(cksum_str[:2], 16)
            computed = 0
            for ch in body:
                computed ^= ord(ch)
            if computed != expected:
                return None
        except (ValueError, IndexError):
            pass
    else:
        body = sentence[1:]

    parts = body.split(",")
    if len(parts) < 2:
        return None

    talker_sentence = parts[0]  # e.g. "GPRMC" or "GNGGA"

    out: dict[str, Any] = {}

    if talker_sentence.endswith("RMC"):
        # $G?RMC,time,status,lat,N/S,lon,E/W,speed_kn,course,date,...
        if len(parts) < 10:
            return None
        status = parts[2]
        if status != "A":  # A=active, V=void
            return None
        lat = _nmea_dm_to_dd(parts[3], parts[4])
        lon = _nmea_dm_to_dd(parts[5], parts[6])
        if lat is None or lon is None:
            return None
        out["lat"] = lat
        out["lon"] = lon
        # Speed in knots → m/s
        try:
            out["speed"] = round(float(parts[7]) * 0.514444, 2)
        except (ValueError, IndexError):
            out["speed"] = None

    elif talker_sentence.endswith("GGA"):
        # $G?GGA,time,lat,N/S,lon,E/W,quality,satellites,hdop,alt,M,...
        if len(parts) < 10:
            return None
        quality = parts[6]
        if quality == "0":
            return None  # no fix
        lat = _nmea_dm_to_dd(parts[2], parts[3])
        lon = _nmea_dm_to_dd(parts[4], parts[5])
        if lat is None or lon is None:
            return None
        out["lat"] = lat
        out["lon"] = lon
        # Satellites in use
        try:
            out["satellites_used"] = int(parts[7])
        except (ValueError, IndexError):
            pass
        # Altitude
        try:
            out["alt"] = round(float(parts[9]))
        except (ValueError, IndexError):
            pass
        # Fix quality → mode
        try:
            q = int(quality)
            out["mode"] = "3D" if q >= 2 else "2D"
        except ValueError:
            pass
    else:
        return None

    return out or None


# ---------------------------------------------------------------------------
# Raw NMEA-over-TCP reader
# ---------------------------------------------------------------------------


def read_nmea_tcp(
    host: str,
    port: int,
    timeout: float = 5.0,
) -> dict[str, Any] | None:
    """Connect to a raw NMEA TCP stream, read sentences, and return a fix.

    Merges fields from RMC and GGA sentences for a complete position.
    Returns ``{lat, lon, alt, speed, mode, satellites_used}`` or ``None``.
    """
    merged: dict[str, Any] = {}
    try:
        with socket.create_connection((host, port), timeout=timeout) as sock:
            sock.settimeout(timeout)
            buf = ""
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                try:
                    data = sock.recv(4096)
                except socket.timeout:
                    break
                if not data:
                    break
                buf += data.decode("ascii", errors="ignore")
                while "\n" in buf:
                    line, buf = buf.split("\n", 1)
                    parsed = parse_nmea_sentence(line)
                    if parsed:
                        merged.update(parsed)
                        # We have enough for a fix once we have lat+lon
                        if "lat" in merged and "lon" in merged:
                            return merged
    except (OSError, socket.timeout, ConnectionRefusedError):
        return None
    return merged if "lat" in merged and "lon" in merged else None


# ---------------------------------------------------------------------------
# gpspipe output parser
# ---------------------------------------------------------------------------


def parse_gpspipe_output(stdout: str) -> dict[str, Any] | None:
    """Parse gpspipe JSON output and return the last valid TPV fix.

    Returns ``{lat, lon, alt, speed, mode}`` or ``None``.
    """
    last_tpv: dict[str, Any] | None = None
    for line in (stdout or "").strip().splitlines():
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

    mode_raw = last_tpv.get("mode") or 0
    if mode_raw == 3:
        mode_str = "3D"
    elif mode_raw == 2:
        mode_str = "2D"
    else:
        mode_str = None

    out: dict[str, Any] = {
        "lat": round(float(lat), 5),
        "lon": round(float(lon), 5),
        "alt": last_tpv.get("alt"),
        "speed": last_tpv.get("speed"),
        "mode": mode_str,
    }

    # Horizontal accuracy from epx/epy
    import math

    epx = last_tpv.get("epx")
    epy = last_tpv.get("epy")
    if epx is not None and epy is not None:
        try:
            out["accuracy_m"] = round(math.sqrt(float(epx) ** 2 + float(epy) ** 2), 1)
        except (TypeError, ValueError):
            pass

    # Satellites from SKY class are not in TPV, but leave the key for merging
    return out


# ---------------------------------------------------------------------------
# Unified GPS fix entry-point
# ---------------------------------------------------------------------------


def get_gps_fix(
    env: dict[str, str],
    timeout: float = 15.0,
    n_lines: int = 30,
) -> dict[str, Any] | None:
    """Get a GPS fix from whatever source is configured.

    Dispatches to ``gpspipe`` (usb / network-gpsd) or :func:`read_nmea_tcp`
    (network-nmea).

    Returns ``{lat, lon, alt, speed, mode, ...}`` or ``None``.
    """
    source, host, port, protocol = get_gps_source(env)

    if source == "disabled":
        return None

    if source == "network" and protocol == "nmea":
        if not host:
            return None
        return read_nmea_tcp(host, port, timeout=timeout)

    # USB or network-gpsd — use gpspipe
    cmd = build_gpspipe_cmd(env, n_lines=n_lines, timeout=int(timeout))
    if not cmd:
        return None

    try:
        r = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout + 2,
            cwd="/opt/adsb/scripts",
            env={**os.environ},
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None

    return parse_gpspipe_output(r.stdout)


# ---------------------------------------------------------------------------
# Unified status check
# ---------------------------------------------------------------------------


def check_gps_status(env: dict[str, str]) -> dict[str, Any]:
    """Check whether the configured GPS source is reachable and has a fix.

    Returns::

        {
            "source":    "usb" | "network" | "disabled",
            "protocol":  "gpsd" | "nmea" | None,
            "available": bool,
            "message":   str,
            "details":   dict,
        }
    """
    source, host, port, protocol = get_gps_source(env)
    out: dict[str, Any] = {
        "source": source,
        "protocol": protocol if source == "network" else None,
        "available": False,
        "message": "",
        "details": {},
    }

    if source == "disabled":
        out["message"] = "GPS is disabled. Use manual coordinates in Settings."
        return out

    # --- Network ---
    if source == "network":
        if not host:
            out["message"] = "GPS_NETWORK_HOST is not configured. Set it in Settings → Location."
            return out

        # TCP connectivity test
        try:
            with socket.create_connection((host, port), timeout=3):
                out["details"]["tcp"] = f"Connected to {host}:{port}"
        except (OSError, socket.timeout, ConnectionRefusedError) as exc:
            out["message"] = f"Cannot connect to {host}:{port} — {exc}"
            out["details"]["tcp"] = str(exc)
            return out

        if protocol == "nmea":
            fix = read_nmea_tcp(host, port, timeout=5.0)
            if fix and fix.get("lat") is not None:
                out["available"] = True
                mode = fix.get("mode", "")
                sats = fix.get("satellites_used")
                msg_parts = ["NMEA stream is active"]
                if mode:
                    msg_parts.append(f"{mode} fix")
                if sats is not None:
                    msg_parts.append(f"{sats} satellites")
                out["message"] = " — ".join(msg_parts) + "."
                out["details"]["fix"] = fix
            else:
                out["message"] = f"Connected to {host}:{port} but no valid NMEA fix received."
            return out

        # Remote gpsd
        cmd = build_gpspipe_cmd(env, n_lines=15, timeout=3)
        if cmd:
            try:
                r = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=5,
                    cwd="/opt/adsb/scripts",
                    env={**os.environ},
                )
                fix = parse_gpspipe_output(r.stdout)
                if fix and fix.get("lat") is not None:
                    out["available"] = True
                    out["message"] = (
                        f"Remote gpsd at {host}:{port} is reachable and has a fix."
                    )
                    out["details"]["fix"] = fix
                else:
                    out["message"] = (
                        f"Remote gpsd at {host}:{port} is reachable but no fix."
                    )
            except (FileNotFoundError, subprocess.TimeoutExpired):
                out["message"] = (
                    f"Connected to {host}:{port} but gpspipe timed out."
                )
        return out

    # --- USB (local gpsd) ---
    # Check if gpsd is running
    gpsd_running = False
    try:
        r = subprocess.run(
            ["systemctl", "is-active", "gpsd"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        gpsd_running = r.returncode == 0 and (r.stdout or "").strip() == "active"
    except (FileNotFoundError, subprocess.TimeoutExpired):
        try:
            r = subprocess.run(
                ["pgrep", "-x", "gpsd"],
                capture_output=True,
                timeout=5,
            )
            gpsd_running = r.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

    out["details"]["gpsd_running"] = gpsd_running

    if not gpsd_running:
        out["message"] = (
            "gpsd is not running. Run the installer or start gpsd "
            "(e.g. sudo systemctl start gpsd)."
        )
        return out

    # Check for a connected USB device via gpspipe
    gps_present = False
    try:
        r = subprocess.run(
            ["timeout", "3", "gpspipe", "-w", "-n", "15"],
            capture_output=True,
            text=True,
            timeout=5,
            cwd="/opt/adsb/scripts",
            env={**os.environ},
        )
        for line in (r.stdout or "").strip().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                cls = obj.get("class")
                if cls == "DEVICES":
                    for dev in obj.get("devices") or []:
                        path = dev.get("path")
                        if path and Path(path).exists():
                            gps_present = True
                            out["details"]["device"] = path
                            break
                elif cls == "TPV":
                    dev_path = obj.get("device")
                    if (
                        isinstance(dev_path, str)
                        and dev_path.startswith("/")
                        and Path(dev_path).exists()
                    ):
                        gps_present = True
                        out["details"]["device"] = dev_path
                    if gps_present and obj.get("mode") is not None:
                        mode_val = obj.get("mode")
                        out["details"]["mode"] = (
                            "3D" if mode_val == 3
                            else ("2D" if mode_val == 2 else "no fix")
                        )
            except json.JSONDecodeError:
                continue
    except FileNotFoundError:
        out["details"]["gpspipe"] = "gpspipe not found (install gpsd-clients)"
    except subprocess.TimeoutExpired:
        out["details"]["note"] = "gpspipe timed out (no data from gpsd in 3s)"

    out["available"] = gps_present
    if gps_present:
        out["message"] = (
            'GPS is present and gpsd is running. You can use "Get coordinates from GPS".'
        )
    else:
        out["message"] = (
            "gpsd is running but no GPS device data received. "
            "Check USB connection and device (e.g. /dev/ttyUSB0)."
        )

    return out


# ---------------------------------------------------------------------------
# Network connection test (for Settings "Test Connection" button)
# ---------------------------------------------------------------------------


def test_network_connection(
    host: str, port: int, protocol: str, timeout: float = 5.0
) -> dict[str, Any]:
    """Test connectivity to a network GPS source.

    Returns ``{"success": bool, "message": str, "details": dict}``.
    """
    out: dict[str, Any] = {"success": False, "message": "", "details": {}}

    if not host:
        out["message"] = "Host is required."
        return out

    # TCP connectivity
    try:
        with socket.create_connection((host, port), timeout=timeout):
            out["details"]["tcp"] = f"TCP connected to {host}:{port}"
    except (OSError, socket.timeout, ConnectionRefusedError) as exc:
        out["message"] = f"Connection failed: {exc}"
        out["details"]["tcp"] = str(exc)
        return out

    if protocol == "nmea":
        fix = read_nmea_tcp(host, port, timeout=timeout)
        if fix and fix.get("lat") is not None:
            out["success"] = True
            parts = [f"Connected to {host}:{port}"]
            mode = fix.get("mode")
            sats = fix.get("satellites_used")
            if mode:
                parts.append(f"{mode} fix")
            if sats is not None:
                parts.append(f"{sats} satellites")
            out["message"] = " — ".join(parts)
            out["details"]["fix"] = fix
        else:
            out["message"] = (
                f"TCP connected to {host}:{port} but no valid NMEA data received. "
                "Ensure the device is sending NMEA sentences ($GPRMC, $GPGGA)."
            )
        return out

    # gpsd protocol
    cmd = [
        "timeout", str(int(timeout)),
        "gpspipe", "-w", "-n", "15",
        f"{host}:{port}",
    ]
    try:
        r = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout + 2,
            cwd="/opt/adsb/scripts",
            env={**os.environ},
        )
        fix = parse_gpspipe_output(r.stdout)
        if fix and fix.get("lat") is not None:
            out["success"] = True
            parts = [f"Connected to gpsd at {host}:{port}"]
            mode = fix.get("mode")
            acc = fix.get("accuracy_m")
            if mode:
                parts.append(f"{mode} fix")
            if acc is not None:
                parts.append(f"~{acc}m accuracy")
            out["message"] = " — ".join(parts)
            out["details"]["fix"] = fix
        else:
            out["message"] = (
                f"gpsd at {host}:{port} is reachable but returned no fix. "
                "Ensure the remote gpsd has a GPS device connected."
            )
    except FileNotFoundError:
        out["message"] = "gpspipe not found. Install gpsd-clients."
    except subprocess.TimeoutExpired:
        out["message"] = f"gpspipe timed out connecting to {host}:{port}."

    return out
