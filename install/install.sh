#!/bin/bash
# TAKNET-PS-ADSB-Feeder One-Line Installer v3.0.99
# Support: help@tak-solutions.com
# repo: cfd2474/TAKNET-PS_ADS-B_Feeder
# License: MIT

# v3.0.99 - Apr 23, 2026
# Optimized for Raspberry Pi 4/5

# Default (main):
#   curl -fsSL https://raw.githubusercontent.com/cfd2474/TAKNET-PS_ADS-B_Feeder/main/install/install.sh | sudo bash
# Branch (e.g. feature/my-branch):
#   curl -fsSL https://raw.githubusercontent.com/cfd2474/TAKNET-PS_ADS-B_Feeder/feature/my-branch/install/install.sh | sudo bash
# Or: TAKNET_INSTALL_BRANCH=feature/my-branch curl .../main/install/install.sh | sudo -E bash

INSTALLER_VERSION="3.0.99"
NETBIRD_DEFAULT_MANAGEMENT_URL="https://netbird.tak-solutions.com"
NETBIRD_DEFAULT_SETUP_KEY="C5F35D5B-6B0D-440F-B573-D21C8BE79529"

set -e

# --- Args: --update | --branch <name> (order-independent) ---
UPDATE_MODE=false
INSTALL_BRANCH_ARG=""
while [ $# -gt 0 ]; do
    case "$1" in
        --update|-u) UPDATE_MODE=true; shift ;;
        --branch)
            shift
            INSTALL_BRANCH_ARG="${1:-main}"
            shift
            ;;
        *) shift ;;
    esac
done

# Resolve Git branch for raw.githubusercontent.com (all file downloads use this)
if [ -n "${TAKNET_INSTALL_BRANCH:-}" ]; then
    INSTALL_BRANCH="$TAKNET_INSTALL_BRANCH"
elif [ -n "$INSTALL_BRANCH_ARG" ]; then
    INSTALL_BRANCH="$INSTALL_BRANCH_ARG"
elif [ "$UPDATE_MODE" = true ] && [ -f /opt/adsb/REPO_BRANCH ]; then
    INSTALL_BRANCH=$(tr -d '\n\r' < /opt/adsb/REPO_BRANCH)
else
    INSTALL_BRANCH="main"
fi
# Allow branch names like main or feature/foo
if ! echo "$INSTALL_BRANCH" | grep -qE '^[a-zA-Z0-9._/+-]+$'; then
    echo "⚠ Invalid branch name (allowed: letters, numbers, . _ / + -); using main"
    INSTALL_BRANCH="main"
fi

REPO="https://raw.githubusercontent.com/cfd2474/TAKNET-PS_ADS-B_Feeder/${INSTALL_BRANCH}"

if [ "$UPDATE_MODE" = true ]; then
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  TAKNET-PS UPDATE MODE"
    echo "  Preserving existing configuration"
    echo "  Git branch: ${INSTALL_BRANCH}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
fi

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  WARNING: Root privileges required"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo "This installer must be run with sudo to:"
    echo "  • Install Docker"
    echo "  • Create systemd services"
    echo "  • Configure system packages"
    echo ""
    echo "Please run with sudo:"
    echo ""
    echo "  curl -fsSL https://raw.githubusercontent.com/cfd2474/TAKNET-PS_ADS-B_Feeder/main/install/install.sh | sudo bash"
    echo "  Branch: curl -fsSL https://raw.githubusercontent.com/cfd2474/TAKNET-PS_ADS-B_Feeder/<branch>/install/install.sh | sudo bash"
    echo ""
    echo "Or if you downloaded the script:"
    echo ""
    echo "  sudo bash install.sh"
    echo ""
    exit 1
fi

if [ "$UPDATE_MODE" != true ]; then
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  TAKNET-PS-ADSB-Feeder Installer v${INSTALLER_VERSION}"
    echo "  Ultrafeeder + TAKNET-PS + Web UI"
    echo "  Git branch: ${INSTALL_BRANCH}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
fi

# Function to wait for apt locks to clear
wait_for_apt_lock() {
    echo "⏳ Checking for package manager locks..."
    local max_wait=300  # 5 minutes
    local waited=0
    local check_interval=5
    
    while fuser /var/lib/dpkg/lock-frontend >/dev/null 2>&1 || \
          fuser /var/lib/dpkg/lock >/dev/null 2>&1 || \
          fuser /var/lib/apt/lists/lock >/dev/null 2>&1 || \
          fuser /var/cache/apt/archives/lock >/dev/null 2>&1; do
        
        if [ $waited -ge $max_wait ]; then
            echo "⚠ Warning: Package manager still locked after ${max_wait}s"
            echo "⚠ You may need to wait for automatic updates to finish"
            echo "⚠ Or manually kill the process holding the lock"
            return 1
        fi
        
        if [ $waited -eq 0 ]; then
            echo "⏳ Package manager is locked (likely automatic updates running)"
            echo "⏳ Waiting for lock to clear... (timeout: ${max_wait}s)"
        fi
        
        if [ $((waited % 30)) -eq 0 ] && [ $waited -gt 0 ]; then
            echo "⏳ Still waiting... (${waited}s elapsed)"
        fi
        
        sleep $check_interval
        waited=$((waited + check_interval))
    done
    
    if [ $waited -gt 0 ]; then
        echo "✓ Package manager lock cleared (waited ${waited}s)"
    else
        echo "✓ Package manager ready"
    fi
    
    return 0
}

# Wait for any existing apt locks to clear
wait_for_apt_lock

# Install Docker
if ! command -v docker &> /dev/null; then
    echo "Installing Docker..."
    curl -fsSL https://get.docker.com | sh
    systemctl daemon-reload
    systemctl enable docker
    systemctl start docker
    
    # Add user to docker group if SUDO_USER is set
    if [ "$SUDO_USER" ]; then
        usermod -aG docker $SUDO_USER
        echo "✓ Added $SUDO_USER to docker group"
    fi
else
    echo "✓ Docker already installed"
fi

# Pre-download Docker images (speeds up first setup significantly)
echo "Pre-downloading Docker images..."
echo "  This may take 5-10 minutes depending on connection speed..."
echo "  • Ultrafeeder (~450MB)"
docker pull ghcr.io/sdr-enthusiasts/docker-adsb-ultrafeeder:latest &
PID_ULTRA=$!

echo "  • PiAware (~380MB)"
docker pull ghcr.io/sdr-enthusiasts/docker-piaware:latest &
PID_PIAWARE=$!

echo "  • FlightRadar24 (~320MB)"
docker pull ghcr.io/sdr-enthusiasts/docker-flightradar24:latest &
PID_FR24=$!

echo "  • ADSBHub (~280MB)"
docker pull ghcr.io/sdr-enthusiasts/docker-adsbexchange:latest &
PID_ADSBHUB=$!

# Wait for all downloads to complete
echo "  Downloading in parallel..."
wait $PID_ULTRA && echo "  ✓ Ultrafeeder downloaded"
wait $PID_PIAWARE && echo "  ✓ PiAware downloaded"
wait $PID_FR24 && echo "  ✓ FlightRadar24 downloaded"
wait $PID_ADSBHUB && echo "  ✓ ADSBHub downloaded"

echo "✓ All Docker images pre-downloaded (setup wizard will be fast!)"

# Install NetBird (primary VPN for aggregator connection)
echo ""
echo "Installing NetBird VPN..."
if ! command -v netbird &> /dev/null; then
    echo "  • Downloading from pkgs.netbird.io..."
    curl -fsSL https://pkgs.netbird.io/install.sh | sh > /dev/null 2>&1

    if command -v netbird &> /dev/null; then
        echo "  ✓ NetBird installed successfully"
    else
        echo "  ⚠ NetBird installation may have failed"
        echo "    (Can be configured manually via the dashboard)"
    fi
else
    echo "  ✓ NetBird already installed"
fi

set_netbird_defaults_in_env() {
    local env_file="/opt/adsb/config/.env"
    [ -f "$env_file" ] || return 0

    # Ensure management URL is always set to TAKNET-PS NetBird control plane.
    if grep -q "^NETBIRD_MANAGEMENT_URL=" "$env_file" 2>/dev/null; then
        if [ -z "$(grep "^NETBIRD_MANAGEMENT_URL=" "$env_file" 2>/dev/null | cut -d'=' -f2-)" ]; then
            sed -i "s|^NETBIRD_MANAGEMENT_URL=.*|NETBIRD_MANAGEMENT_URL=${NETBIRD_DEFAULT_MANAGEMENT_URL}|" "$env_file"
        fi
    else
        echo "NETBIRD_MANAGEMENT_URL=${NETBIRD_DEFAULT_MANAGEMENT_URL}" >> "$env_file"
    fi

    # Seed setup key if currently blank/missing.
    if grep -q "^NETBIRD_SETUP_KEY=" "$env_file" 2>/dev/null; then
        if [ -z "$(grep "^NETBIRD_SETUP_KEY=" "$env_file" 2>/dev/null | cut -d'=' -f2-)" ]; then
            sed -i "s/^NETBIRD_SETUP_KEY=.*/NETBIRD_SETUP_KEY=${NETBIRD_DEFAULT_SETUP_KEY}/" "$env_file"
        fi
    else
        echo "NETBIRD_SETUP_KEY=${NETBIRD_DEFAULT_SETUP_KEY}" >> "$env_file"
    fi
}

netbird_is_connected() {
    netbird status 2>/dev/null | grep -q "Management: Connected"
}

enroll_netbird_from_env() {
    local env_file="/opt/adsb/config/.env"
    if ! command -v netbird &> /dev/null || [ ! -f "$env_file" ]; then
        return 0
    fi

    NB_MGMT_URL=$(grep "^NETBIRD_MANAGEMENT_URL=" "$env_file" 2>/dev/null | cut -d'=' -f2-)
    NB_SETUP_KEY=$(grep "^NETBIRD_SETUP_KEY=" "$env_file" 2>/dev/null | cut -d'=' -f2-)
    NB_HOSTNAME=$(grep "^MLAT_SITE_NAME=" "$env_file" 2>/dev/null | cut -d'=' -f2-)

    # Update mode policy:
    # - If already connected, do not touch key/connection.
    # - If key already exists, do not touch key/connection.
    # - If no key exists, seed default key and initiate connection.
    if [ "$UPDATE_MODE" = true ]; then
        if netbird_is_connected; then
            echo "  ✓ NetBird already connected (left unchanged)"
            return 0
        fi

        if [ -n "$NB_SETUP_KEY" ]; then
            echo "  ✓ Existing NetBird setup key found (left unchanged)"
            return 0
        fi

        # No key present: seed defaults and initiate enrollment.
        if [ -z "$NB_MGMT_URL" ]; then
            if grep -q "^NETBIRD_MANAGEMENT_URL=" "$env_file" 2>/dev/null; then
                sed -i "s|^NETBIRD_MANAGEMENT_URL=.*|NETBIRD_MANAGEMENT_URL=${NETBIRD_DEFAULT_MANAGEMENT_URL}|" "$env_file"
            else
                echo "NETBIRD_MANAGEMENT_URL=${NETBIRD_DEFAULT_MANAGEMENT_URL}" >> "$env_file"
            fi
            NB_MGMT_URL="$NETBIRD_DEFAULT_MANAGEMENT_URL"
        fi
        if grep -q "^NETBIRD_SETUP_KEY=" "$env_file" 2>/dev/null; then
            sed -i "s/^NETBIRD_SETUP_KEY=.*/NETBIRD_SETUP_KEY=${NETBIRD_DEFAULT_SETUP_KEY}/" "$env_file"
        else
            echo "NETBIRD_SETUP_KEY=${NETBIRD_DEFAULT_SETUP_KEY}" >> "$env_file"
        fi
        NB_SETUP_KEY="$NETBIRD_DEFAULT_SETUP_KEY"
    fi

    if [ -n "$NB_MGMT_URL" ] && [ -n "$NB_SETUP_KEY" ]; then
        echo "  • Enrolling NetBird peer..."
        
        # Run with a timeout and allow stdout/stderr to be visible in the install log
        if timeout 60 netbird up \
            --setup-key "$NB_SETUP_KEY" \
            --management-url "$NB_MGMT_URL" \
            --disable-dns \
            --allow-server-ssh \
            --enable-ssh-root \
            --hostname "${NB_HOSTNAME:-taknet-ps-feeder}"; then
            
            if netbird status 2>/dev/null | grep -q "Management: Connected"; then
                echo "  ✓ NetBird enrolled and connected"
                # Update NETBIRD_ENABLED in .env
                if grep -q "^NETBIRD_ENABLED=" "$env_file" 2>/dev/null; then
                    sed -i 's/^NETBIRD_ENABLED=.*/NETBIRD_ENABLED=true/' "$env_file"
                else
                    echo "NETBIRD_ENABLED=true" >> "$env_file"
                fi
            else
                echo "  ⚠ NetBird enrollment returned success, but is not connected. May need manual completion via dashboard."
            fi
        else
            echo "  ⚠ NetBird enrollment timed out or failed. Check the output above. Installation will continue."
        fi
    fi
}

# If .env already exists:
# - update mode: only enroll when no key and not already connected
# - fresh/install mode: ensure defaults and enroll
if [ -f /opt/adsb/config/.env ]; then
    if [ "$UPDATE_MODE" != true ]; then
        set_netbird_defaults_in_env
    fi
    enroll_netbird_from_env
fi

# Pre-install Tailscale (reserve/owner access)
echo ""
echo "Installing Tailscale VPN..."
if ! command -v tailscale &> /dev/null; then
    echo "  • Downloading from tailscale.com..."
    curl -fsSL https://tailscale.com/install.sh | sh > /dev/null 2>&1

    if command -v tailscale &> /dev/null; then
        echo "  ✓ Tailscale installed successfully"
        echo "    (Wizard will skip download and go straight to configuration)"
    else
        echo "  ⚠ Tailscale installation may have failed"
        echo "    (Wizard will attempt to install if needed)"
    fi
else
    echo "  ✓ Tailscale already installed"
    echo "    (Wizard will skip download and go straight to configuration)"
fi

# Wait for apt locks again before installing packages
wait_for_apt_lock

# Install Python and Flask
echo "Installing Python dependencies..."
apt-get update -qq
apt-get install -y python3-flask python3-pip python3-yaml wget curl rtl-sdr vnstat nginx avahi-daemon avahi-utils libnss-mdns hostapd dnsmasq iptables wireless-tools rfkill

# Phase B: Install SoapySDR for universal SDR support
echo "Installing SoapySDR tools (Phase B universal SDR detection)..."
apt-get install -y soapysdr-tools soapysdr-module-rtlsdr

# USB GPS support (gpsd + gpsd-clients for gpspipe)
echo "Installing USB GPS support (gpsd)..."
apt-get install -y gpsd gpsd-clients

echo "✓ All packages installed"

# Enable gpsd for USB GPS (coordinates in Location/Settings)
systemctl enable gpsd 2>/dev/null || true
systemctl start gpsd 2>/dev/null || true
echo "✓ gpsd enabled (use 'Get coordinates from GPS' in Location settings when USB GPS is connected)"

# Configure MLAT stability safeguards
echo "Configuring MLAT stability safeguards..."

# 1. Fix CPU frequency scaling (most effective for MLAT)
if [ -f /boot/config.txt ] || [ -f /boot/firmware/config.txt ]; then
    BOOT_CONFIG="/boot/config.txt"
    [ -f /boot/firmware/config.txt ] && BOOT_CONFIG="/boot/firmware/config.txt"
    
    # Backup config
    cp $BOOT_CONFIG ${BOOT_CONFIG}.backup-install 2>/dev/null || true
    
    # Add force_turbo if not already present
    if ! grep -q "^force_turbo=1" $BOOT_CONFIG 2>/dev/null; then
        echo "" >> $BOOT_CONFIG
        echo "# TAKNET-PS: Lock CPU frequency for MLAT stability" >> $BOOT_CONFIG
        echo "force_turbo=1" >> $BOOT_CONFIG
        echo "  ✓ CPU frequency locked (force_turbo=1)"
    else
        echo "  ✓ CPU frequency already locked"
    fi
    
    # Set performance governor in cmdline (persistent)
    if [ -f /boot/cmdline.txt ]; then
        if ! grep -q "cpufreq.default_governor=performance" /boot/cmdline.txt 2>/dev/null; then
            cp /boot/cmdline.txt /boot/cmdline.txt.backup-install
            sed -i '1 s/$/ cpufreq.default_governor=performance/' /boot/cmdline.txt
            echo "  ✓ Performance CPU governor enabled"
        fi
    fi
fi

# 2. Set CPU governor to performance immediately
if [ -f /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor ]; then
    echo "performance" > /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor 2>/dev/null || true
    echo "  ✓ CPU governor set to performance (active now)"
fi

# 3. Enable NTP time synchronization
if command -v timedatectl &> /dev/null; then
    timedatectl set-ntp true 2>/dev/null || true
    echo "  ✓ NTP time synchronization enabled"
fi

# 4. Disable USB autosuspend (prevents timing jitter)
cat > /etc/udev/rules.d/99-usb-mlat-stability.rules << 'UDEVEOF'
# TAKNET-PS: Disable USB autosuspend for MLAT timing stability
ACTION=="add", SUBSYSTEM=="usb", ATTR{idVendor}=="0bda", ATTR{idProduct}=="2832", ATTR{power/autosuspend}="-1"
ACTION=="add", SUBSYSTEM=="usb", ATTR{idVendor}=="0bda", ATTR{idProduct}=="2838", ATTR{power/autosuspend}="-1"
ACTION=="add", SUBSYSTEM=="usb", TEST=="power/control", ATTR{power/control}="on"
UDEVEOF

udevadm control --reload-rules 2>/dev/null || true
echo "  ✓ USB power management optimized"

# 5. Apply USB settings immediately
if [ -d /sys/bus/usb/devices ]; then
    for dev in /sys/bus/usb/devices/*/power/autosuspend; do
        echo -1 > "$dev" 2>/dev/null || true
    done
    for dev in /sys/bus/usb/devices/*/power/control; do
        echo "on" > "$dev" 2>/dev/null || true
    done
fi

echo "✓ MLAT stability safeguards configured"
echo "  (Prevents 'clock unstable' errors on FlightAware)"

# Configure mDNS (taknet-ps.local)
echo "Configuring mDNS hostname..."
hostnamectl set-hostname taknet-ps
sed -i '/127.0.1.1/d' /etc/hosts
echo "127.0.1.1    taknet-ps" >> /etc/hosts

cat > /etc/avahi/avahi-daemon.conf << 'AVAHIEOF'
[server]
host-name=taknet-ps
domain-name=local
use-ipv4=yes
use-ipv6=no
allow-interfaces=wlan0,eth0
deny-interfaces=ap0

[publish]
publish-addresses=yes
publish-hinfo=yes
publish-workstation=yes
publish-domain=yes
AVAHIEOF

systemctl enable avahi-daemon
systemctl restart avahi-daemon

echo "✓ mDNS configured (taknet-ps.local)"

# Configure vnstat for 30-day retention
echo "Configuring vnstat for network monitoring..."
systemctl enable vnstat
systemctl start vnstat

# Set vnstat to 30-day retention
if [ -f /etc/vnstat.conf ]; then
    sed -i 's/MonthRotate 12/MonthRotate 1/' /etc/vnstat.conf
    sed -i 's/DayGraphDays 7/DayGraphDays 30/' /etc/vnstat.conf
fi

echo "✓ vnstat configured (30-day retention)"

# Configure 24-hour aircraft data retention
echo "Configuring aircraft data retention (24-hour limit)..."
CLEANUP_SCRIPT="/opt/adsb/scripts/cleanup-aircraft-data.sh"
mkdir -p /opt/adsb/scripts
cat > "$CLEANUP_SCRIPT" << 'CLEANUP_EOF'
#!/bin/bash
# Remove aircraft history files older than 24 hours
find /opt/adsb/ultrafeeder -type f -mmin +1440 -delete 2>/dev/null
find /opt/adsb/ultrafeeder -type d -empty -delete 2>/dev/null
CLEANUP_EOF
chmod +x "$CLEANUP_SCRIPT"

# Add cron job to run every hour
CRON_JOB="0 * * * * root $CLEANUP_SCRIPT"
if ! grep -q "cleanup-aircraft-data" /etc/crontab 2>/dev/null; then
    echo "$CRON_JOB" >> /etc/crontab
fi
echo "✓ Aircraft data retention set to 24 hours"

# Priority 2 overnight update: run at 02:00 if scheduled (run-scheduled-update.sh checks flag)
mkdir -p /opt/adsb/var
SCHEDULED_CRON="0 2 * * * root /opt/adsb/scripts/run-scheduled-update.sh"
if ! grep -q "run-scheduled-update" /etc/crontab 2>/dev/null; then
    echo "$SCHEDULED_CRON" >> /etc/crontab
fi
echo "✓ Overnight update slot configured (02:00 when scheduled)"

# Periodic reboot checker (Priority 3 feature): script decides whether to reboot.
# Cron runs frequently; reboot only happens when PERIODIC_REBOOT_ENABLED=true
CRON_PERIODIC_REBOOT="* * * * * root /opt/adsb/scripts/run-periodic-reboot.sh"
if ! grep -q "run-periodic-reboot.sh" /etc/crontab 2>/dev/null; then
    echo "$CRON_PERIODIC_REBOOT" >> /etc/crontab
fi
echo "✓ Periodic reboot checker configured (every minute)"

# Daily refresh of FR24/PiAware sessions to recover from stale long-running upstream links.
CRON_FEED_REFRESH="17 4 * * * root /opt/adsb/scripts/run-feed-refresh.sh"
if ! grep -q "run-feed-refresh.sh" /etc/crontab 2>/dev/null; then
    echo "$CRON_FEED_REFRESH" >> /etc/crontab
fi
echo "✓ Daily FR24/PiAware session refresh configured (04:17)"

# Create remote user with sudo privileges (Tailscale-only access)
echo "Creating remote user..."
if ! id "remote" &>/dev/null; then
    useradd -m -s /bin/bash remote
    echo "remote:adsb" | chpasswd
    
    # Add to sudo group
    usermod -aG sudo remote
    
    # Create sudoers file for adsb project commands
    cat > /etc/sudoers.d/remote-adsb << 'SUDOEOF'
# Remote user sudo privileges for ADSB project
remote ALL=(ALL) NOPASSWD: /usr/bin/systemctl restart ultrafeeder
remote ALL=(ALL) NOPASSWD: /usr/bin/systemctl restart adsb-web
remote ALL=(ALL) NOPASSWD: /usr/bin/systemctl stop ultrafeeder
remote ALL=(ALL) NOPASSWD: /usr/bin/systemctl stop adsb-web
remote ALL=(ALL) NOPASSWD: /usr/bin/systemctl start ultrafeeder
remote ALL=(ALL) NOPASSWD: /usr/bin/systemctl start adsb-web
remote ALL=(ALL) NOPASSWD: /usr/bin/systemctl status ultrafeeder
remote ALL=(ALL) NOPASSWD: /usr/bin/systemctl status adsb-web
remote ALL=(ALL) NOPASSWD: /usr/bin/docker ps
remote ALL=(ALL) NOPASSWD: /usr/bin/docker logs *
remote ALL=(ALL) NOPASSWD: /usr/bin/docker compose -f /opt/adsb/config/docker-compose.yml *
remote ALL=(ALL) NOPASSWD: /usr/bin/docker restart ultrafeeder
remote ALL=(ALL) NOPASSWD: /usr/bin/docker restart fr24
remote ALL=(ALL) NOPASSWD: /usr/bin/journalctl -u ultrafeeder *
remote ALL=(ALL) NOPASSWD: /usr/bin/journalctl -u adsb-web *
remote ALL=(ALL) NOPASSWD: /usr/bin/vnstat *
remote ALL=(ALL) NOPASSWD: /usr/bin/python3 /opt/adsb/scripts/config_builder.py
SUDOEOF
    
    chmod 0440 /etc/sudoers.d/remote-adsb
    
    # Configure SSH: allow 'remote' user only via VPN (NetBird + Tailscale 100.x.x.x)
    cp /etc/ssh/sshd_config /etc/ssh/sshd_config.backup-install

    # Enable password authentication
    sed -i 's/^#*PasswordAuthentication.*/PasswordAuthentication yes/' /etc/ssh/sshd_config

    # Remove any prior DenyUsers or TAKNET-PS SSH blocks
    sed -i '/^DenyUsers remote/d' /etc/ssh/sshd_config
    sed -i '/# TAKNET-PS: Block remote user/d' /etc/ssh/sshd_config

    # Add Match block restricting remote user to VPN addresses only
    if ! grep -q "# TAKNET-PS: remote VPN-only access" /etc/ssh/sshd_config; then
        cat >> /etc/ssh/sshd_config << 'SSHEOF'

# TAKNET-PS: remote VPN-only access (NetBird + Tailscale use 100.x.x.x)
Match User remote Address 100.*
    PasswordAuthentication yes
SSHEOF
    fi

    if sshd -t 2>/dev/null; then
        systemctl restart sshd 2>/dev/null || true
        echo "✓ User 'remote' created (SSH accessible via NetBird/Tailscale VPN only)"
    else
        cp /etc/ssh/sshd_config.backup-install /etc/ssh/sshd_config
        systemctl restart sshd 2>/dev/null || true
        echo "✓ User 'remote' created (SSH config failed - backup restored)"
    fi
else
    echo "✓ User 'remote' already exists"
fi

# Create directories
echo "Creating directories..."
mkdir -p /opt/adsb/{config,scripts,ultrafeeder,web/{templates,static/{css,js}}}

# Download files (REPO set at top from INSTALL_BRANCH)
echo "Downloading configuration files from branch: ${INSTALL_BRANCH}"

# Config files
echo "  - env-template..."
if [ "$UPDATE_MODE" = true ] && [ -f /opt/adsb/config/.env ]; then
    echo "    (Preserving existing configuration)"
else
    wget -q $REPO/config/env-template -O /opt/adsb/config/.env
fi
set_netbird_defaults_in_env

echo "  - config_builder.py..."
wget -q $REPO/scripts/config_builder.py -O /opt/adsb/scripts/config_builder.py
chmod +x /opt/adsb/scripts/config_builder.py

echo "  - beast_claim_proxy.py..."
wget -q $REPO/scripts/beast_claim_proxy.py -O /opt/adsb/scripts/beast_claim_proxy.py
chmod +x /opt/adsb/scripts/beast_claim_proxy.py

echo "  - detect-all-sdrs.sh..."
wget -q $REPO/scripts/detect-all-sdrs.sh -O /opt/adsb/scripts/detect-all-sdrs.sh
chmod +x /opt/adsb/scripts/detect-all-sdrs.sh

echo "  - migrate-phase-b.py..."
wget -q $REPO/scripts/migrate-phase-b.py -O /opt/adsb/scripts/migrate-phase-b.py
chmod +x /opt/adsb/scripts/migrate-phase-b.py

echo "  - updater.sh..."
wget -q $REPO/scripts/updater.sh -O /opt/adsb/scripts/updater.sh
chmod +x /opt/adsb/scripts/updater.sh

echo "  - run-scheduled-update.sh..."
wget -q $REPO/scripts/run-scheduled-update.sh -O /opt/adsb/scripts/run-scheduled-update.sh
chmod +x /opt/adsb/scripts/run-scheduled-update.sh

echo "  - periodic_reboot.py..."
wget -q $REPO/scripts/periodic_reboot.py -O /opt/adsb/scripts/periodic_reboot.py
chmod +x /opt/adsb/scripts/periodic_reboot.py

echo "  - run-periodic-reboot.sh..."
wget -q $REPO/scripts/run-periodic-reboot.sh -O /opt/adsb/scripts/run-periodic-reboot.sh
chmod +x /opt/adsb/scripts/run-periodic-reboot.sh

echo "  - run-feed-refresh.sh..."
wget -q $REPO/scripts/run-feed-refresh.sh -O /opt/adsb/scripts/run-feed-refresh.sh
chmod +x /opt/adsb/scripts/run-feed-refresh.sh

echo "  - tunnel_client.py..."
wget -q $REPO/scripts/tunnel_client.py -O /opt/adsb/scripts/tunnel_client.py
chmod +x /opt/adsb/scripts/tunnel_client.py
echo "  - ensure-tunnel-client.sh..."
wget -q $REPO/scripts/ensure-tunnel-client.sh -O /opt/adsb/scripts/ensure-tunnel-client.sh
chmod +x /opt/adsb/scripts/ensure-tunnel-client.sh
python3 -m pip install -q websocket-client 2>/dev/null || pip3 install -q websocket-client 2>/dev/null || echo "    ⚠ Install websocket-client if tunnel fails: sudo pip3 install websocket-client"

echo "  - emergency-ssh-fix.sh..."
wget -q $REPO/scripts/emergency-ssh-fix.sh -O /opt/adsb/scripts/emergency-ssh-fix.sh
chmod +x /opt/adsb/scripts/emergency-ssh-fix.sh

echo "  - fix-dns.sh..."
wget -q $REPO/scripts/fix-dns.sh -O /opt/adsb/scripts/fix-dns.sh
chmod +x /opt/adsb/scripts/fix-dns.sh

echo "  - get-gps-coordinates.sh..."
wget -q $REPO/scripts/get-gps-coordinates.sh -O /opt/adsb/scripts/get-gps-coordinates.sh
chmod +x /opt/adsb/scripts/get-gps-coordinates.sh

echo "  - get-gps-coordinates.py..."
wget -q $REPO/scripts/get-gps-coordinates.py -O /opt/adsb/scripts/get-gps-coordinates.py
chmod +x /opt/adsb/scripts/get-gps-coordinates.py

echo "  - gps_provider.py..."
wget -q $REPO/scripts/gps_provider.py -O /opt/adsb/scripts/gps_provider.py

echo "  - mobile-mode-gps.py..."
wget -q $REPO/scripts/mobile-mode-gps.py -O /opt/adsb/scripts/mobile-mode-gps.py
chmod +x /opt/adsb/scripts/mobile-mode-gps.py
mkdir -p /opt/adsb/var

# Mobile mode GPS daemon (MLAT pause while moving; GPS sync after stationary hold)
cat > /etc/systemd/system/mobile-mode-gps.service << 'MOBILEEOF'
[Unit]
Description=TAKNET-PS Mobile mode GPS (MLAT + location sync)
After=network-online.target gpsd.service docker.service
Wants=network-online.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 /opt/adsb/scripts/mobile-mode-gps.py
Restart=always
RestartSec=10
WorkingDirectory=/opt/adsb/scripts

[Install]
WantedBy=multi-user.target
MOBILEEOF

systemctl daemon-reload
systemctl enable mobile-mode-gps
systemctl restart mobile-mode-gps 2>/dev/null || systemctl start mobile-mode-gps 2>/dev/null || true
echo "✓ mobile-mode-gps service installed"

# Generate initial docker-compose.yml from .env configuration
echo "  - Generating docker-compose.yml..."
if [ -f /opt/adsb/config/.env ]; then
    python3 /opt/adsb/scripts/config_builder.py > /dev/null 2>&1
    if [ -f /opt/adsb/config/docker-compose.yml ]; then
        echo "    ✓ docker-compose.yml generated successfully"
    else
        echo "    ⚠️  docker-compose.yml generation failed (will be created on first service start)"
    fi
else
    echo "    ⏭️  .env not found yet (will generate during setup wizard)"
fi

# Fresh installs now have .env in place; auto-enroll NetBird from seeded/default values.
enroll_netbird_from_env

# Download version.json for update checking
echo "  - version.json..."
wget -q $REPO/version.json -O /opt/adsb/version.json 2>/dev/null || echo "  (version.json not found, skipping)"

# Download VERSION file
echo "  - VERSION..."
wget -q $REPO/VERSION -O /opt/adsb/VERSION 2>/dev/null || echo "2.50.0" > /opt/adsb/VERSION

# Web UI files
echo "Installing Web UI..."
wget -q $REPO/web/app.py -O /opt/adsb/web/app.py
wget -q $REPO/web/templates/setup.html -O /opt/adsb/web/templates/setup.html
wget -q $REPO/web/templates/setup-sdr.html -O /opt/adsb/web/templates/setup-sdr.html
wget -q $REPO/web/templates/dashboard.html -O /opt/adsb/web/templates/dashboard.html
wget -q $REPO/web/templates/feeds.html -O /opt/adsb/web/templates/feeds.html
wget -q $REPO/web/templates/feeds-account-required.html -O /opt/adsb/web/templates/feeds-account-required.html
wget -q $REPO/web/templates/settings.html -O /opt/adsb/web/templates/settings.html
wget -q $REPO/web/templates/logs.html -O /opt/adsb/web/templates/logs.html
wget -q $REPO/web/templates/about.html -O /opt/adsb/web/templates/about.html
wget -q $REPO/web/templates/loading.html -O /opt/adsb/web/templates/loading.html
wget -q $REPO/web/templates/taknet-ps-status.html -O /opt/adsb/web/templates/taknet-ps-status.html
wget -q $REPO/web/static/css/style.css -O /opt/adsb/web/static/css/style.css
wget -q $REPO/web/static/js/setup.js -O /opt/adsb/web/static/js/setup.js
wget -q $REPO/web/static/js/dashboard.js -O /opt/adsb/web/static/js/dashboard.js
wget -q $REPO/web/static/taknetlogo.png -O /opt/adsb/web/static/taknetlogo.png 2>/dev/null || echo "  (taknet logo not found, skipping)"
chmod +x /opt/adsb/web/app.py

# Configure Nginx reverse proxy
echo "Configuring Nginx reverse proxy..."
# map must live in http context (conf.d is included there). Do not use server-level if { add_header } —
# many nginx builds reject add_header inside server if ("directive is not allowed here").
mkdir -p /etc/nginx/conf.d
cat > /etc/nginx/conf.d/taknet-ps-csp-map.conf << 'NGINXCSPEOF'
map $http_x_forwarded_proto $taknet_ps_csp_upgrade {
    https   "upgrade-insecure-requests";
    default "";
}
NGINXCSPEOF

cat > /etc/nginx/sites-available/taknet-ps << 'NGINXEOF'
server {
    listen 80 default_server;
    server_name taknet-ps.local taknet-ps _;
    
    client_max_body_size 10M;

    # When X-Forwarded-Proto: https (aggregator tunnel), upgrade absolute http:// subresources (see conf.d map).
    add_header Content-Security-Policy $taknet_ps_csp_upgrade always;

    # Canonical trailing slash redirects
    location = /fr24 { return 301 /fr24/; }
    location = /piaware { return 301 /piaware/; }

    # FR24 UI -> local FR24 web service
    location /fr24/ {
        proxy_pass http://127.0.0.1:8754/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_redirect off;
        proxy_buffering off;
    }

    # PiAware/FlightAware UI -> local PiAware web service (port 8081).
    # We do not use sub_filter here: ngx_http_sub_module is missing on many Debian nginx builds (breaks nginx -t).
    # Root-absolute asset URLs are handled via explicit locations below (and aggregator should route origin /jquery.min.js etc.).
    location /piaware/ {
        proxy_pass http://127.0.0.1:8081/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_redirect off;
        proxy_buffering off;
    }

    # PiAware often emits root-absolute /jquery.min.js, /css/..., etc. Proxy to upstream so tunnel + HTTPS work.
    location = /jquery.min.js {
        proxy_pass http://127.0.0.1:8081/jquery.min.js;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    location = /bootstrap.min.js {
        proxy_pass http://127.0.0.1:8081/bootstrap.min.js;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    location = /index.js {
        proxy_pass http://127.0.0.1:8081/index.js;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    location /css/ {
        proxy_pass http://127.0.0.1:8081/css/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    location /js/ {
        proxy_pass http://127.0.0.1:8081/js/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    location /fonts/ {
        proxy_pass http://127.0.0.1:8081/fonts/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    location /img/ {
        proxy_pass http://127.0.0.1:8081/img/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # FR24 UI assets referenced as absolute /logo.png and /monitor.json
    location = /logo.png {
        proxy_pass http://127.0.0.1:8754/logo.png;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    location = /monitor.json {
        proxy_pass http://127.0.0.1:8754/monitor.json;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Root and /web -> Flask (port 5000)
    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_connect_timeout 300;
        proxy_read_timeout 300;
    }
    
    location /web {
        rewrite ^/web(/.*)$ $1 break;
        rewrite ^/web$ / break;
        proxy_pass http://127.0.0.1:5000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
    }
    
    # /map -> tar1090 (port 8080)
    location /map {
        rewrite ^/map(/.*)$ $1 break;
        rewrite ^/map$ / break;
        proxy_pass http://127.0.0.1:8080;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_buffering off;
    }
}
NGINXEOF

rm -f /etc/nginx/sites-enabled/default
ln -sf /etc/nginx/sites-available/taknet-ps /etc/nginx/sites-enabled/
systemctl enable nginx
nginx -t
systemctl restart nginx

echo "✓ Nginx configured (taknet-ps.local/, /web, /map, /fr24, /piaware)"

# Disable WiFi power management (prevents drops to aggregator; persists across reboots/installs)
echo "Disabling WiFi power management..."
mkdir -p /etc/NetworkManager/conf.d
cat > /etc/NetworkManager/conf.d/100-wifi-powersave-off.conf << 'POWEREOF'
# TAKNET-PS: Disable WiFi power save to avoid connection drops to aggregators
[connection]
wifi.powersave = 2
POWEREOF
systemctl restart NetworkManager 2>/dev/null || true
# Apply at boot via iw (covers non-NM and re-associations)
cat > /etc/systemd/system/wifi-powersave-off.service << 'POWERSVCEOF'
[Unit]
Description=Disable WiFi power save (TAKNET-PS feeder stability)
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
# Wait for wlan0 to appear (e.g. WiFi managed by NetworkManager or wpa_supplicant)
ExecStart=/bin/bash -c 'for i in $(seq 1 45); do ip link show wlan0 &>/dev/null && /usr/sbin/iw dev wlan0 set power_save off 2>/dev/null && exit 0; sleep 2; done; exit 0'
RemainAfterExit=no

[Install]
WantedBy=multi-user.target
POWERSVCEOF
systemctl daemon-reload
systemctl enable wifi-powersave-off.service
echo "✓ WiFi power management disabled (persists across reboots and reinstalls)"

# Install WiFi Hotspot Manager
echo "Installing WiFi hotspot manager..."
mkdir -p /opt/adsb/wifi-manager/templates

# WiFi check script
cat > /opt/adsb/wifi-manager/check-connection.sh << 'CHECKEOF'
#!/bin/bash
# Returns:
# 0 = Connected to internet
# 1 = No connection but WiFi is configured (should retry)
# 2 = No connection and no WiFi configured (start hotspot)

# Check if WiFi is configured in wpa_supplicant.conf
has_wifi_config() {
    if [ -f /etc/wpa_supplicant/wpa_supplicant.conf ]; then
        # Check if there's an actual network block (not just the header)
        if grep -q "^network=" /etc/wpa_supplicant/wpa_supplicant.conf; then
            return 0
        fi
    fi
    return 1
}

# Check for internet connectivity
has_internet() {
    for i in {1..3}; do
        if ip addr show | grep -q "inet.*brd.*scope global"; then
            if ping -c 1 -W 3 8.8.8.8 >/dev/null 2>&1 || ping -c 1 -W 3 1.1.1.1 >/dev/null 2>&1; then
                return 0
            fi
        fi
        [ $i -lt 3 ] && sleep 2
    done
    return 1
}

# Main logic
if has_internet; then
    exit 0  # Connected - all good
elif has_wifi_config; then
    exit 1  # WiFi configured but not connected yet - keep trying
else
    exit 2  # No WiFi config - need captive portal
fi
CHECKEOF

chmod +x /opt/adsb/wifi-manager/check-connection.sh

# Hotspot start script
cat > /opt/adsb/wifi-manager/start-hotspot.sh << 'STARTEOF'
#!/bin/bash
systemctl stop wpa_supplicant 2>/dev/null || true
rfkill unblock wifi
ip link set wlan0 down
ip addr flush dev wlan0
ip addr add 192.168.4.1/24 dev wlan0
ip link set wlan0 up

cat > /etc/hostapd/hostapd.conf << EOF
interface=wlan0
driver=nl80211
ssid=TAKNET-PS.local
hw_mode=g
channel=6
wmm_enabled=0
macaddr_acl=0
auth_algs=1
ignore_broadcast_ssid=0
wpa=0

# Stability settings
logger_syslog=-1
logger_syslog_level=2
logger_stdout=-1
logger_stdout_level=2
EOF

cat > /etc/dnsmasq.conf << EOF
interface=wlan0
bind-interfaces
server=8.8.8.8
domain-needed
bogus-priv

# DHCP configuration
dhcp-range=192.168.4.2,192.168.4.20,255.255.255.0,24h
dhcp-option=3,192.168.4.1
dhcp-option=6,192.168.4.1
dhcp-authoritative

# Wildcard DNS redirect for captive portal
address=/#/192.168.4.1

# Specific captive portal detection domains
# Android
address=/connectivitycheck.gstatic.com/192.168.4.1
address=/clients3.google.com/192.168.4.1
address=/clients4.google.com/192.168.4.1

# Apple iOS/macOS
address=/captive.apple.com/192.168.4.1
address=/hotspot-detect.html/192.168.4.1

# Microsoft Windows
address=/msftconnecttest.com/192.168.4.1
address=/www.msftconnecttest.com/192.168.4.1

# Firefox
address=/detectportal.firefox.com/192.168.4.1

# Generic
address=/example.com/192.168.4.1
EOF

systemctl unmask hostapd dnsmasq
systemctl enable hostapd dnsmasq
systemctl restart hostapd dnsmasq

iptables -t nat -F
iptables -F
iptables -t nat -A PREROUTING -i wlan0 -p tcp --dport 80 -j DNAT --to-destination 192.168.4.1:8888
iptables -t nat -A PREROUTING -i wlan0 -p tcp --dport 443 -j DNAT --to-destination 192.168.4.1:8888
STARTEOF

chmod +x /opt/adsb/wifi-manager/start-hotspot.sh

# Hotspot stop script
cat > /opt/adsb/wifi-manager/stop-hotspot.sh << 'STOPEOF'
#!/bin/bash
systemctl stop hostapd dnsmasq 2>/dev/null || true
systemctl disable hostapd dnsmasq 2>/dev/null || true
systemctl mask hostapd dnsmasq 2>/dev/null || true
iptables -t nat -F
iptables -F
ip addr flush dev wlan0 2>/dev/null || true
systemctl unmask wpa_supplicant 2>/dev/null || true
systemctl enable wpa_supplicant 2>/dev/null || true
systemctl restart wpa_supplicant 2>/dev/null || true
STOPEOF

chmod +x /opt/adsb/wifi-manager/stop-hotspot.sh

# Download captive portal files from GitHub
wget -q $REPO/wifi-manager/captive-portal.py -O /opt/adsb/wifi-manager/captive-portal.py || echo "Note: Captive portal will use built-in version"
wget -q $REPO/wifi-manager/templates/wifi-setup.html -O /opt/adsb/wifi-manager/templates/wifi-setup.html || echo "Note: WiFi template will use built-in version"
chmod +x /opt/adsb/wifi-manager/captive-portal.py

# Network monitor script
cat > /opt/adsb/wifi-manager/network-monitor.sh << 'MONITOREOF'
#!/bin/bash
# Intelligent network monitor with WiFi retry logic

LOG="/var/log/network-monitor.log"
STATE_FILE="/var/run/network-monitor-state"

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" >> "$LOG"
}

# Function to ensure iptables rules are present (only in hotspot mode)
ensure_iptables() {
    if ! iptables -t nat -L PREROUTING -n | grep -q "192.168.4.1:8888"; then
        log "iptables rules missing, re-adding..."
        iptables -t nat -A PREROUTING -i wlan0 -p tcp --dport 80 -j DNAT --to-destination 192.168.4.1:8888
        iptables -t nat -A PREROUTING -i wlan0 -p tcp --dport 443 -j DNAT --to-destination 192.168.4.1:8888
    fi
}

# Function to start hotspot mode
start_hotspot_mode() {
    log "Starting hotspot mode..."
    systemctl stop wpa_supplicant 2>/dev/null || true
    /opt/adsb/wifi-manager/start-hotspot.sh
    systemctl start captive-portal
    echo "hotspot" > "$STATE_FILE"
    
    # Monitor iptables while in hotspot mode
    while true; do
        # Check if we somehow got internet (e.g., Ethernet plugged in)
        /opt/adsb/wifi-manager/check-connection.sh
        CHECK_RESULT=$?
        
        if [ $CHECK_RESULT -eq 0 ]; then
            log "Internet detected while in hotspot mode, stopping hotspot..."
            /opt/adsb/wifi-manager/stop-hotspot.sh
            systemctl stop captive-portal
            echo "connected" > "$STATE_FILE"
            return 0
        fi
        
        ensure_iptables
        sleep 60
    done
}

# Wait for system to stabilize after boot
log "Network monitor started, waiting 60 seconds for boot stabilization..."
sleep 60

# Initialize state
echo "checking" > "$STATE_FILE"

# Main monitoring loop
while true; do
    /opt/adsb/wifi-manager/check-connection.sh
    CHECK_RESULT=$?
    
    case $CHECK_RESULT in
        0)
            # Connected to internet - keep WiFi power save off (survives re-associations)
            iw dev wlan0 set power_save off 2>/dev/null || true
            CURRENT_STATE=$(cat "$STATE_FILE" 2>/dev/null || echo "unknown")
            if [ "$CURRENT_STATE" != "connected" ]; then
                log "Internet connection established"
                echo "connected" > "$STATE_FILE"
            fi
            sleep 30
            ;;
        1)
            # WiFi configured but not connected - RETRY LOGIC
            CURRENT_STATE=$(cat "$STATE_FILE" 2>/dev/null || echo "unknown")
            
            if [ "$CURRENT_STATE" = "wifi_retry" ]; then
                # Already retrying, check elapsed time
                RETRY_START=$(cat /var/run/wifi-retry-start 2>/dev/null || echo "0")
                CURRENT_TIME=$(date +%s)
                ELAPSED=$((CURRENT_TIME - RETRY_START))
                
                if [ $ELAPSED -gt 300 ]; then
                    # 5 minutes elapsed, WiFi failed - start hotspot
                    log "WiFi connection timeout after 5 minutes, starting hotspot..."
                    rm -f /var/run/wifi-retry-start
                    start_hotspot_mode
                else
                    # Still within retry window
                    log "WiFi connecting... ${ELAPSED}s elapsed (timeout: 300s)"
                    sleep 10
                fi
            else
                # First detection of WiFi config without connection
                log "WiFi configured but not connected, starting 5-minute retry timer..."
                
                # Ensure wpa_supplicant is unmasked and enabled
                systemctl unmask wpa_supplicant 2>/dev/null || true
                systemctl enable wpa_supplicant 2>/dev/null || true
                systemctl restart wpa_supplicant 2>/dev/null || true
                log "Ensured wpa_supplicant is running for WiFi connection attempt"
                
                echo "wifi_retry" > "$STATE_FILE"
                date +%s > /var/run/wifi-retry-start
                sleep 10
            fi
            ;;
        2)
            # No WiFi configured - start hotspot immediately
            CURRENT_STATE=$(cat "$STATE_FILE" 2>/dev/null || echo "unknown")
            if [ "$CURRENT_STATE" != "hotspot" ]; then
                log "No WiFi configured and no internet, starting hotspot..."
                start_hotspot_mode
            fi
            ;;
    esac
done
MONITOREOF

chmod +x /opt/adsb/wifi-manager/network-monitor.sh

# Create captive portal directory and files
echo "Creating captive portal..."
mkdir -p /opt/adsb/captive-portal/templates

# Captive portal Python script
cat > /opt/adsb/captive-portal/portal.py << 'PORTALEOF'
#!/usr/bin/env python3
"""TAKNET-PS Captive Portal - WiFi configuration wizard"""

from flask import Flask, render_template, request, jsonify, redirect
import subprocess
import re

app = Flask(__name__)

def scan_wifi():
    """Scan for available WiFi networks"""
    try:
        result = subprocess.run(['iwlist', 'wlan0', 'scan'], capture_output=True, text=True, timeout=10)
        networks = []
        current = {}
        
        for line in result.stdout.split('\n'):
            line = line.strip()
            if 'ESSID:' in line:
                ssid = re.search(r'ESSID:"([^"]*)"', line)
                if ssid and ssid.group(1):
                    current['ssid'] = ssid.group(1)
            elif 'Quality=' in line:
                quality = re.search(r'Quality=(\d+)/(\d+)', line)
                if quality:
                    signal = int((int(quality.group(1)) / int(quality.group(2))) * 100)
                    current['signal'] = signal
            elif 'Encryption key:' in line:
                current['secured'] = 'on' in line.lower()
                if 'ssid' in current:
                    networks.append(current.copy())
                current = {}
        
        unique = {}
        for net in networks:
            ssid = net['ssid']
            if ssid not in unique or net['signal'] > unique[ssid]['signal']:
                unique[ssid] = net
        
        return sorted(unique.values(), key=lambda x: x['signal'], reverse=True)
    except Exception as e:
        print(f"Error scanning WiFi: {e}")
        return []

def connect_wifi(ssid, password=''):
    """Configure WiFi connection"""
    try:
        if password:
            result = subprocess.run(['wpa_passphrase', ssid, password], capture_output=True, text=True, timeout=10)
            network_config = result.stdout
        else:
            network_config = f'network={{\n    ssid="{ssid}"\n    key_mgmt=NONE\n}}\n'
        
        config = 'country=US\nctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev\nupdate_config=1\n\n' + network_config
        
        with open('/etc/wpa_supplicant/wpa_supplicant.conf', 'w') as f:
            f.write(config)
        
        subprocess.run(['systemctl', 'unmask', 'wpa_supplicant'], check=False)
        subprocess.run(['systemctl', 'enable', 'wpa_supplicant'], check=False)
        subprocess.Popen(['bash', '-c', 'sleep 5 && reboot'])
        return True
    except Exception as e:
        print(f"Error configuring WiFi: {e}")
        return False

@app.route('/')
def index():
    return render_template('portal.html')

@app.route('/generate_204')
@app.route('/hotspot-detect.html')
@app.route('/connecttest.txt')
@app.route('/success.txt')
def captive_portal_detect():
    return redirect('/')

@app.route('/api/scan', methods=['GET'])
def api_scan():
    networks = scan_wifi()
    return jsonify({'success': True, 'networks': networks})

@app.route('/api/connect', methods=['POST'])
def api_connect():
    data = request.json
    ssid = data.get('ssid', '')
    password = data.get('password', '')
    
    if not ssid:
        return jsonify({'success': False, 'message': 'SSID required'}), 400
    
    if connect_wifi(ssid, password):
        return jsonify({'success': True, 'message': 'Configuration saved. Device will reboot in 5 seconds.'})
    else:
        return jsonify({'success': False, 'message': 'Failed to configure WiFi'}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8888, debug=False)
PORTALEOF

chmod +x /opt/adsb/captive-portal/portal.py

# Download portal HTML template from GitHub or create it
wget -q $REPO/captive-portal/templates/portal.html -O /opt/adsb/captive-portal/templates/portal.html 2>/dev/null || \
cat > /opt/adsb/captive-portal/templates/portal.html << 'HTMLEOF'
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>TAKNET-PS WiFi Setup</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }
        .container {
            background: white;
            border-radius: 20px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            max-width: 500px;
            width: 100%;
            padding: 40px;
        }
        h1 { color: #333; margin-bottom: 10px; font-size: 28px; text-align: center; }
        .subtitle { text-align: center; color: #666; margin-bottom: 30px; font-size: 14px; }
        .scan-button {
            width: 100%;
            padding: 15px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            border-radius: 10px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            margin-bottom: 20px;
        }
        .scan-button:disabled { opacity: 0.6; cursor: not-allowed; }
        .networks { max-height: 400px; overflow-y: auto; }
        .network {
            padding: 15px;
            border: 2px solid #e0e0e0;
            border-radius: 10px;
            margin-bottom: 10px;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }
        .network:hover { border-color: #667eea; background: #f8f9ff; }
        .network.selected { border-color: #667eea; background: #f0f2ff; }
        .network-name { font-weight: 600; color: #333; }
        .network-details { font-size: 12px; color: #666; margin-top: 5px; }
        .password-section { margin-bottom: 20px; display: none; }
        label { display: block; margin-bottom: 8px; color: #333; font-weight: 600; }
        input[type="password"] {
            width: 100%;
            padding: 12px;
            border: 2px solid #e0e0e0;
            border-radius: 10px;
            font-size: 16px;
        }
        .connect-button {
            width: 100%;
            padding: 15px;
            background: #10b981;
            color: white;
            border: none;
            border-radius: 10px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            display: none;
        }
        .status { padding: 15px; border-radius: 10px; text-align: center; margin-top: 20px; display: none; }
        .status.show { display: block; }
        .status.success { background: #d1fae5; color: #065f46; }
        .countdown { 
            font-size: 72px; 
            font-weight: bold; 
            margin: 30px 0; 
            color: #667eea;
            line-height: 1;
        }
        .reboot-info {
            margin: 20px 0;
            padding: 15px;
            background: #f0f9ff;
            border-radius: 10px;
            font-size: 14px;
            line-height: 1.6;
        }
        .reboot-info strong { color: #0369a1; display: block; margin-bottom: 8px; font-size: 16px; }
        .success-check { font-size: 48px; margin-bottom: 15px; }
        @media (max-width: 480px) {
            .container { padding: 25px; }
            h1 { font-size: 24px; }
            .countdown { font-size: 56px; }
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🛩️ TAKNET-PS</h1>
        <p class="subtitle">WiFi Configuration Portal</p>
        <button class="scan-button" onclick="scanNetworks()" id="scanBtn">📡 Scan for WiFi Networks</button>
        <div id="networks" class="networks"></div>
        <div id="passwordSection" class="password-section">
            <label>WiFi Password:</label>
            <input type="password" id="password" placeholder="Enter password">
        </div>
        <button class="connect-button" onclick="connectNetwork()" id="connectBtn">🔗 Connect to Network</button>
        <div id="status" class="status"></div>
    </div>
    <script>
        let selectedNetwork = null;
        async function scanNetworks() {
            const btn = document.getElementById('scanBtn');
            const networksDiv = document.getElementById('networks');
            btn.disabled = true;
            networksDiv.innerHTML = '';
            try {
                const response = await fetch('/api/scan');
                const data = await response.json();
                if (data.success && data.networks.length > 0) {
                    data.networks.forEach(network => {
                        const div = document.createElement('div');
                        div.className = 'network';
                        div.onclick = () => selectNetwork(network, div);
                        div.innerHTML = `<div><div class="network-name">${network.ssid}</div><div class="network-details">${network.secured ? '🔒 Secured' : '🔓 Open'} • Signal: ${network.signal}%</div></div>`;
                        networksDiv.appendChild(div);
                    });
                }
            } catch (error) {
                alert('Error scanning networks');
            } finally {
                btn.disabled = false;
            }
        }
        function selectNetwork(network, element) {
            selectedNetwork = network;
            document.querySelectorAll('.network').forEach(n => n.classList.remove('selected'));
            element.classList.add('selected');
            document.getElementById('passwordSection').style.display = network.secured ? 'block' : 'none';
            document.getElementById('connectBtn').style.display = 'block';
        }
        async function connectNetwork() {
            if (!selectedNetwork) return;
            const password = document.getElementById('password').value;
            if (selectedNetwork.secured && !password) {
                alert('Please enter the WiFi password');
                return;
            }
            const connectBtn = document.getElementById('connectBtn');
            connectBtn.disabled = true;
            try {
                const response = await fetch('/api/connect', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ssid: selectedNetwork.ssid, password: password})
                });
                const data = await response.json();
                if (data.success) {
                    // Hide all main content
                    document.querySelectorAll('.container > *:not(#status)').forEach(el => el.style.display = 'none');
                    
                    const statusDiv = document.getElementById('status');
                    statusDiv.className = 'status show success';
                    statusDiv.innerHTML = `
                        <div class="success-check">✓</div>
                        <div style="font-size: 20px; font-weight: 600; margin-bottom: 15px;">
                            Configuration Saved!
                        </div>
                        <div class="countdown" id="countdown">5</div>
                        <div class="reboot-info">
                            <strong>Device Rebooting...</strong>
                            <div>Network: <strong>${selectedNetwork.ssid}</strong></div>
                            <div style="margin-top: 10px; padding-top: 10px; border-top: 1px solid #bae6fd;">
                                After reboot, connect to your WiFi network and visit:
                            </div>
                            <div style="margin-top: 5px; font-weight: 600; color: #0369a1;">
                                taknet-ps.local/web
                            </div>
                            <div style="margin-top: 15px; font-size: 12px; color: #64748b;">
                                ⓘ If connection fails, this hotspot will restart automatically
                            </div>
                        </div>
                    `;
                    
                    // Countdown
                    let count = 5;
                    const countdownEl = document.getElementById('countdown');
                    const interval = setInterval(() => {
                        count--;
                        if (countdownEl) countdownEl.textContent = count;
                        if (count <= 0) {
                            clearInterval(interval);
                            if (countdownEl) countdownEl.textContent = '⏳';
                        }
                    }, 1000);
                } else {
                    alert('Failed: ' + data.message);
                    connectBtn.disabled = false;
                }
            } catch (error) {
                alert('Error: ' + error.message);
                connectBtn.disabled = false;
            }
        }
        window.addEventListener('load', () => setTimeout(scanNetworks, 500));
    </script>
</body>
</html>
HTMLEOF

echo "✓ Captive portal files created"

# Create systemd services
cat > /etc/systemd/system/captive-portal.service << 'PORTALEOF'
[Unit]
Description=TAKNET-PS WiFi Captive Portal
After=network.target hostapd.service
Requires=hostapd.service
PartOf=hostapd.service

[Service]
Type=simple
User=root
WorkingDirectory=/opt/adsb/captive-portal
ExecStart=/usr/bin/python3 /opt/adsb/captive-portal/portal.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
PORTALEOF

cat > /etc/systemd/system/network-monitor.service << 'MONITOREOF'
[Unit]
Description=TAKNET-PS Network Monitor
After=network-online.target
Wants=network-online.target
Conflicts=wpa_supplicant.service

[Service]
Type=simple
ExecStart=/opt/adsb/wifi-manager/network-monitor.sh
Restart=always
RestartSec=10
ExecStartPre=-/usr/bin/systemctl stop wpa_supplicant

[Install]
WantedBy=multi-user.target
MONITOREOF

cat > /etc/systemd/system/tunnel-client.service << 'TUNNELEOF'
[Unit]
Description=TAKNET-PS Remote access tunnel client
After=network-online.target adsb-web.service
Wants=network-online.target

[Service]
Type=simple
Environment=PYTHONUNBUFFERED=1
ExecStartPre=/bin/sh -c '/usr/bin/python3 -m pip install --quiet websocket-client 2>/dev/null || /usr/bin/python3 -m pip install --quiet --break-system-packages websocket-client 2>/dev/null || true'
ExecStart=/usr/bin/python3 /opt/adsb/scripts/tunnel_client.py
Restart=on-failure
RestartSec=10
# When TUNNEL_AGGREGATOR_URL is unset, script exits 0 and we do not restart

[Install]
WantedBy=multi-user.target
TUNNELEOF

# Disable (but don't mask) wpa_supplicant - network-monitor will manage it
# Using disable instead of mask allows wpa_supplicant to be started when needed
systemctl disable wpa_supplicant 2>/dev/null || true

systemctl daemon-reload
systemctl enable network-monitor captive-portal tunnel-client
# Start tunnel when .env has aggregator URL (fixes feeders updated from pre-tunnel versions)
bash /opt/adsb/scripts/ensure-tunnel-client.sh 2>/dev/null || true

echo "✓ WiFi hotspot manager installed"

# Create ultrafeeder systemd service
echo "Creating ultrafeeder service..."
cat > /etc/systemd/system/ultrafeeder.service << 'SVCEOF'
[Unit]
Description=TAKNET-PS-ADSB Ultrafeeder
Requires=docker.service
After=docker.service network-online.target
Wants=network-online.target

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/opt/adsb/config
EnvironmentFile=/opt/adsb/config/.env
ExecStartPre=/usr/bin/python3 /opt/adsb/scripts/config_builder.py
ExecStart=/usr/bin/docker compose up -d --no-color --remove-orphans
ExecStartPost=/bin/bash -c 'echo "Waiting for containers to be ready..." >&2; \
    max_attempts=60; \
    attempt=0; \
    while [ $attempt -lt $max_attempts ]; do \
        attempt=$((attempt + 1)); \
        if docker ps --filter name=ultrafeeder --filter status=running --format "{{.Names}}" 2>/dev/null | grep -q ultrafeeder; then \
            echo "Ultrafeeder container is running" >&2; \
            exit 0; \
        fi; \
        echo "Waiting for containers... ($attempt/$max_attempts)" >&2; \
        sleep 2; \
    done; \
    echo "WARNING: Containers took longer than expected to start. Check: docker ps" >&2; \
    exit 0'
ExecStop=/usr/bin/docker compose down
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
SVCEOF

# Create web UI systemd service
echo "Creating web interface service..."
cat > /etc/systemd/system/adsb-web.service << 'WEBSVC'
[Unit]
Description=TAKNET-PS-ADSB Web Interface
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/adsb/web
ExecStart=/usr/bin/python3 /opt/adsb/web/app.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
WEBSVC

# Phase B: Run automatic migration (silent, idempotent)
if [ -f /opt/adsb/config/.env ] && [ -f /opt/adsb/scripts/migrate-phase-b.py ]; then
    echo "Running Phase B migration (adding SoapySDR variables)..."
    python3 /opt/adsb/scripts/migrate-phase-b.py 2>/dev/null || true
    echo "✓ Configuration migrated to Phase B format"
fi

# Default deployment mode (stationary vs mobile) if missing
if [ -f /opt/adsb/config/.env ] && ! grep -q '^FEEDER_DEPLOYMENT_MODE=' /opt/adsb/config/.env 2>/dev/null; then
    echo "FEEDER_DEPLOYMENT_MODE=stationary" >> /opt/adsb/config/.env
    echo "✓ FEEDER_DEPLOYMENT_MODE defaulted to stationary"
fi

# Enable services
systemctl daemon-reload
systemctl enable ultrafeeder
systemctl enable adsb-web

# Web UI service
# - Fresh install: start web UI for setup wizard
# - Update mode: restart to ensure template/JS cache is reloaded
if [ "$UPDATE_MODE" = true ]; then
    systemctl restart adsb-web 2>/dev/null || systemctl start adsb-web
else
    systemctl start adsb-web
fi

# Set permissions
if [ "$SUDO_USER" ]; then
    chown -R $SUDO_USER:$SUDO_USER /opt/adsb
fi

# Persist Git branch for future updates (scripts/updater.sh reads this)
echo -n "$INSTALL_BRANCH" > /opt/adsb/REPO_BRANCH

# Get IP address
IP=$(hostname -I | awk '{print $1}')

# Done
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if [ "$UPDATE_MODE" = true ]; then
    # Ensure updated templates/static files and compose changes are active even when
    # this script is invoked directly in update mode (outside updater.sh wrapper).
    systemctl restart adsb-web 2>/dev/null || true
    systemctl restart ultrafeeder 2>/dev/null || true

    echo "✓ Update complete!"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo "✅ TAKNET-PS has been updated successfully"
    echo ""
    echo "   • Configuration preserved"
    echo "   • Services will restart automatically"
    echo "   • Return to dashboard: http://taknet-ps.local"
    echo ""
    bash /opt/adsb/scripts/ensure-tunnel-client.sh 2>/dev/null || true
    
    # Remove update lock file
    rm -f /tmp/taknet_update.lock
else
    echo "✓ Installation complete!"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo "🌐 Open your browser and go to:"
    echo ""
    echo "   http://taknet-ps.local"
    echo ""
    echo "   Complete the setup wizard to configure your feeder."
    echo ""
    echo "After setup, you can access:"
    echo "   • Setup/Dashboard: http://taknet-ps.local"
    echo "   • Live Map: http://taknet-ps.local:8080"
    echo ""
    echo "   (Or use http://$IP if .local doesn't work)"
    echo ""
    echo "Manual commands (if needed):"
    echo "   • Start: sudo systemctl start ultrafeeder"
    echo "   • Restart: sudo systemctl restart ultrafeeder"
    echo "   • Logs: sudo docker logs ultrafeeder"
    echo ""
    echo "🔒 SSH Access:"
    echo "   • Connect via NetBird or Tailscale, then:"
    echo "     ssh remote@<vpn-ip>  (password: adsb)"
    echo "   • Not accessible from public internet"
    echo ""
    echo "📊 Network Monitoring:"
    echo "   • vnstat configured (30-day retention)"
    echo "   • Usage: vnstat -d (daily stats)"
    echo ""
fi
