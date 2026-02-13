#!/bin/bash
# TAKNET-PS Update Script
# Handles backing up config, updating system, and restoring config

set -e

REPO_URL="https://raw.githubusercontent.com/cfd2474/TAKNET-PS_ADS-B_Feeder/main"
BACKUP_DIR="/opt/adsb/backup"
CONFIG_FILE="/opt/adsb/config/.env"
VERSION_FILE="/opt/adsb/VERSION"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  TAKNET-PS System Update"
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
    
    # Run installer in update mode
    if bash "$TEMP_INSTALLER" --update; then
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
    
    # Restart ultrafeeder (rebuilds config with new code)
    if systemctl restart ultrafeeder 2>/dev/null; then
        echo "   ✓ Ultrafeeder restarted"
    else
        echo "   ⚠ Failed to restart ultrafeeder"
    fi
    
    # Restart web interface
    if systemctl restart adsb-web 2>/dev/null; then
        echo "   ✓ Web interface restarted"
    else
        echo "   ⚠ Failed to restart web interface"
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
