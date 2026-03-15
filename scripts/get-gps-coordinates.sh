#!/bin/bash
# Get current GPS coordinates from gpsd (USB GPS).
# Outputs JSON: {"success": true, "lat": 33.12345, "lon": -117.12345, "alt": 100}
# or {"success": false, "message": "..."}
# Used by the web UI "Get coordinates from GPS" button (setup wizard and settings).

set -e

TIMEOUT=15
TPV_LIMIT=30

if ! command -v gpspipe &>/dev/null; then
    echo '{"success": false, "message": "gpsd-clients not installed. Run the installer or update."}'
    exit 0
fi

# Wait for first TPV report that has lat/lon (timeout 15s)
OUTPUT=$(timeout "$TIMEOUT" gpspipe -w -n "$TPV_LIMIT" 2>/dev/null | while read -r line; do
    if echo "$line" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    if d.get('class') == 'TPV' and d.get('lat') is not None and d.get('lon') is not None:
        sys.exit(0)
except Exception:
    pass
sys.exit(1)
" 2>/dev/null; then
        echo "$line"
        break
    fi
done)

if [ -z "$OUTPUT" ]; then
    echo '{"success": false, "message": "No GPS fix (timeout or no USB GPS connected). Ensure GPS has sky view and gpsd is running."}'
    exit 0
fi

echo "$OUTPUT" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    lat = d.get('lat')
    lon = d.get('lon')
    alt = d.get('alt')
    if lat is None or lon is None:
        print(json.dumps({'success': False, 'message': 'No lat/lon in GPS data'}))
    else:
        out = {'success': True, 'lat': round(lat, 5), 'lon': round(lon, 5)}
        if alt is not None:
            out['alt'] = int(round(alt))
        else:
            out['alt'] = None
        print(json.dumps(out))
except Exception as e:
    print(json.dumps({'success': False, 'message': str(e)}))
"
exit 0
