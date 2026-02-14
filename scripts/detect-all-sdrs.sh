#!/bin/bash

###############################################################################
# TAKNET-PS: Enhanced Multi-SDR Detection
# Detects RTL-SDR devices AND FTDI-based UATRadio devices
# Returns unified JSON with all devices
###############################################################################

set -e

# Output file
OUTPUT="/tmp/sdrs_detected.json"

# Device arrays
declare -a ALL_DEVICES=()
declare -a DEVICE_TYPES=()
declare -a DEVICE_SERIALS=()
declare -a SUGGESTED_USE=()
declare -a DEVICE_PATHS=()

echo "Scanning for SDR devices..." >&2

###############################################################################
# 1. Detect RTL-SDR devices (Realtek chipset)
###############################################################################

RTL_COUNT=0
if command -v rtl_test &> /dev/null; then
    echo "Checking for RTL-SDR devices..." >&2
    DETECTION=$(rtl_test 2>&1 || true)
    RTL_COUNT=$(echo "$DETECTION" | grep "^Found" | awk '{print $2}' || echo "0")
    
    if [ "$RTL_COUNT" != "0" ]; then
        echo "Found $RTL_COUNT RTL-SDR device(s)" >&2
        
        for i in $(seq 0 $((RTL_COUNT-1))); do
            # Get serial number
            SERIAL=$(rtl_eeprom -d $i 2>&1 | grep "Serial number" | awk '{print $NF}' || echo "")
            
            # If no serial or empty, set to N/A
            if [ -z "$SERIAL" ] || [ "$SERIAL" = "00000000" ] || [[ "$SERIAL" == rtlsdr_* ]]; then
                SERIAL="N/A"
            fi
            
            # Suggest use based on serial
            USE="disabled"
            if [[ "$SERIAL" == *"1090"* ]]; then
                USE="1090"
            elif [[ "$SERIAL" == *"978"* ]]; then
                USE="978"
            elif [ $i -eq 0 ]; then
                USE="1090"  # First RTL-SDR defaults to 1090
            fi
            
            ALL_DEVICES+=("RTL-SDR #$i")
            DEVICE_TYPES+=("rtlsdr")
            DEVICE_SERIALS+=("$SERIAL")
            SUGGESTED_USE+=("$USE")
            DEVICE_PATHS+=("$i")
            
            echo "  - RTL-SDR device $i: $SERIAL (suggested: $USE)" >&2
        done
    fi
else
    echo "rtl_test not found, skipping RTL-SDR detection" >&2
fi

###############################################################################
# 2. Detect FTDI UATRadio devices (Stratux hardware)
###############################################################################

FTDI_COUNT=0
if command -v lsusb &> /dev/null; then
    echo "Checking for FTDI UATRadio devices..." >&2
    
    # Look for FTDI devices with UATRadio in product name
    FTDI_LINES=$(lsusb | grep -i "UATRadio" || echo "")
    
    if [ -n "$FTDI_LINES" ]; then
        while IFS= read -r line; do
            [ -z "$line" ] && continue
            
            echo "Found FTDI UATRadio device" >&2
            
            # Try to get serial from lsusb -v
            BUS=$(echo "$line" | awk '{print $2}')
            DEV=$(echo "$line" | awk '{print $4}' | tr -d ':')
            
            SERIAL=$(lsusb -v -s ${BUS}:${DEV} 2>/dev/null | grep "iSerial" | awk '{print $3}' || echo "")
            
            # If no serial or empty, set to N/A
            if [ -z "$SERIAL" ] || [[ "$SERIAL" == uatradio_* ]]; then
                SERIAL="N/A"
            fi
            
            # Find the /dev/serial/by-id path for this device
            DEV_PATH=""
            for path in /dev/serial/by-id/*; do
                if [ -e "$path" ]; then
                    # Check if this is an FTDI or Stratux device
                    if [[ "$path" == *"FTDI"* ]] || [[ "$path" == *"Stratux"* ]]; then
                        DEV_PATH="$path"
                        break
                    fi
                fi
            done
            
            # Fallback to /dev/ttyUSB0 if no by-id found
            if [ -z "$DEV_PATH" ]; then
                if [ -e "/dev/ttyUSB0" ]; then
                    DEV_PATH="/dev/ttyUSB0"
                else
                    DEV_PATH="/dev/ttyUSB0"  # Will fail later, but document expected path
                fi
            fi
            
            ALL_DEVICES+=("FTDI UATRadio")
            DEVICE_TYPES+=("ftdi")
            DEVICE_SERIALS+=("$SERIAL")
            SUGGESTED_USE+=("978")  # UATRadio is 978 MHz only
            DEVICE_PATHS+=("$DEV_PATH")
            
            FTDI_COUNT=$((FTDI_COUNT + 1))
            
            echo "  - FTDI UATRadio: $SERIAL → $DEV_PATH (978 MHz only)" >&2
            
        done <<< "$FTDI_LINES"
    fi
else
    echo "lsusb not found, skipping FTDI detection" >&2
fi

###############################################################################
# 3. Generate unified JSON output
###############################################################################

TOTAL_COUNT=$((RTL_COUNT + FTDI_COUNT))

if [ "$TOTAL_COUNT" = "0" ]; then
    echo '{"count": 0, "devices": [], "message": "No SDR devices detected"}' > "$OUTPUT"
    echo '{"count": 0, "devices": [], "message": "No SDR devices detected"}'
    exit 0
fi

echo "Total devices detected: $TOTAL_COUNT" >&2

# Start JSON - use echo instead of cat
echo "{" > "$OUTPUT"
echo "  \"count\": $TOTAL_COUNT," >> "$OUTPUT"
echo "  \"devices\": [" >> "$OUTPUT"

# Add each device to JSON
for idx in "${!ALL_DEVICES[@]}"; do
    DEVICE_NAME="${ALL_DEVICES[$idx]}"
    DEVICE_TYPE="${DEVICE_TYPES[$idx]}"
    SERIAL="${DEVICE_SERIALS[$idx]}"
    USE="${SUGGESTED_USE[$idx]}"
    PATH="${DEVICE_PATHS[$idx]}"
    
    # Determine if device can do 1090/978
    SUPPORTS_1090="true"
    SUPPORTS_978="true"
    if [ "$DEVICE_TYPE" = "ftdi" ]; then
        SUPPORTS_1090="false"
        SUPPORTS_978="true"
    fi
    
    # Build device JSON using echo
    echo "    {" >> "$OUTPUT"
    echo "      \"index\": $idx," >> "$OUTPUT"
    echo "      \"name\": \"$DEVICE_NAME\"," >> "$OUTPUT"
    echo "      \"type\": \"$DEVICE_TYPE\"," >> "$OUTPUT"
    echo "      \"serial\": \"$SERIAL\"," >> "$OUTPUT"
    echo "      \"device_path\": \"$PATH\"," >> "$OUTPUT"
    echo "      \"suggested_use\": \"$USE\"," >> "$OUTPUT"
    echo "      \"suggested_gain\": \"autogain\"," >> "$OUTPUT"
    echo "      \"supports_1090\": $SUPPORTS_1090," >> "$OUTPUT"
    echo "      \"supports_978\": $SUPPORTS_978" >> "$OUTPUT"
    
    # Add comma if not last device
    if [ $idx -lt $((TOTAL_COUNT - 1)) ]; then
        echo "    }," >> "$OUTPUT"
    else
        echo "    }" >> "$OUTPUT"
    fi
done

# Close JSON
echo "  ]" >> "$OUTPUT"
echo "}" >> "$OUTPUT"

# Output JSON (use shell built-in instead of cat)
while IFS= read -r line; do
    echo "$line"
done < "$OUTPUT"

echo "Detection complete!" >&2
