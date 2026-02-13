#!/bin/bash
# Verify and fix remote user SSH access via Tailscale

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Remote User SSH Access Verification"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo "❌ This script must be run with sudo"
    exit 1
fi

# 1. Check if remote user exists
echo "1. Checking remote user..."
if id "remote" &>/dev/null; then
    echo "   ✓ User 'remote' exists"
else
    echo "   ❌ User 'remote' does not exist"
    exit 1
fi

# 2. Check password
echo ""
echo "2. Checking password..."
if grep -q "^remote:" /etc/shadow; then
    echo "   ✓ Password is set"
else
    echo "   ⚠️  No password set - setting to 'adsb'"
    echo "remote:adsb" | chpasswd
fi

# 3. Check Tailscale status
echo ""
echo "3. Checking Tailscale..."
if ! command -v tailscale &> /dev/null; then
    echo "   ❌ Tailscale not installed"
    exit 1
fi

TAILSCALE_IP=$(tailscale ip -4 2>/dev/null)
if [ -z "$TAILSCALE_IP" ]; then
    echo "   ❌ Tailscale not connected"
    exit 1
fi

TAILSCALE_SUBNET=$(echo $TAILSCALE_IP | cut -d'.' -f1-2).0.0/16
echo "   ✓ Tailscale connected: $TAILSCALE_IP"
echo "   ✓ Tailscale subnet: $TAILSCALE_SUBNET"

# 4. Check SSH config
echo ""
echo "4. Checking SSH configuration..."

# Check for DenyUsers
if grep -q "^DenyUsers.*remote" /etc/ssh/sshd_config; then
    echo "   ⚠️  Found DenyUsers blocking remote - REMOVING"
    sed -i '/^DenyUsers.*remote/d' /etc/ssh/sshd_config
    sed -i '/# TAKNET-PS: Block remote user/d' /etc/ssh/sshd_config
fi

# Check for existing Match block
if grep -q "Match User remote" /etc/ssh/sshd_config; then
    echo "   ✓ Match block exists"
else
    echo "   ⚠️  Match block missing - ADDING"
    cat >> /etc/ssh/sshd_config << SSHEOF

# TAKNET-PS Remote User - Tailscale Only Access
Match User remote Address $TAILSCALE_SUBNET
    PasswordAuthentication yes
    PubkeyAuthentication yes
SSHEOF
fi

# 5. Test SSH config
echo ""
echo "5. Testing SSH configuration..."
if sshd -t 2>&1; then
    echo "   ✓ SSH configuration valid"
else
    echo "   ❌ SSH configuration has errors"
    sshd -t
    exit 1
fi

# 6. Restart SSH
echo ""
echo "6. Restarting SSH service..."
if systemctl restart sshd; then
    echo "   ✓ SSH restarted successfully"
else
    echo "   ❌ Failed to restart SSH"
    exit 1
fi

# 7. Show final status
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Configuration Complete!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Remote Access Details:"
echo "  Username: remote"
echo "  Password: adsb"
echo "  Tailscale IP: $TAILSCALE_IP"
echo ""
echo "Test connection from another Tailscale device:"
echo "  ssh remote@$TAILSCALE_IP"
echo ""
echo "Current SSH restrictions:"
grep -A 5 "Match User remote" /etc/ssh/sshd_config | sed 's/^/  /'
echo ""
