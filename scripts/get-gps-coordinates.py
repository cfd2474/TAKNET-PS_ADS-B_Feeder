#!/usr/bin/env python3
"""
Get current GPS coordinates (USB, network gpsd, or raw NMEA-over-TCP).

Outputs JSON:
  {"success": true, "lat": 33.12345, "lon": -117.12345, "alt": 100}
  {"success": false, "message": "..."}

Replaces get-gps-coordinates.sh — uses gps_provider for source-aware logic.
Used by the web UI "Get coordinates from GPS" button (setup wizard and settings).
"""

import json
import sys

sys.path.insert(0, "/opt/adsb/scripts")
from gps_provider import get_gps_fix, read_env  # noqa: E402

env = read_env()
result = get_gps_fix(env, timeout=15.0)
if result and result.get("lat") is not None:
    out = {
        "success": True,
        "lat": round(result["lat"], 5),
        "lon": round(result["lon"], 5),
    }
    alt = result.get("alt")
    if alt is not None:
        out["alt"] = int(round(float(alt)))
    else:
        out["alt"] = None
    print(json.dumps(out))
else:
    print(
        json.dumps(
            {
                "success": False,
                "message": "No GPS fix. Check source configuration in Settings.",
            }
        )
    )
