#!/bin/bash
# Configure SSH to allow 'remote' user only from Tailscale network
# Run after Tailscale is configured

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  SSH Tailscale-Only Access Configuration"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo "❌ This script must be run with sudo"
    exit 1
fi

# Check if Tailscale is installed and running
if ! command -v tailscale &> /dev/null; then
    echo "⚠️  Tailscale not installed. Install Tailscale first."
    exit 1
fi

# Get Tailscale IP range
TAILSCALE_IP=$(tailscale ip -4 2>/dev/null)
if [ -z "$TAILSCALE_IP" ]; then
    echo "⚠️  Tailscale not connected. Connect to Tailscale first."
    exit 1
fi

# Extract the /16 subnet (e.g., 100.117.x.x -> 100.117.0.0/16)
TAILSCALE_SUBNET=$(echo $TAILSCALE_IP | cut -d'.' -f1-2).0.0/16

echo "Tailscale IP detected: $TAILSCALE_IP"
echo "Tailscale subnet: $TAILSCALE_SUBNET"
echo ""

# Create Match block for remote user
SSH_CONFIG_FILE="/etc/ssh/sshd_config"
BACKUP_FILE="/etc/ssh/sshd_config.backup-$(date +%Y%m%d-%H%M%S)"

# Backup original config
cp $SSH_CONFIG_FILE $BACKUP_FILE
echo "✓ Backed up SSH config to $BACKUP_FILE"

# Remove any existing DenyUsers remote line (from install)
if grep -q "^DenyUsers remote" $SSH_CONFIG_FILE; then
    sed -i '/^DenyUsers remote/d' $SSH_CONFIG_FILE
    # Also remove the comment line before it
    sed -i '/# TAKNET-PS: Block remote user until Tailscale configured/d' $SSH_CONFIG_FILE
    echo "✓ Removed DenyUsers restriction for remote user"
fi

# Remove any existing Match block for remote user
if grep -q "Match User remote" $SSH_CONFIG_FILE; then
    # Remove the entire Match block
    sed -i '/# TAKNET-PS Remote User - Tailscale Only Access/,/^Match\|^$/d' $SSH_CONFIG_FILE
    echo "✓ Removed existing Match block for remote user"
fi

# Add AllowUsers at top level and Match block for address restriction
cat >> $SSH_CONFIG_FILE << EOF

# TAKNET-PS Remote User - Tailscale Only Access
# Allow remote user only from Tailscale network
Match User remote Address $TAILSCALE_SUBNET
    PasswordAuthentication yes
    PubkeyAuthentication yes
EOF

echo "✓ Added SSH configuration for remote user"

# Test SSH config
if sshd -t; then
    echo "✓ SSH configuration valid"
    
    # Restart SSH
    systemctl restart sshd
    echo "✓ SSH service restarted"
    
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  Configuration Complete!"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo "Remote Access Details:"
    echo "  Username: remote"
    echo "  Password: adsb"
    echo "  Access: Tailscale network only ($TAILSCALE_SUBNET)"
    echo ""
    echo "Test connection:"
    echo "  ssh remote@$TAILSCALE_IP"
    echo ""
    echo "The 'remote' user has sudo access for:"
    echo "  • systemctl (ultrafeeder, adsb-web)"
    echo "  • docker commands"
    echo "  • journalctl logs"
    echo "  • vnstat monitoring"
    echo "  • config_builder.py"
    echo ""
else
    echo "❌ SSH configuration test failed"
    echo "   Restoring backup..."
    cp $BACKUP_FILE $SSH_CONFIG_FILE
    systemctl restart sshd
    echo "   SSH config restored from backup"
    exit 1
fi
