#!/bin/bash
# Fix Private Tailscale TUN device conflicts
# Run this if Private Tailscale container fails to start with "device or resource busy"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Private Tailscale TUN Device Fix"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo "❌ This script must be run with sudo"
    exit 1
fi

echo "1. Checking what's using /dev/net/tun..."
echo ""
PROCESSES=$(lsof -n /dev/net/tun 2>/dev/null)
if [ -n "$PROCESSES" ]; then
    echo "$PROCESSES"
    echo ""
else
    echo "✓ No processes using /dev/net/tun"
    echo ""
fi

echo "2. Stopping Private Tailscale container..."
cd /opt/adsb/config
docker compose --profile private-tailscale stop tailscale-private 2>/dev/null || true
docker compose --profile private-tailscale kill tailscale-private 2>/dev/null || true
docker compose --profile private-tailscale rm -f tailscale-private 2>/dev/null || true
echo "✓ Container stopped and removed"
echo ""

echo "3. Checking if TUN device is still busy..."
sleep 2
PROCESSES=$(lsof -n /dev/net/tun 2>/dev/null | grep -v COMMAND)
if [ -n "$PROCESSES" ]; then
    echo "⚠️  Still processes using /dev/net/tun:"
    echo "$PROCESSES"
    echo ""
    
    # Show PIDs
    PIDS=$(echo "$PROCESSES" | awk '{print $2}' | sort -u)
    echo "PIDs using device: $PIDS"
    echo ""
    
    read -p "Kill these processes? (y/n) " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        for PID in $PIDS; do
            echo "Killing PID $PID..."
            kill -9 $PID 2>/dev/null || true
        done
        echo "✓ Processes killed"
        sleep 2
    fi
else
    echo "✓ TUN device is free"
fi
echo ""

echo "4. Rebuilding docker-compose configuration..."
python3 /opt/adsb/scripts/config_builder.py
echo "✓ Configuration rebuilt"
echo ""

echo "5. Starting Private Tailscale with fresh config..."
docker compose --profile private-tailscale up -d tailscale-private
echo ""

echo "6. Waiting for container to start..."
sleep 5

# Check if container is running
if docker ps --format '{{.Names}}' | grep -q "^tailscale-private$"; then
    echo "✓ Container is running"
    echo ""
    
    # Check logs for errors
    echo "7. Checking logs for errors..."
    LOGS=$(docker logs tailscale-private 2>&1 | tail -10)
    if echo "$LOGS" | grep -q "device or resource busy"; then
        echo "❌ Still seeing device conflict in logs"
        echo ""
        echo "$LOGS"
        echo ""
        echo "Please check:"
        echo "  - Primary Tailscale might be using tailscale0"
        echo "  - Old processes might still be holding /dev/net/tun"
        echo "  - Run: sudo lsof -n /dev/net/tun"
    else
        echo "✓ No device conflicts in logs"
        echo ""
        
        # Check for ts-private interface
        if ip addr show | grep -q "ts-private"; then
            TS_IP=$(ip addr show ts-private | grep "inet " | awk '{print $2}' | cut -d'/' -f1)
            echo "✓ ts-private interface created: $TS_IP"
            echo ""
            echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            echo "  ✓ Private Tailscale Fixed!"
            echo "  SSH should now work: ssh remote@$TS_IP"
            echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        else
            echo "⚠️  ts-private interface not found"
            echo "   Container is running but interface not created yet"
            echo "   Wait 10 seconds and check: ip addr show | grep ts-private"
        fi
    fi
else
    echo "❌ Container failed to start"
    echo ""
    echo "Check logs: docker logs tailscale-private"
fi

echo ""
