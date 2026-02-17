#!/bin/bash
# Fix DNS resolution issues

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  DNS Fix for TAKNET-PS"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo "❌ This script must be run with sudo"
    exit 1
fi

echo "1. Current DNS configuration:"
cat /etc/resolv.conf
echo ""

echo "2. Testing DNS resolution..."
if nslookup raw.githubusercontent.com > /dev/null 2>&1; then
    echo "✓ DNS is working"
    exit 0
else
    echo "❌ DNS resolution failing"
fi
echo ""

echo "3. Backing up current resolv.conf..."
cp /etc/resolv.conf /etc/resolv.conf.backup-$(date +%Y%m%d-%H%M%S)
echo "✓ Backup created"
echo ""

echo "4. Adding Google DNS servers..."
cat > /etc/resolv.conf << 'DNSEOF'
# Google DNS (added by TAKNET-PS DNS fix)
nameserver 8.8.8.8
nameserver 8.8.4.4
DNSEOF
echo "✓ DNS servers added"
echo ""

echo "5. Testing DNS resolution again..."
if nslookup raw.githubusercontent.com > /dev/null 2>&1; then
    echo "✓ DNS is now working!"
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  DNS Fixed!"
    echo "  Update check should work now"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
else
    echo "⚠️  Still having DNS issues"
    echo ""
    echo "Try restarting network services:"
    echo "  sudo systemctl restart systemd-resolved"
    echo "  sudo systemctl restart networking"
fi
echo ""
