#!/bin/bash
# MLAT Clock Stability Fix Script
# Fixes common causes of "clock unstable" errors

if [ "$EUID" -ne 0 ]; then 
    echo "Please run as root: sudo bash $0"
    exit 1
fi

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  TAKNET-PS MLAT Clock Stability Fix"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "This script will:"
echo "  1. Fix CPU frequency scaling (most effective)"
echo "  2. Ensure NTP is running"
echo "  3. Apply USB power management tweaks"
echo "  4. Configure boot settings for stability"
echo ""

read -p "Continue? [Y/n]: " -n 1 -r
echo ""
if [[ ! $REPLY =~ ^[Yy]$ ]] && [[ ! -z $REPLY ]]; then
    echo "Cancelled."
    exit 0
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "[1/4] Fixing CPU Frequency Scaling"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Check if we're on a Raspberry Pi
if [ -f /boot/config.txt ] || [ -f /boot/firmware/config.txt ]; then
    BOOT_CONFIG="/boot/config.txt"
    [ -f /boot/firmware/config.txt ] && BOOT_CONFIG="/boot/firmware/config.txt"
    
    echo "Found boot config: $BOOT_CONFIG"
    
    # Backup config
    cp $BOOT_CONFIG ${BOOT_CONFIG}.backup-$(date +%Y%m%d-%H%M%S)
    echo "✓ Backed up boot config"
    
    # Check current settings
    if grep -q "^force_turbo=1" $BOOT_CONFIG; then
        echo "✓ force_turbo already enabled"
    else
        echo "Adding force_turbo=1"
        echo "" >> $BOOT_CONFIG
        echo "# Fix CPU frequency for MLAT stability" >> $BOOT_CONFIG
        echo "force_turbo=1" >> $BOOT_CONFIG
        echo "✓ Enabled force_turbo (locks CPU at max frequency)"
    fi
    
    # Also set CPU governor to performance
    if [ -f /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor ]; then
        echo "performance" > /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor
        echo "✓ Set CPU governor to 'performance' (active immediately)"
    fi
    
    # Make performance governor persistent
    if ! grep -q "cpufreq.default_governor=performance" /boot/cmdline.txt 2>/dev/null; then
        if [ -f /boot/cmdline.txt ]; then
            cp /boot/cmdline.txt /boot/cmdline.txt.backup-$(date +%Y%m%d-%H%M%S)
            sed -i '1 s/$/ cpufreq.default_governor=performance/' /boot/cmdline.txt
            echo "✓ Set performance governor in boot cmdline"
        fi
    fi
else
    echo "⚠ Not a Raspberry Pi - skipping boot config changes"
    
    # Try to set performance governor anyway
    if [ -f /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor ]; then
        echo "performance" > /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor
        echo "✓ Set CPU governor to 'performance'"
    fi
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "[2/4] Checking NTP Synchronization"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Enable NTP if not already enabled
if command -v timedatectl &> /dev/null; then
    timedatectl set-ntp true
    echo "✓ Enabled NTP synchronization"
    
    sleep 2
    SYNC_STATUS=$(timedatectl show --property=NTPSynchronized --value)
    if [[ "$SYNC_STATUS" == "yes" ]]; then
        echo "✓ NTP is synchronized"
    else
        echo "⚠ NTP not yet synchronized (may take a few minutes)"
        echo "  Check with: timedatectl status"
    fi
else
    echo "⚠ timedatectl not available"
    
    # Try to install/start systemd-timesyncd
    if command -v systemctl &> /dev/null; then
        systemctl enable systemd-timesyncd 2>/dev/null
        systemctl start systemd-timesyncd 2>/dev/null
        echo "✓ Started systemd-timesyncd"
    fi
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "[3/4] USB Power Management"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Disable USB power management that can cause timing issues
if [ -d /sys/bus/usb/devices ]; then
    echo "Disabling USB autosuspend..."
    for dev in /sys/bus/usb/devices/*/power/autosuspend; do
        if [ -f "$dev" ]; then
            echo -1 > "$dev" 2>/dev/null
        fi
    done
    
    for dev in /sys/bus/usb/devices/*/power/control; do
        if [ -f "$dev" ]; then
            echo "on" > "$dev" 2>/dev/null
        fi
    done
    
    echo "✓ Disabled USB autosuspend"
fi

# Make USB settings persistent
cat > /etc/udev/rules.d/99-usb-power.rules << 'EOF'
# Disable USB autosuspend for RTL-SDR devices
ACTION=="add", SUBSYSTEM=="usb", ATTR{idVendor}=="0bda", ATTR{idProduct}=="2832", ATTR{power/autosuspend}="-1"
ACTION=="add", SUBSYSTEM=="usb", ATTR{idVendor}=="0bda", ATTR{idProduct}=="2838", ATTR{power/autosuspend}="-1"

# Disable USB autosuspend for all devices
ACTION=="add", SUBSYSTEM=="usb", TEST=="power/control", ATTR{power/control}="on"
EOF

echo "✓ Created persistent USB power rules"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "[4/4] Additional Optimizations"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Disable WiFi power management (can cause timing issues)
if command -v iwconfig &> /dev/null; then
    WIFI_IFACE=$(iwconfig 2>&1 | grep -o "^[a-z0-9]*" | head -1)
    if [ ! -z "$WIFI_IFACE" ]; then
        iwconfig $WIFI_IFACE power off 2>/dev/null
        echo "✓ Disabled WiFi power management on $WIFI_IFACE"
    fi
fi

# Increase USB buffer sizes
if [ -f /sys/module/usbcore/parameters/usbfs_memory_mb ]; then
    echo 256 > /sys/module/usbcore/parameters/usbfs_memory_mb 2>/dev/null
    echo "✓ Increased USB buffer size"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Fix Complete!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Changes applied:"
echo "  ✓ CPU frequency locked (force_turbo=1)"
echo "  ✓ Performance CPU governor enabled"
echo "  ✓ NTP synchronization enabled"
echo "  ✓ USB power management disabled"
echo "  ✓ USB autosuspend disabled"
echo ""
echo "⚠ REBOOT REQUIRED for all changes to take effect!"
echo ""
echo "After reboot:"
echo "  1. Wait 5 minutes for system to stabilize"
echo "  2. Check FlightAware stats page for MLAT status"
echo "  3. Look for 'Receiver synchronized' message"
echo "  4. MLAT should start working within 10-15 minutes"
echo ""

read -p "Reboot now? [Y/n]: " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]] || [[ -z $REPLY ]]; then
    echo "Rebooting in 5 seconds..."
    sleep 5
    reboot
else
    echo "Reboot cancelled. Please reboot manually: sudo reboot"
fi
