#!/bin/bash

###############################################################################
# TAKNET-PS: Universal Multi-SDR Detection (SoapySDR + Legacy)
# Detects ALL SDR types via SoapySDR, falls back to RTL-SDR native detection
# Phase A: Detection only - configuration still uses native drivers
###############################################################################

set -e

# Output file
OUTPUT="/tmp/sdrs_detected.json"

# Device arrays
declare -a ALL_DEVICES=()
declare -a DEVICE_TYPES=()
declare -a DEVICE_DRIVERS=()
declare -a DEVICE_SERIALS=()
declare -a SUGGESTED_USE=()
declare -a DEVICE_PATHS=()
declare -a DEVICE_LABELS=()
declare -a SOAPY_STRINGS=()

SOAPY_AVAILABLE="false"
DETECTION_METHOD="legacy"

echo "Scanning for SDR devices..." >&2

###############################################################################
# 1. Try SoapySDR Universal Detection (Preferred)
###############################################################################

if command -v SoapySDRUtil &> /dev/null; then
    echo "SoapySDR detected - using universal detection..." >&2
    SOAPY_AVAILABLE="true"
    DETECTION_METHOD="soapysdr"
    
    # Run SoapySDR detection
    SOAPY_OUTPUT=$(timeout 5 SoapySDRUtil --find 2>&1 || true)
    
    if [ -n "$SOAPY_OUTPUT" ]; then
        # Parse SoapySDR output
        # Format varies by device, but generally:
        # Found device 0
        #   driver = rtlsdr
        #   label = Generic RTL2832U :: 00001090
        #   serial = 00001090
        
        DEVICE_COUNT=0
        CURRENT_DRIVER=""
        CURRENT_SERIAL=""
        CURRENT_LABEL=""
        
        while IFS= read -r line; do
            # New device starts with "Found device"
            if [[ "$line" =~ ^Found\ device\ ([0-9]+) ]]; then
                # Save previous device if exists
                if [ -n "$CURRENT_DRIVER" ]; then
                    # Determine device type
                    if [ "$CURRENT_DRIVER" = "rtlsdr" ]; then
                        DEVICE_TYPE="rtlsdr"
                    elif [ "$CURRENT_DRIVER" = "airspy" ]; then
                        DEVICE_TYPE="airspy"
                    elif [ "$CURRENT_DRIVER" = "hackrf" ]; then
                        DEVICE_TYPE="hackrf"
                    else
                        DEVICE_TYPE="soapy"
                    fi
                    
                    # Suggest use based on serial or device type
                    USE="disabled"
                    if [[ "$CURRENT_SERIAL" == *"1090"* ]]; then
                        USE="1090"
                    elif [[ "$CURRENT_SERIAL" == *"978"* ]]; then
                        USE="978"
                    elif [ "$DEVICE_COUNT" -eq 0 ]; then
                        USE="1090"  # First device defaults to 1090
                    fi
                    
                    # Build SoapySDR device string
                    if [ -n "$CURRENT_SERIAL" ] && [ "$CURRENT_SERIAL" != "0" ]; then
                        SOAPY_STR="driver=${CURRENT_DRIVER},serial=${CURRENT_SERIAL}"
                    else
                        SOAPY_STR="driver=${CURRENT_DRIVER},index=${DEVICE_COUNT}"
                    fi
                    
                    ALL_DEVICES+=("${CURRENT_DRIVER^^} #${DEVICE_COUNT}")
                    DEVICE_TYPES+=("$DEVICE_TYPE")
                    DEVICE_DRIVERS+=("$CURRENT_DRIVER")
                    DEVICE_SERIALS+=("$CURRENT_SERIAL")
                    SUGGESTED_USE+=("$USE")
                    DEVICE_PATHS+=("$DEVICE_COUNT")
                    DEVICE_LABELS+=("$CURRENT_LABEL")
                    SOAPY_STRINGS+=("$SOAPY_STR")
                    
                    echo "  - ${CURRENT_DRIVER} device $DEVICE_COUNT: Serial=$CURRENT_SERIAL (suggested: $USE)" >&2
                fi
                
                # Reset for new device
                DEVICE_COUNT=$((DEVICE_COUNT + 1))
                CURRENT_DRIVER=""
                CURRENT_SERIAL=""
                CURRENT_LABEL=""
            fi
            
            # Parse driver
            if [[ "$line" =~ driver[[:space:]]*=[[:space:]]*(.*) ]]; then
                CURRENT_DRIVER="${BASH_REMATCH[1]}"
                CURRENT_DRIVER="${CURRENT_DRIVER// /}"  # Remove whitespace
            fi
            
            # Parse serial
            if [[ "$line" =~ serial[[:space:]]*=[[:space:]]*(.*) ]]; then
                CURRENT_SERIAL="${BASH_REMATCH[1]}"
                CURRENT_SERIAL="${CURRENT_SERIAL// /}"  # Remove whitespace
            fi
            
            # Parse label
            if [[ "$line" =~ label[[:space:]]*=[[:space:]]*(.*) ]]; then
                CURRENT_LABEL="${BASH_REMATCH[1]}"
            fi
            
        done <<< "$SOAPY_OUTPUT"
        
        # Don't forget the last device
        if [ -n "$CURRENT_DRIVER" ]; then
            if [ "$CURRENT_DRIVER" = "rtlsdr" ]; then
                DEVICE_TYPE="rtlsdr"
            elif [ "$CURRENT_DRIVER" = "airspy" ]; then
                DEVICE_TYPE="airspy"
            elif [ "$CURRENT_DRIVER" = "hackrf" ]; then
                DEVICE_TYPE="hackrf"
            else
                DEVICE_TYPE="soapy"
            fi
            
            USE="disabled"
            if [[ "$CURRENT_SERIAL" == *"1090"* ]]; then
                USE="1090"
            elif [[ "$CURRENT_SERIAL" == *"978"* ]]; then
                USE="978"
            elif [ "$DEVICE_COUNT" -eq 0 ]; then
                USE="1090"
            fi
            
            if [ -n "$CURRENT_SERIAL" ] && [ "$CURRENT_SERIAL" != "0" ]; then
                SOAPY_STR="driver=${CURRENT_DRIVER},serial=${CURRENT_SERIAL}"
            else
                SOAPY_STR="driver=${CURRENT_DRIVER},index=${DEVICE_COUNT}"
            fi
            
            ALL_DEVICES+=("${CURRENT_DRIVER^^} #${DEVICE_COUNT}")
            DEVICE_TYPES+=("$DEVICE_TYPE")
            DEVICE_DRIVERS+=("$CURRENT_DRIVER")
            DEVICE_SERIALS+=("$CURRENT_SERIAL")
            SUGGESTED_USE+=("$USE")
            DEVICE_PATHS+=("$DEVICE_COUNT")
            DEVICE_LABELS+=("$CURRENT_LABEL")
            SOAPY_STRINGS+=("$SOAPY_STR")
            
            echo "  - ${CURRENT_DRIVER} device $DEVICE_COUNT: Serial=$CURRENT_SERIAL (suggested: $USE)" >&2
        fi
    fi
fi

###############################################################################
# 2. Fallback: RTL-SDR Native Detection (if SoapySDR didn't find anything)
###############################################################################

TOTAL_COUNT=${#ALL_DEVICES[@]}

if [ "$TOTAL_COUNT" = "0" ] && command -v rtl_test &> /dev/null; then
    echo "Falling back to RTL-SDR native detection..." >&2
    DETECTION_METHOD="rtl_test"
    
    # Capture rtl_test output
    DETECTION=$(timeout 3 rtl_test 2>&1 || true)
    RTL_COUNT=$(echo "$DETECTION" | grep -c "^[[:space:]]*[0-9]:" || echo "0")
    
    if [ "$RTL_COUNT" != "0" ]; then
        echo "Found $RTL_COUNT RTL-SDR device(s)" >&2
        
        # Parse each device line from rtl_test output
        while IFS= read -r line; do
            INDEX=$(echo "$line" | awk -F':' '{print $1}' | tr -d ' ')
            SERIAL=$(echo "$line" | grep -oP 'SN:\s*\K[^\s]+' || echo "")
            
            if [ -z "$SERIAL" ]; then
                SERIAL=$(echo "$line" | awk -F'SN:' '{print $2}' | awk '{print $1}' | tr -d ' ')
            fi
            
            if [ -z "$SERIAL" ] || [ "$SERIAL" = "00000000" ]; then
                SERIAL="N/A"
            fi
            
            USE="disabled"
            if [[ "$SERIAL" == *"1090"* ]]; then
                USE="1090"
            elif [[ "$SERIAL" == *"978"* ]]; then
                USE="978"
            elif [ "$INDEX" = "0" ]; then
                USE="1090"
            fi
            
            ALL_DEVICES+=("RTL-SDR #$INDEX")
            DEVICE_TYPES+=("rtlsdr")
            DEVICE_DRIVERS+=("rtlsdr")
            DEVICE_SERIALS+=("$SERIAL")
            SUGGESTED_USE+=("$USE")
            DEVICE_PATHS+=("$INDEX")
            DEVICE_LABELS+=("Generic RTL2832U")
            SOAPY_STRINGS+=("driver=rtlsdr,serial=$SERIAL")
            
            echo "  - RTL-SDR device $INDEX: Serial=$SERIAL (suggested: $USE)" >&2
            
        done < <(echo "$DETECTION" | grep "^[[:space:]]*[0-9]:")
    fi
fi

###############################################################################
# 3. Check for FTDI UATRadio devices (978 MHz only)
###############################################################################

FTDI_COUNT=0
if command -v lsusb &> /dev/null; then
    echo "Checking for FTDI UATRadio devices..." >&2
    
    FTDI_LINES=$(lsusb | grep -i "UATRadio" || echo "")
    
    if [ -n "$FTDI_LINES" ]; then
        while IFS= read -r line; do
            [ -z "$line" ] && continue
            
            echo "Found FTDI UATRadio device" >&2
            
            BUS=$(echo "$line" | awk '{print $2}')
            DEV=$(echo "$line" | awk '{print $4}' | tr -d ':')
            SERIAL=$(lsusb -v -s ${BUS}:${DEV} 2>/dev/null | grep "iSerial" | awk '{print $3}' || echo "")
            
            if [ -z "$SERIAL" ]; then
                SERIAL="N/A"
            fi
            
            DEV_PATH=""
            for path in /dev/serial/by-id/*; do
                if [ -e "$path" ]; then
                    if [[ "$path" == *"FTDI"* ]] || [[ "$path" == *"Stratux"* ]]; then
                        DEV_PATH="$path"
                        break
                    fi
                fi
            done
            
            if [ -z "$DEV_PATH" ]; then
                DEV_PATH="/dev/ttyUSB0"
            fi
            
            FTDI_INDEX=${#ALL_DEVICES[@]}
            
            ALL_DEVICES+=("FTDI UATRadio")
            DEVICE_TYPES+=("ftdi")
            DEVICE_DRIVERS+=("ftdi")
            DEVICE_SERIALS+=("$SERIAL")
            SUGGESTED_USE+=("978")
            DEVICE_PATHS+=("$DEV_PATH")
            DEVICE_LABELS+=("FTDI-based UAT Receiver")
            SOAPY_STRINGS+=("N/A")
            
            FTDI_COUNT=$((FTDI_COUNT + 1))
            
            echo "  - FTDI UATRadio: $SERIAL → $DEV_PATH (978 MHz only)" >&2
            
        done <<< "$FTDI_LINES"
    fi
fi

###############################################################################
# 4. Generate unified JSON output
###############################################################################

TOTAL_COUNT=${#ALL_DEVICES[@]}

if [ "$TOTAL_COUNT" = "0" ]; then
    echo '{"count": 0, "devices": [], "soapy_available": false, "detection_method": "none", "message": "No SDR devices detected"}' > "$OUTPUT"
    echo '{"count": 0, "devices": [], "soapy_available": false, "detection_method": "none", "message": "No SDR devices detected"}'
    exit 0
fi

echo "Total devices detected: $TOTAL_COUNT (method: $DETECTION_METHOD)" >&2

# Start JSON
echo "{" > "$OUTPUT"
echo "  \"count\": $TOTAL_COUNT," >> "$OUTPUT"
echo "  \"soapy_available\": $SOAPY_AVAILABLE," >> "$OUTPUT"
echo "  \"detection_method\": \"$DETECTION_METHOD\"," >> "$OUTPUT"
echo "  \"devices\": [" >> "$OUTPUT"

# Add each device to JSON
for idx in "${!ALL_DEVICES[@]}"; do
    DEVICE_NAME="${ALL_DEVICES[$idx]}"
    DEVICE_TYPE="${DEVICE_TYPES[$idx]}"
    DRIVER="${DEVICE_DRIVERS[$idx]}"
    SERIAL="${DEVICE_SERIALS[$idx]}"
    USE="${SUGGESTED_USE[$idx]}"
    PATH="${DEVICE_PATHS[$idx]}"
    LABEL="${DEVICE_LABELS[$idx]}"
    SOAPY_STR="${SOAPY_STRINGS[$idx]}"
    
    # Determine capabilities
    SUPPORTS_1090="true"
    SUPPORTS_978="true"
    if [ "$DEVICE_TYPE" = "ftdi" ]; then
        SUPPORTS_1090="false"
        SUPPORTS_978="true"
    elif [ "$DEVICE_TYPE" = "airspy" ]; then
        SUPPORTS_1090="true"
        SUPPORTS_978="false"
    fi
    
    # Build device JSON
    echo "    {" >> "$OUTPUT"
    echo "      \"index\": $idx," >> "$OUTPUT"
    echo "      \"name\": \"$DEVICE_NAME\"," >> "$OUTPUT"
    echo "      \"type\": \"$DEVICE_TYPE\"," >> "$OUTPUT"
    echo "      \"driver\": \"$DRIVER\"," >> "$OUTPUT"
    echo "      \"serial\": \"$SERIAL\"," >> "$OUTPUT"
    echo "      \"label\": \"$LABEL\"," >> "$OUTPUT"
    echo "      \"device_path\": \"$PATH\"," >> "$OUTPUT"
    echo "      \"soapy_device_string\": \"$SOAPY_STR\"," >> "$OUTPUT"
    echo "      \"suggested_use\": \"$USE\"," >> "$OUTPUT"
    echo "      \"suggested_gain\": \"autogain\"," >> "$OUTPUT"
    echo "      \"supports_1090\": $SUPPORTS_1090," >> "$OUTPUT"
    echo "      \"supports_978\": $SUPPORTS_978" >> "$OUTPUT"
    
    if [ $idx -lt $((TOTAL_COUNT - 1)) ]; then
        echo "    }," >> "$OUTPUT"
    else
        echo "    }" >> "$OUTPUT"
    fi
done

# Close JSON
echo "  ]" >> "$OUTPUT"
echo "}" >> "$OUTPUT"

# Output JSON
while IFS= read -r line; do
    echo "$line"
done < "$OUTPUT"

echo "Detection complete! (method: $DETECTION_METHOD, soapy: $SOAPY_AVAILABLE)" >&2
