#!/usr/bin/env python3
"""
TAKNET-PS Periodic Reboot

Cron-friendly checker:
- Runs frequently (typically every minute).
- Reads periodic reboot settings from /opt/adsb/config/.env.
- Computes the next scheduled reboot time based on an anchored start time.
- Reboots once when the schedule hits (prevents repeated reboots via state file).
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

try:
    from zoneinfo import ZoneInfo
except Exception:
    ZoneInfo = None  # type: ignore


ENV_FILE = Path("/opt/adsb/config/.env")
STATE_FILE = Path("/opt/adsb/var/periodic-reboot/state.json")
LOCK_FILE = Path("/opt/adsb/var/periodic-reboot/lock")
LOG_FILE = Path("/var/log/taknet-periodic-reboot.log")


def _log(msg: str) -> None:
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with LOG_FILE.open("a", encoding="utf-8") as f:
            f.write(f"{datetime.now().isoformat(timespec='seconds')} - {msg}\n")
    except Exception:
        # Logging must never break reboot scheduling.
        pass


def read_env() -> dict[str, str]:
    env: dict[str, str] = {}
    if ENV_FILE.exists():
        with ENV_FILE.open("r", encoding="utf-8", errors="ignore") as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                env[key.strip()] = value.strip()
    return env


def parse_bool(s: str | None, default: bool = False) -> bool:
    if s is None:
        return default
    v = str(s).strip().lower()
    if v in ("1", "true", "yes", "on", "enabled"):
        return True
    if v in ("0", "false", "no", "off", "disabled"):
        return False
    return default


def parse_hhmm(s: str, default: str = "02:00") -> tuple[int, int]:
    s = (s or "").strip()
    if not re.fullmatch(r"\d{2}:\d{2}", s):
        s = default
    hh_str, mm_str = s.split(":", 1)
    hh = int(hh_str)
    mm = int(mm_str)
    hh = max(0, min(23, hh))
    mm = max(0, min(59, mm))
    return hh, mm


def get_timezone(tz_name: str | None):
    tz_name = (tz_name or "").strip()
    if not tz_name:
        return None
    if ZoneInfo is None:
        return None
    try:
        return ZoneInfo(tz_name)
    except Exception:
        return None


def now_in_timezone(tz_name: str | None) -> datetime:
    # datetime.now(tz) gives local time in that tz (with DST rules).
    tz = get_timezone(tz_name)
    if tz is None:
        return datetime.now().replace(microsecond=0)
    return datetime.now(tz).replace(microsecond=0)


@dataclass(frozen=True)
class Schedule:
    enabled: bool
    unit: str  # hourly|daily|weekly
    count: int  # N
    hhmm: str
    tz_name: str | None

    def signature(self) -> str:
        payload = "|".join([self.unit, str(self.count), self.hhmm, self.tz_name or ""]).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    def interval_delta(self) -> timedelta:
        if self.unit == "hourly":
            return timedelta(hours=self.count)
        if self.unit == "daily":
            return timedelta(days=self.count)
        if self.unit == "weekly":
            return timedelta(weeks=self.count)
        return timedelta(days=self.count)


def compute_next_anchor(now: datetime, unit: str, hh: int, mm: int) -> datetime:
    """
    Anchor is the next occurrence of the selected time-of-day.

    - hourly: repeats every N hours anchored to that time-of-day
    - daily: repeats every N days anchored to that time-of-day
    - weekly: repeats every N weeks anchored to that weekday determined by anchor time
    """
    candidate = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
    if now <= candidate:
        return candidate

    # Time already passed today -> next anchor based on unit.
    if unit == "weekly":
        return candidate + timedelta(weeks=1)
    # For hourly/daily we go to tomorrow at the selected time.
    return candidate + timedelta(days=1)


def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            with STATE_FILE.open("r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_state(state: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATE_FILE.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, sort_keys=True)
    tmp.replace(STATE_FILE)


def acquire_lock() -> bool:
    try:
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(str(LOCK_FILE), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.close(fd)
        return True
    except FileExistsError:
        return False
    except Exception:
        return False


def release_lock() -> None:
    try:
        if LOCK_FILE.exists():
            LOCK_FILE.unlink()
    except Exception:
        pass


def parse_schedule_from_env(env: dict[str, str]) -> Schedule:
    enabled = parse_bool(env.get("PERIODIC_REBOOT_ENABLED"), default=False)
    unit = (env.get("PERIODIC_REBOOT_INTERVAL_UNIT") or "daily").strip().lower()
    if unit not in ("hourly", "daily", "weekly"):
        unit = "daily"

    try:
        count = int(env.get("PERIODIC_REBOOT_INTERVAL_COUNT") or "1")
    except Exception:
        count = 1
    count = max(1, min(count, 3650))  # clamp

    hhmm = (env.get("PERIODIC_REBOOT_TIME") or "02:00").strip()
    # Validate/normalize time string
    hh, mm = parse_hhmm(hhmm)
    hhmm = f"{hh:02d}:{mm:02d}"

    tz_name = env.get("FEEDER_TZ")
    if not tz_name:
        tz_name = None

    return Schedule(enabled=enabled, unit=unit, count=count, hhmm=hhmm, tz_name=tz_name)


def parse_dt(iso: str | None) -> datetime | None:
    if not iso:
        return None
    try:
        # fromisoformat handles offsets if present.
        return datetime.fromisoformat(iso)
    except Exception:
        return None


def main() -> int:
    if not acquire_lock():
        return 0

    try:
        env = read_env()
        schedule = parse_schedule_from_env(env)

        if not schedule.enabled:
            # Keep state, but record enabled false so re-enable resets anchor.
            st = load_state()
            if st.get("enabled") is not False:
                st["enabled"] = False
                save_state(st)
            return 0

        now = now_in_timezone(schedule.tz_name)
        hh, mm = parse_hhmm(schedule.hhmm)

        state = load_state()
        prev_enabled = bool(state.get("enabled", False))
        prev_sig = str(state.get("signature", ""))
        sig = schedule.signature()

        reset_anchor = (not state.get("anchor_iso")) or (prev_enabled is False) or (prev_sig != sig)

        if reset_anchor:
            anchor = compute_next_anchor(now, schedule.unit, hh, mm)
            state = {
                "enabled": True,
                "signature": sig,
                "unit": schedule.unit,
                "count": schedule.count,
                "hhmm": schedule.hhmm,
                "tz_name": schedule.tz_name,
                "anchor_iso": anchor.isoformat(),
                "last_fired_iso": None,
            }
            save_state(state)
        else:
            # Ensure enabled flag stays true.
            state["enabled"] = True
            state["signature"] = sig
            save_state(state)

        anchor_iso = state.get("anchor_iso")
        anchor_dt = parse_dt(anchor_iso)
        if anchor_dt is None:
            return 0

        last_fired_iso = state.get("last_fired_iso")
        last_fired_dt = parse_dt(last_fired_iso)

        interval = schedule.interval_delta()
        if now < anchor_dt:
            return 0

        # Compute the latest scheduled time <= now.
        delta = now - anchor_dt
        if interval.total_seconds() <= 0:
            return 0

        k = int(delta.total_seconds() // interval.total_seconds())
        scheduled_dt = anchor_dt + (k * interval)

        # If we landed exactly on a scheduled time, fire.
        # Allow a small execution delay window (<= 2 minutes).
        scheduled_epoch = scheduled_dt.timestamp()
        now_epoch = now.timestamp()

        if now_epoch < scheduled_epoch:
            return 0

        if now_epoch - scheduled_epoch > 120:
            # Too late for this cycle; don't "catch up" to avoid surprising behavior.
            return 0

        last_fired_epoch = last_fired_dt.timestamp() if last_fired_dt else None
        if last_fired_epoch is not None and abs(last_fired_epoch - scheduled_epoch) < 1:
            return 0

        _log(f"Periodic reboot due. unit={schedule.unit} count={schedule.count} time={schedule.hhmm} tz={schedule.tz_name} anchor={anchor_dt.isoformat()} scheduled={scheduled_dt.isoformat()}")

        # Update state BEFORE reboot so repeated runs don't re-trigger.
        state["last_fired_iso"] = scheduled_dt.isoformat()
        save_state(state)

        # Trigger reboot (cron typically runs as root).
        subprocess.Popen(["reboot"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        return 0

    except Exception as e:
        _log(f"Error in periodic_reboot: {e}")
        return 0
    finally:
        release_lock()


if __name__ == "__main__":
    raise SystemExit(main())

