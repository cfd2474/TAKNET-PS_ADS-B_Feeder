#!/bin/bash
# TAKNET-PS Update Script
# Handles backing up config, updating system, and restoring config
# Uses the same Git branch as install: /opt/adsb/REPO_BRANCH (written by install.sh),
# or override with: TAKNET_INSTALL_BRANCH=my-branch sudo -E bash /opt/adsb/scripts/updater.sh

set -e

# Match install.sh branch resolution
if [ -n "${TAKNET_INSTALL_BRANCH:-}" ]; then
    INSTALL_BRANCH="$TAKNET_INSTALL_BRANCH"
elif [ -f /opt/adsb/REPO_BRANCH ]; then
    INSTALL_BRANCH=$(tr -d '\n\r' < /opt/adsb/REPO_BRANCH)
else
    INSTALL_BRANCH="main"
fi
if ! echo "$INSTALL_BRANCH" | grep -qE '^[a-zA-Z0-9._/+-]+$'; then
    INSTALL_BRANCH="main"
fi

REPO_URL="https://raw.githubusercontent.com/cfd2474/TAKNET-PS_ADS-B_Feeder/${INSTALL_BRANCH}"
BACKUP_DIR="/opt/adsb/backup"
CONFIG_FILE="/opt/adsb/config/.env"
VERSION_FILE="/opt/adsb/VERSION"
NETBIRD_DEFAULT_MANAGEMENT_URL="https://netbird.tak-solutions.com"
NETBIRD_DEFAULT_SETUP_KEY="C5F35D5B-6B0D-440F-B573-D21C8BE79529"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  TAKNET-PS System Update"
echo "  Git branch: ${INSTALL_BRANCH}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Show current version
if [ -f "$VERSION_FILE" ]; then
    CURRENT_VERSION=$(cat "$VERSION_FILE")
    echo "Current Version: $CURRENT_VERSION"
    echo ""
fi

# Function to backup configuration
backup_config() {
    echo "📦 Backing up current configuration..."
    
    # Create backup directory with timestamp
    TIMESTAMP=$(date +%Y%m%d_%H%M%S)
    BACKUP_PATH="$BACKUP_DIR/config_backup_$TIMESTAMP"
    mkdir -p "$BACKUP_PATH"
    
    # Backup .env file (contains all user settings)
    if [ -f "$CONFIG_FILE" ]; then
        cp "$CONFIG_FILE" "$BACKUP_PATH/.env"
        echo "   ✓ Configuration backed up to: $BACKUP_PATH"
    else
        echo "   ⚠ No configuration file found at $CONFIG_FILE"
        return 1
    fi
    
    # Backup VERSION file
    if [ -f "$VERSION_FILE" ]; then
        cp "$VERSION_FILE" "$BACKUP_PATH/VERSION"
    fi
    
    # Store backup path for restoration
    echo "$BACKUP_PATH" > /tmp/taknet_update_backup_path
    
    return 0
}

# Function to restore configuration
restore_config() {
    BACKUP_PATH=$(cat /tmp/taknet_update_backup_path 2>/dev/null)
    
    if [ -z "$BACKUP_PATH" ] || [ ! -d "$BACKUP_PATH" ]; then
        echo "   ⚠ No backup path found"
        return 1
    fi
    
    echo "📥 Restoring configuration..."
    
    # Restore .env file
    if [ -f "$BACKUP_PATH/.env" ]; then
        cp "$BACKUP_PATH/.env" "$CONFIG_FILE"
        echo "   ✓ Configuration restored"
    else
        echo "   ⚠ No backup configuration found"
        return 1
    fi
    
    # Clean up temp file
    rm -f /tmp/taknet_update_backup_path
    
    return 0
}

# Function to download and run installer
run_update() {
    echo "📥 Downloading latest installer..."
    
    # Download installer
    TEMP_INSTALLER="/tmp/taknet_installer_update.sh"
    if curl -fsSL "$REPO_URL/install/install.sh" -o "$TEMP_INSTALLER"; then
        echo "   ✓ Installer downloaded"
    else
        echo "   ❌ Failed to download installer"
        return 1
    fi
    
    # Make executable
    chmod +x "$TEMP_INSTALLER"
    
    echo "🔄 Running update (this may take a few minutes)..."
    echo ""
    
    # Run installer in update mode (pass branch so REPO matches)
    if bash "$TEMP_INSTALLER" --update --branch "$INSTALL_BRANCH"; then
        echo ""
        echo "   ✓ Update completed successfully"
        rm -f "$TEMP_INSTALLER"
        return 0
    else
        echo ""
        echo "   ❌ Update failed"
        rm -f "$TEMP_INSTALLER"
        return 1
    fi
}

# Function to restart services
restart_services() {
    echo "🔄 Restarting services..."
    
    # Force-refresh critical web files from selected branch to avoid stale template drift.
    # This makes updates deterministic even if a previous installer run partially succeeded.
    echo "   • Syncing web UI files from branch: ${INSTALL_BRANCH}"
    sync_web_file() {
        local rel="$1"
        local dest="/opt/adsb/${rel}"
        local tmp="${dest}.tmp.$$"
        if curl -fsSL "${REPO_URL}/${rel}" -o "${tmp}"; then
            mkdir -p "$(dirname "${dest}")"
            mv "${tmp}" "${dest}"
            echo "   ✓ Synced ${rel}"
        else
            rm -f "${tmp}" 2>/dev/null || true
            echo "   ⚠ Failed to sync ${rel} (keeping existing file)"
        fi
    }
    sync_web_file "web/app.py"
    sync_web_file "web/templates/dashboard.html"
    sync_web_file "web/templates/settings.html"
    sync_web_file "web/templates/setup.html"
    sync_web_file "web/static/js/dashboard.js"
    sync_web_file "web/static/js/setup.js"

    # Verify SSH is configured for remote user via VPN
    if ! grep -q "# TAKNET-PS: remote VPN-only access" /etc/ssh/sshd_config 2>/dev/null; then
        sed -i 's/^#*PasswordAuthentication.*/PasswordAuthentication yes/' /etc/ssh/sshd_config
        sed -i '/^DenyUsers remote/d' /etc/ssh/sshd_config
        sed -i '/# TAKNET-PS: Block remote user/d' /etc/ssh/sshd_config
        cat >> /etc/ssh/sshd_config << 'SSHEOF'

# TAKNET-PS: remote VPN-only access (NetBird + Tailscale use 100.x.x.x)
Match User remote Address 100.*
    PasswordAuthentication yes
SSHEOF
        if sshd -t 2>/dev/null; then
            systemctl restart sshd 2>/dev/null || true
            echo "   ✓ SSH configured: remote user accessible via VPN (100.x.x.x)"
        fi
    else
        echo "   ✓ SSH config verified"
    fi
    CLEANUP_SCRIPT="/opt/adsb/scripts/cleanup-aircraft-data.sh"
    if [ ! -f "$CLEANUP_SCRIPT" ]; then
        cat > "$CLEANUP_SCRIPT" << 'CLEANUP_EOF'
#!/bin/bash
find /opt/adsb/ultrafeeder -type f -mmin +1440 -delete 2>/dev/null
find /opt/adsb/ultrafeeder -type d -empty -delete 2>/dev/null
CLEANUP_EOF
        chmod +x "$CLEANUP_SCRIPT"
    fi
    if ! grep -q "cleanup-aircraft-data" /etc/crontab 2>/dev/null; then
        echo "0 * * * * root $CLEANUP_SCRIPT" >> /etc/crontab
        echo "   ✓ Aircraft data retention (24h) configured"
    fi
    
    # Rebuild docker-compose.yml with new config_builder.py
    echo "   • Rebuilding docker-compose configuration..."
    if python3 /opt/adsb/scripts/config_builder.py 2>/dev/null; then
        echo "   ✓ Docker-compose configuration rebuilt"
    else
        echo "   ⚠ Failed to rebuild docker-compose configuration"
    fi
    
    # Restart ultrafeeder (rebuilds config with new code)
    if systemctl restart ultrafeeder 2>/dev/null; then
        echo "   ✓ Ultrafeeder restarted"
    else
        echo "   ⚠ Failed to restart ultrafeeder"
    fi
    
    # Restart web interface (hard recycle fallback to avoid stale template process state)
    if systemctl restart adsb-web 2>/dev/null; then
        echo "   ✓ Web interface restarted"
    else
        echo "   ⚠ Restart failed, trying stop/start web interface..."
        systemctl stop adsb-web 2>/dev/null || true
        sleep 1
        if systemctl start adsb-web 2>/dev/null; then
            echo "   ✓ Web interface started (after stop/start)"
        else
            echo "   ⚠ Failed to start web interface"
        fi
    fi

    # Quick local health check to confirm Flask is responding post-restart
    if curl -fsS --max-time 6 "http://127.0.0.1:5000/settings" > /dev/null 2>&1; then
        echo "   ✓ Web interface health check passed"
    else
        echo "   ⚠ Web interface health check failed (check: sudo journalctl -u adsb-web -n 80)"
    fi

    # Tunnel: enable unit and start if configured (.env)
    if [ -x /opt/adsb/scripts/ensure-tunnel-client.sh ]; then
        bash /opt/adsb/scripts/ensure-tunnel-client.sh 2>/dev/null && echo "   ✓ Tunnel client enabled/started (if configured)" || true
    elif systemctl restart tunnel-client 2>/dev/null; then
        echo "   ✓ Tunnel client restarted"
    else
        echo "   ⚠ Tunnel client not restarted (run update again or Settings → restart tunnel)"
    fi

    # NetBird update-mode policy:
    # - If already connected: leave key/connection untouched.
    # - If setup key already exists in .env: leave key/connection untouched.
    # - If no setup key: seed default key and initiate connection.
    if command -v netbird &> /dev/null; then
        NB_CONNECTED=false
        if netbird status 2>/dev/null | grep -q "Management: Connected"; then
            NB_CONNECTED=true
        fi

        NB_SETUP_KEY=""
        NB_MGMT_URL=""
        NB_HOSTNAME="$(hostname)"
        if [ -f "$CONFIG_FILE" ]; then
            NB_SETUP_KEY=$(grep "^NETBIRD_SETUP_KEY=" "$CONFIG_FILE" 2>/dev/null | cut -d'=' -f2-)
            NB_MGMT_URL=$(grep "^NETBIRD_MANAGEMENT_URL=" "$CONFIG_FILE" 2>/dev/null | cut -d'=' -f2-)
            _SITE_NAME=$(grep "^MLAT_SITE_NAME=" "$CONFIG_FILE" 2>/dev/null | cut -d'=' -f2-)
            [ -n "$_SITE_NAME" ] && NB_HOSTNAME="$_SITE_NAME"
        fi

        if [ "$NB_CONNECTED" = true ]; then
            echo "   ✓ NetBird already connected (left unchanged)"
        elif [ -n "$NB_SETUP_KEY" ]; then
            echo "   ✓ Existing NetBird setup key found (left unchanged)"
        else
            echo "   • No NetBird setup key found; seeding default and connecting..."
            [ -z "$NB_MGMT_URL" ] && NB_MGMT_URL="$NETBIRD_DEFAULT_MANAGEMENT_URL"

            if [ -f "$CONFIG_FILE" ]; then
                if grep -q "^NETBIRD_MANAGEMENT_URL=" "$CONFIG_FILE" 2>/dev/null; then
                    sed -i "s|^NETBIRD_MANAGEMENT_URL=.*|NETBIRD_MANAGEMENT_URL=${NB_MGMT_URL}|" "$CONFIG_FILE"
                else
                    echo "NETBIRD_MANAGEMENT_URL=${NB_MGMT_URL}" >> "$CONFIG_FILE"
                fi

                if grep -q "^NETBIRD_SETUP_KEY=" "$CONFIG_FILE" 2>/dev/null; then
                    sed -i "s/^NETBIRD_SETUP_KEY=.*/NETBIRD_SETUP_KEY=${NETBIRD_DEFAULT_SETUP_KEY}/" "$CONFIG_FILE"
                else
                    echo "NETBIRD_SETUP_KEY=${NETBIRD_DEFAULT_SETUP_KEY}" >> "$CONFIG_FILE"
                fi
            fi

            if netbird up \
                --setup-key "$NETBIRD_DEFAULT_SETUP_KEY" \
                --management-url "$NB_MGMT_URL" \
                --disable-dns \
                --allow-server-ssh \
                --enable-ssh-root \
                --hostname "${NB_HOSTNAME:-taknet-ps-feeder}" \
                > /dev/null 2>&1; then
                echo "   ✓ NetBird connected using default setup key"
                if [ -f "$CONFIG_FILE" ]; then
                    if grep -q "^NETBIRD_ENABLED=" "$CONFIG_FILE" 2>/dev/null; then
                        sed -i 's/^NETBIRD_ENABLED=.*/NETBIRD_ENABLED=true/' "$CONFIG_FILE"
                    else
                        echo "NETBIRD_ENABLED=true" >> "$CONFIG_FILE"
                    fi
                fi
            else
                echo "   ⚠ NetBird connection attempt failed (default key)"
            fi
        fi
    fi
    
    echo ""
}

# Main update process
main() {
    # Check if running as root
    if [ "$EUID" -ne 0 ]; then 
        echo "❌ This script must be run as root (use sudo)"
        exit 1
    fi
    
    # Step 1: Backup configuration
    if ! backup_config; then
        echo "❌ Backup failed - aborting update"
        exit 1
    fi
    
    echo ""
    
    # Step 2: Run update
    if ! run_update; then
        echo ""
        echo "❌ Update failed - restoring configuration"
        restore_config
        exit 1
    fi
    
    echo ""
    
    # Step 3: Restore configuration
    if ! restore_config; then
        echo "⚠ Warning: Configuration restoration failed"
        echo "   Backup is available at: $(cat /tmp/taknet_update_backup_path 2>/dev/null)"
    fi
    
    echo ""
    
    # Step 4: Restart services
    restart_services
    
    # Show new version
    if [ -f "$VERSION_FILE" ]; then
        NEW_VERSION=$(cat "$VERSION_FILE")
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo "  ✓ Update Complete!"
        echo "  New Version: $NEW_VERSION"
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    fi
    
    echo ""
}

# Run main function
main
