#!/bin/bash
# Emergency SSH Fix for Tailscale Access
# Use when SSH times out on both Primary and Private Tailscale

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Emergency SSH Fix for Tailscale"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo "❌ This script must be run with sudo"
    exit 1
fi

echo "1. Backing up SSH config..."
cp /etc/ssh/sshd_config /etc/ssh/sshd_config.backup-emergency-$(date +%Y%m%d-%H%M%S)
echo "✓ Backup created"
echo ""

echo "2. Checking SSH service..."
if systemctl is-active --quiet sshd; then
    echo "✓ SSH service is running"
else
    echo "⚠️  SSH service is NOT running - starting it..."
    systemctl start sshd
fi
echo ""

echo "3. Checking what SSH is listening on..."
netstat -tlnp | grep :22 || ss -tlnp | grep :22
echo ""

echo "4. Removing old SSH rules..."
# Remove any old TAKNET-PS blocks
sed -i '/# TAKNET-PS/d' /etc/ssh/sshd_config
sed -i '/Match User remote/d' /etc/ssh/sshd_config
sed -i '/PasswordAuthentication yes/d' /etc/ssh/sshd_config
sed -i '/PubkeyAuthentication yes/d' /etc/ssh/sshd_config
sed -i '/DenyUsers.*remote/d' /etc/ssh/sshd_config
echo "✓ Old rules removed"
echo ""

echo "5. Adding correct SSH configuration..."
cat >> /etc/ssh/sshd_config << 'SSHEOF'

# TAKNET-PS Remote User - All Tailscale Networks
# Allows SSH from Primary AND Private Tailscale (entire CGNAT range)
Match User remote Address 100.64.0.0/10
    PasswordAuthentication yes
    PubkeyAuthentication yes
SSHEOF
echo "✓ New configuration added"
echo ""

echo "6. Checking for ListenAddress restrictions..."
if grep -q "^ListenAddress" /etc/ssh/sshd_config | grep -v "^#"; then
    echo "⚠️  Found ListenAddress restrictions:"
    grep "^ListenAddress" /etc/ssh/sshd_config
    echo ""
    echo "   These may prevent SSH from listening on Tailscale interfaces!"
    echo "   Commenting them out..."
    sed -i 's/^ListenAddress/#ListenAddress/' /etc/ssh/sshd_config
    echo "✓ ListenAddress lines commented out"
else
    echo "✓ No ListenAddress restrictions (SSH will listen on all interfaces)"
fi
echo ""

echo "7. Testing SSH configuration..."
if sshd -t 2>&1; then
    echo "✓ SSH configuration is valid"
else
    echo "❌ SSH configuration has errors:"
    sshd -t
    echo ""
    echo "Restoring backup..."
    cp /etc/ssh/sshd_config.backup-emergency-$(date +%Y%m%d-%H%M%S) /etc/ssh/sshd_config
    exit 1
fi
echo ""

echo "8. Restarting SSH service..."
systemctl restart sshd
if [ $? -eq 0 ]; then
    echo "✓ SSH service restarted successfully"
else
    echo "❌ Failed to restart SSH service"
    exit 1
fi
echo ""

echo "9. Verifying Tailscale IPs..."
# Primary Tailscale
PRIMARY_IP=$(tailscale ip -4 2>/dev/null)
if [ -n "$PRIMARY_IP" ]; then
    echo "✓ Primary Tailscale IP: $PRIMARY_IP"
else
    echo "⚠️  Primary Tailscale not connected"
fi

# Private Tailscale
PRIVATE_IP=$(docker exec tailscale-private tailscale --socket=/var/run/tailscale-private/tailscaled.sock ip -4 2>/dev/null)
if [ -n "$PRIVATE_IP" ]; then
    echo "✓ Private Tailscale IP: $PRIVATE_IP"
else
    echo "⚠️  Private Tailscale not connected"
fi
echo ""

echo "10. Testing SSH ports from localhost..."
# Test Primary Tailscale
if [ -n "$PRIMARY_IP" ]; then
    echo "Testing Primary Tailscale ($PRIMARY_IP)..."
    timeout 2 bash -c "echo | nc -w 1 $PRIMARY_IP 22" 2>/dev/null
    if [ $? -eq 0 ]; then
        echo "✓ SSH port 22 is OPEN on Primary Tailscale"
    else
        echo "❌ SSH port 22 is CLOSED on Primary Tailscale"
    fi
fi

# Test Private Tailscale
if [ -n "$PRIVATE_IP" ]; then
    echo "Testing Private Tailscale ($PRIVATE_IP)..."
    timeout 2 bash -c "echo | nc -w 1 $PRIVATE_IP 22" 2>/dev/null
    if [ $? -eq 0 ]; then
        echo "✓ SSH port 22 is OPEN on Private Tailscale"
    else
        echo "❌ SSH port 22 is CLOSED on Private Tailscale"
    fi
fi
echo ""

echo "11. Checking Tailscale interfaces..."
ip addr show | grep -E "tailscale|ts-private" -A 2
echo ""

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Fix Complete!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "SSH Configuration:"
echo "  - Remote user SSH enabled"
echo "  - Allowed from: 100.64.0.0/10 (all Tailscale IPs)"
echo "  - Listening on: All interfaces (no ListenAddress restrictions)"
echo ""
echo "Test SSH access:"
if [ -n "$PRIMARY_IP" ]; then
    echo "  ssh remote@$PRIMARY_IP"
fi
if [ -n "$PRIVATE_IP" ]; then
    echo "  ssh remote@$PRIVATE_IP"
fi
echo ""
echo "If still not working:"
echo "  1. Check firewall: sudo ufw status"
echo "  2. Check SSH logs: sudo journalctl -u sshd -n 50"
echo "  3. Try from remote machine with verbose: ssh -vvv remote@<ip>"
echo ""
