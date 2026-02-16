#!/bin/bash
# Update SSH configuration to allow remote user from ALL Tailscale networks
# This supports both Primary and Private Tailscale with different subnets

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Updating SSH for All Tailscale Networks"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo "❌ This script must be run with sudo"
    exit 1
fi

# Backup SSH config
cp /etc/ssh/sshd_config /etc/ssh/sshd_config.backup-$(date +%Y%m%d-%H%M%S)
echo "✓ SSH config backed up"

# Remove old Match blocks
echo "Removing old Match blocks..."
sed -i '/# TAKNET-PS Remote User/,+2d' /etc/ssh/sshd_config
sed -i '/Match User remote Address/d' /etc/ssh/sshd_config
sed -i '/# TAKNET-PS: Block remote user/d' /etc/ssh/sshd_config
sed -i '/^DenyUsers.*remote/d' /etc/ssh/sshd_config

# Add new Match block for ALL Tailscale CGNAT range
# 100.64.0.0/10 covers the entire Tailscale IP space
cat >> /etc/ssh/sshd_config << 'SSHEOF'

# TAKNET-PS Remote User - All Tailscale Networks
# Allows SSH from Primary AND Private Tailscale
Match User remote Address 100.64.0.0/10
    PasswordAuthentication yes
    PubkeyAuthentication yes
SSHEOF

echo "✓ Added SSH access for ALL Tailscale networks (100.64.0.0/10)"

# Test SSH config
echo ""
echo "Testing SSH configuration..."
if sshd -t 2>&1; then
    echo "✓ SSH configuration valid"
else
    echo "❌ SSH configuration has errors - restoring backup"
    cp /etc/ssh/sshd_config.backup-$(date +%Y%m%d-%H%M%S) /etc/ssh/sshd_config
    exit 1
fi

# Restart SSH
echo ""
echo "Restarting SSH service..."
if systemctl restart sshd; then
    echo "✓ SSH restarted successfully"
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  SSH Access Enabled for Both Networks:"
    echo "  • Primary Tailscale: Enabled"
    echo "  • Private Tailscale: Enabled"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
else
    echo "❌ Failed to restart SSH"
    exit 1
fi
