#!/bin/bash
# ADSBHub Fix Script for Raspberry Pi
# Run this directly on your Raspberry Pi to add ADSBHub support
# 
# Usage: sudo bash fix-adsbhub.sh

set -e

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  TAKNET-PS ADSBHub Fix Script"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "❌ ERROR: This script must be run as root"
    echo ""
    echo "Please run:"
    echo "  sudo bash fix-adsbhub.sh"
    echo ""
    exit 1
fi

# Check if docker-compose.yml exists
if [ ! -f /opt/adsb/config/docker-compose.yml ]; then
    echo "❌ ERROR: /opt/adsb/config/docker-compose.yml not found"
    echo ""
    echo "This means TAKNET-PS is not installed."
    echo "Please run the installer first."
    echo ""
    exit 1
fi

# Check if adsbhub already exists
if grep -q "^  adsbhub:" /opt/adsb/config/docker-compose.yml; then
    echo "✓ ADSBHub service already exists in docker-compose.yml"
    echo ""
    echo "If you're still getting 'no such service' errors, try:"
    echo "  cd /opt/adsb/config"
    echo "  sudo docker compose down"
    echo "  sudo docker compose up -d"
    echo ""
    exit 0
fi

echo "📋 Diagnostic Check:"
echo "  Current services in docker-compose.yml:"
grep "^  [a-z].*:" /opt/adsb/config/docker-compose.yml | sed 's/://g' | sed 's/^/    /'
echo ""
echo "  ❌ adsbhub is MISSING"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

read -p "Add ADSBHub service now? [Y/n]: " -n 1 -r
echo ""
if [[ ! $REPLY =~ ^[Yy]$ ]] && [[ ! -z $REPLY ]]; then
    echo "Cancelled."
    exit 0
fi

echo ""
echo "[1/5] Creating backup..."
BACKUP_FILE="/opt/adsb/config/docker-compose.yml.backup-$(date +%Y%m%d-%H%M%S)"
cp /opt/adsb/config/docker-compose.yml "$BACKUP_FILE"
echo "  ✓ Backup: $BACKUP_FILE"

echo ""
echo "[2/5] Adding ADSBHub service to docker-compose.yml..."
cat >> /opt/adsb/config/docker-compose.yml << 'EOF'

  adsbhub:
    image: ghcr.io/sdr-enthusiasts/docker-adsbhub:latest
    container_name: adsbhub
    hostname: adsbhub
    restart: unless-stopped
    networks:
      - adsb_net
    environment:
      - TZ=${FEEDER_TZ}
      - SBSHOST=ultrafeeder
      - CLIENTKEY=${ADSBHUB_STATION_KEY}
    depends_on:
      - ultrafeeder
EOF

if grep -q "^  adsbhub:" /opt/adsb/config/docker-compose.yml; then
    echo "  ✓ ADSBHub service added"
else
    echo "  ❌ Failed to add service"
    mv "$BACKUP_FILE" /opt/adsb/config/docker-compose.yml
    exit 1
fi

echo ""
echo "[3/5] Adding environment variables to .env..."
if [ -f /opt/adsb/config/.env ]; then
    # Add PIAWARE if missing
    if ! grep -q "PIAWARE_FEEDER_ID" /opt/adsb/config/.env; then
        cat >> /opt/adsb/config/.env << 'EOF'

# FlightAware / PiAware
PIAWARE_ENABLED=false
PIAWARE_FEEDER_ID=
EOF
        echo "  ✓ Added PIAWARE variables"
    else
        echo "  ✓ PIAWARE variables already exist"
    fi
    
    # Add ADSBHUB if missing
    if ! grep -q "ADSBHUB_STATION_KEY" /opt/adsb/config/.env; then
        cat >> /opt/adsb/config/.env << 'EOF'

# ADSBHub Configuration
ADSBHUB_ENABLED=false
ADSBHUB_STATION_KEY=
EOF
        echo "  ✓ Added ADSBHUB variables"
    else
        echo "  ✓ ADSBHUB variables already exist"
    fi
else
    echo "  ⚠️  WARNING: .env file not found"
fi

echo ""
echo "[4/5] Validating docker-compose.yml syntax..."
cd /opt/adsb/config
if docker compose config >/dev/null 2>&1; then
    echo "  ✓ YAML syntax is valid"
    echo ""
    echo "  Services detected:"
    docker compose config --services | sed 's/^/    /'
else
    echo "  ❌ YAML syntax error!"
    echo ""
    echo "  Restoring backup..."
    mv "$BACKUP_FILE" /opt/adsb/config/docker-compose.yml
    echo ""
    echo "  Error details:"
    docker compose config 2>&1 | head -20
    exit 1
fi

echo ""
echo "[5/5] Downloading ADSBHub Docker image..."
if docker pull ghcr.io/sdr-enthusiasts/docker-adsbexchange:latest; then
    echo "  ✓ Docker image downloaded"
else
    echo "  ⚠️  WARNING: Failed to download image"
    echo "  You can download it later manually"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  ✅ FIX COMPLETE!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Next steps:"
echo "  1. Open: http://taknet-ps.local"
echo "  2. Go to: Settings → Feed Selection → Account-Required Feeds"
echo "  3. Scroll to: ADSBHub section"
echo "  4. Enter your station key from adsbhub.org"
echo "  5. Click: 'Save & Enable ADSBHub'"
echo ""
echo "✨ ADSBHub should work now!"
echo ""
