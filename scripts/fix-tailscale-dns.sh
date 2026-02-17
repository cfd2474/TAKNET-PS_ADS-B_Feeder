#!/bin/bash
# Fix Tailscale DNS Override Issue
# Tailscale MagicDNS (100.100.100.100) blocks public DNS resolution

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Tailscale DNS Override Fix"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo "❌ This script must be run with sudo"
    exit 1
fi

echo "Current DNS configuration:"
cat /etc/resolv.conf
echo ""

# Check if Tailscale is overriding DNS
if grep -q "100.100.100.100" /etc/resolv.conf; then
    echo "⚠️  Tailscale MagicDNS is overriding system DNS"
    echo "   This prevents resolution of public domains"
    echo ""
else
    echo "✓ Tailscale DNS not detected"
    echo ""
fi

# Fix Primary Tailscale
echo "1. Disabling DNS override on Primary Tailscale..."
if command -v tailscale &> /dev/null; then
    if tailscale set --accept-dns=false 2>&1; then
        echo "   ✓ Primary Tailscale DNS override disabled"
    else
        echo "   ⚠️  Failed to disable Primary Tailscale DNS"
    fi
else
    echo "   ⏭️  Primary Tailscale not installed"
fi
echo ""

# Fix Private Tailscale (if running)
echo "2. Disabling DNS override on Private Tailscale..."
if docker ps --format '{{.Names}}' 2>/dev/null | grep -q "^tailscale-private$"; then
    if docker exec tailscale-private tailscale --socket=/var/run/tailscale-private/tailscaled.sock set --accept-dns=false 2>&1; then
        echo "   ✓ Private Tailscale DNS override disabled"
    else
        echo "   ⚠️  Failed to disable Private Tailscale DNS"
    fi
else
    echo "   ⏭️  Private Tailscale not running"
fi
echo ""

# Configure NetworkManager DNS
echo "3. Configuring NetworkManager DNS..."
if command -v nmcli &> /dev/null; then
    # Find the primary wired connection
    CONN=$(nmcli -t -f NAME,DEVICE connection show --active | grep "eth0" | cut -d':' -f1)
    
    if [ -n "$CONN" ]; then
        echo "   Found connection: $CONN"
        nmcli connection modify "$CONN" ipv4.dns "8.8.8.8 8.8.4.4" 2>&1
        nmcli connection modify "$CONN" ipv4.ignore-auto-dns yes 2>&1
        nmcli connection up "$CONN" 2>&1 > /dev/null
        echo "   ✓ NetworkManager DNS configured (Google DNS)"
    else
        echo "   ⚠️  Could not find active connection"
    fi
else
    echo "   ⚠️  NetworkManager not found"
fi
echo ""

# Wait for DNS to propagate
sleep 2

echo "4. Verifying DNS configuration..."
echo ""
cat /etc/resolv.conf
echo ""

# Test DNS resolution
echo "5. Testing DNS resolution..."
if ping -c 2 raw.githubusercontent.com > /dev/null 2>&1; then
    echo "   ✓ DNS resolution working!"
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  DNS Fixed Successfully!"
    echo "  Update check should now work"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
else
    echo "   ❌ DNS resolution still failing"
    echo ""
    echo "Troubleshooting:"
    echo "  1. Check internet connection: ping 8.8.8.8"
    echo "  2. Restart networking: sudo systemctl restart NetworkManager"
    echo "  3. Check resolv.conf: cat /etc/resolv.conf"
fi
echo ""
