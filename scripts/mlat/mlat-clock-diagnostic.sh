#!/bin/bash
# MLAT Clock Stability Diagnostic Script
# Checks common causes of "clock unstable" errors

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  TAKNET-PS MLAT Clock Stability Diagnostics"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# 1. Check power supply voltage
echo "[1/8] Power Supply Voltage"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if command -v vcgencmd &> /dev/null; then
    VOLTAGE=$(vcgencmd measure_volts | cut -d= -f2 | cut -d V -f1)
    echo "Current voltage: ${VOLTAGE}V"
    
    # Check for under-voltage
    THROTTLED=$(vcgencmd get_throttled)
    echo "Throttle status: $THROTTLED"
    
    if [[ "$THROTTLED" == "throttled=0x0" ]]; then
        echo "✓ No throttling detected - power supply OK"
    else
        echo "⚠ THROTTLING DETECTED!"
        echo "  This usually means inadequate power supply"
        echo "  Recommend: Official Raspberry Pi 5V 3A power supply"
    fi
else
    echo "⚠ vcgencmd not available (not a Raspberry Pi?)"
fi

echo ""

# 2. Check CPU frequency scaling
echo "[2/8] CPU Frequency & Scaling"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if [ -f /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor ]; then
    GOVERNOR=$(cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor)
    CUR_FREQ=$(cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq)
    MIN_FREQ=$(cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_min_freq)
    MAX_FREQ=$(cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_max_freq)
    
    echo "Governor: $GOVERNOR"
    echo "Current: $((CUR_FREQ / 1000)) MHz"
    echo "Min: $((MIN_FREQ / 1000)) MHz"
    echo "Max: $((MAX_FREQ / 1000)) MHz"
    
    if [[ "$GOVERNOR" == "performance" ]] || [[ "$MIN_FREQ" == "$MAX_FREQ" ]]; then
        echo "✓ CPU frequency is fixed/stable"
    else
        echo "⚠ CPU frequency scaling is ACTIVE"
        echo "  This can cause clock instability!"
        echo "  Recommend: Fix CPU frequency (see fix script)"
    fi
else
    echo "⚠ Cannot check CPU frequency scaling"
fi

echo ""

# 3. Check NTP synchronization
echo "[3/8] NTP Time Synchronization"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if command -v timedatectl &> /dev/null; then
    SYNC_STATUS=$(timedatectl show --property=NTPSynchronized --value)
    TIME_ZONE=$(timedatectl show --property=Timezone --value)
    
    echo "NTP Synchronized: $SYNC_STATUS"
    echo "Timezone: $TIME_ZONE"
    
    if [[ "$SYNC_STATUS" == "yes" ]]; then
        echo "✓ System time is synchronized"
        
        # Show NTP details if available
        if command -v ntpq &> /dev/null; then
            echo ""
            echo "NTP servers:"
            ntpq -p 2>/dev/null || echo "  (ntpq not available)"
        fi
    else
        echo "⚠ NTP is NOT synchronized!"
        echo "  This WILL cause MLAT failures"
        echo "  Recommend: Enable NTP (see fix script)"
    fi
else
    echo "⚠ timedatectl not available"
fi

echo ""

# 4. Check USB device tree
echo "[4/8] USB Device Connection"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "RTL-SDR devices:"
lsusb | grep -i "rtl\|realtek" || echo "  No RTL-SDR found"

# Check for USB hubs
HUB_COUNT=$(lsusb | grep -i "hub" | wc -l)
if [ $HUB_COUNT -gt 0 ]; then
    echo ""
    echo "⚠ Warning: $HUB_COUNT USB hub(s) detected"
    echo "  USB hubs can cause timing issues"
    echo "  Recommend: Connect SDR directly to Pi USB port"
    lsusb | grep -i "hub"
fi

echo ""

# 5. Check CPU load
echo "[5/8] CPU Load & Temperature"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
LOAD=$(uptime | awk -F'load average:' '{print $2}')
echo "Load average:$LOAD"

if command -v vcgencmd &> /dev/null; then
    TEMP=$(vcgencmd measure_temp | cut -d= -f2)
    echo "Temperature: $TEMP"
    
    TEMP_NUM=$(echo $TEMP | cut -d. -f1 | tr -d "'C")
    if [ $TEMP_NUM -gt 80 ]; then
        echo "⚠ High temperature! Consider cooling"
    else
        echo "✓ Temperature OK"
    fi
fi

echo ""

# 6. Check piaware container logs for clock errors
echo "[6/8] PiAware MLAT Status"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━"
if command -v docker &> /dev/null; then
    if docker ps --format '{{.Names}}' | grep -q piaware; then
        echo "Last 10 MLAT-related log entries:"
        docker logs piaware 2>&1 | grep -i "mlat\|clock" | tail -10
    else
        echo "⚠ PiAware container not running"
    fi
else
    echo "⚠ Docker not available"
fi

echo ""

# 7. Check location settings
echo "[7/8] Location Configuration"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if [ -f /opt/adsb/config/.env ]; then
    echo "Current location settings:"
    grep -E "FEEDER_LAT|FEEDER_LONG|FEEDER_ALT" /opt/adsb/config/.env | head -3
    echo ""
    echo "⚠ Verify these match your actual antenna location!"
    echo "  Incorrect location causes MLAT failures"
else
    echo "⚠ Cannot find .env file"
fi

echo ""

# 8. Check for kernel messages
echo "[8/8] System Kernel Messages"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Recent USB errors:"
dmesg | grep -i "usb\|rtl" | tail -5
if [ $? -ne 0 ]; then
    echo "  (No recent USB issues)"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Diagnostic Complete"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Common causes of 'clock unstable' errors:"
echo "  1. Inadequate power supply (most common)"
echo "  2. CPU frequency scaling (second most common)"
echo "  3. NTP not synchronized"
echo "  4. SDR connected through USB hub"
echo "  5. Incorrect location settings"
echo "  6. High CPU load / temperature"
echo ""
echo "Run the fix script to address these issues automatically."
echo ""
