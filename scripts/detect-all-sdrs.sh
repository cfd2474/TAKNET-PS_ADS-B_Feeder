#!/bin/bash

###############################################################################
# TAKNET-PS: Enhanced Multi-SDR Detection
# Detects all RTL-SDR devices and returns JSON with details
###############################################################################

set -e

# Output file
OUTPUT="/tmp/sdrs_detected.json"

# Check if rtl_test is available
if ! command -v rtl_test &> /dev/null; then
    echo '{"error": "rtl_test not found", "count": 0, "devices": []}'
    exit 1
fi

# Detect devices
echo "Detecting RTL-SDR devices..." >&2
DETECTION=$(rtl_test 2>&1 || true)

# Get device count
DEVICE_COUNT=$(echo "$DETECTION" | grep "^Found" | awk '{print $2}' || echo "0")

if [ "$DEVICE_COUNT" = "0" ]; then
    echo '{"count": 0, "devices": [], "message": "No RTL-SDR devices detected"}'
    exit 0
fi

echo "Found $DEVICE_COUNT RTL-SDR device(s)" >&2

# Start JSON output
cat > "$OUTPUT" << 'EOF'
{
  "count": 
EOF

echo "$DEVICE_COUNT" >> "$OUTPUT"

cat >> "$OUTPUT" << 'EOF'
,
  "devices": [
EOF

# Get details for each device
for i in $(seq 0 $((DEVICE_COUNT-1))); do
    echo "Checking device $i..." >&2
    
    # Get serial number
    SERIAL=$(rtl_eeprom -d $i 2>&1 | grep "Serial number" | awk '{print $NF}' || echo "unknown_$i")
    
    # Suggest use based on serial or index
    SUGGESTED_USE="disabled"
    if [[ "$SERIAL" == *"1090"* ]]; then
        SUGGESTED_USE="1090"
    elif [[ "$SERIAL" == *"978"* ]]; then
        SUGGESTED_USE="978"
    elif [ $i -eq 0 ]; then
        SUGGESTED_USE="1090"  # First SDR defaults to 1090
    elif [ $i -eq 1 ]; then
        SUGGESTED_USE="978"   # Second SDR defaults to 978
    fi
    
    # Add device to JSON
    cat >> "$OUTPUT" << EOF
    {
      "index": $i,
      "serial": "$SERIAL",
      "suggested_use": "$SUGGESTED_USE",
      "suggested_gain": "autogain"
    }
EOF
    
    # Add comma if not last device
    if [ $i -lt $((DEVICE_COUNT-1)) ]; then
        echo "," >> "$OUTPUT"
    fi
done

# Close JSON
cat >> "$OUTPUT" << 'EOF'

  ]
}
EOF

# Output JSON
cat "$OUTPUT"
