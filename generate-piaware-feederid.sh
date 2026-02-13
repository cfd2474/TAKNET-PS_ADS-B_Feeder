#!/bin/bash
# Manual FlightAware Feeder ID Generator
# Use this if the web interface times out

set -e

echo "=========================================="
echo "FLIGHTAWARE FEEDER ID GENERATOR"
echo "=========================================="
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "⚠️  Not running as root, attempting without sudo..."
fi

echo "1. Reading your coordinates from .env..."
echo "------------------------------------------"

if [ ! -f /opt/adsb/.env ]; then
    echo "❌ ERROR: /opt/adsb/.env not found!"
    echo ""
    echo "Please enter your coordinates manually:"
    read -p "Latitude: " LAT
    read -p "Longitude: " LONG
else
    source /opt/adsb/.env
    LAT="${FEEDER_LAT}"
    LONG="${FEEDER_LONG}"
    echo "✓ Using coordinates from .env:"
    echo "  Latitude:  $LAT"
    echo "  Longitude: $LONG"
fi

echo ""
echo "2. Pulling latest PiAware container image..."
echo "------------------------------------------"
docker pull ghcr.io/sdr-enthusiasts/docker-piaware:latest

echo ""
echo "3. Generating Feeder ID (this takes 60-90 seconds)..."
echo "------------------------------------------"
echo "Please wait while PiAware contacts FlightAware servers..."
echo ""

# Run container and capture output
OUTPUT=$(timeout 120 docker run --rm \
    -e LAT="$LAT" \
    -e LONG="$LONG" \
    -e RECEIVER_TYPE=none \
    ghcr.io/sdr-enthusiasts/docker-piaware:latest 2>&1 || true)

echo "$OUTPUT" > /tmp/piaware-generation.log

# Extract Feeder ID from output
FEEDER_ID=$(echo "$OUTPUT" | grep -i "my feeder ID is" | grep -oE '[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}' | head -1)

if [ -n "$FEEDER_ID" ]; then
    echo ""
    echo "=========================================="
    echo "✅ SUCCESS!"
    echo "=========================================="
    echo ""
    echo "Your new FlightAware Feeder ID is:"
    echo ""
    echo "    $FEEDER_ID"
    echo ""
    echo "=========================================="
    echo ""
    echo "NEXT STEPS:"
    echo "1. Copy the Feeder ID above"
    echo "2. Go to TAKNET-PS web interface: http://$(hostname -I | awk '{print $1}'):5000/feeds"
    echo "3. Paste the Feeder ID in the FlightAware field"
    echo "4. Click 'Save and Enable FlightAware'"
    echo ""
    echo "OR claim it at FlightAware:"
    echo "https://flightaware.com/adsb/piaware/claim/$FEEDER_ID"
    echo ""
    
    # Offer to save it
    echo ""
    read -p "Would you like to automatically save this to .env? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        if [ -f /opt/adsb/.env ]; then
            # Update or add PIAWARE_FEEDER_ID
            if grep -q "^PIAWARE_FEEDER_ID=" /opt/adsb/.env; then
                sed -i "s|^PIAWARE_FEEDER_ID=.*|PIAWARE_FEEDER_ID=$FEEDER_ID|" /opt/adsb/.env
                echo "✓ Updated PIAWARE_FEEDER_ID in .env"
            else
                echo "PIAWARE_FEEDER_ID=$FEEDER_ID" >> /opt/adsb/.env
                echo "✓ Added PIAWARE_FEEDER_ID to .env"
            fi
            
            # Enable PiAware
            if grep -q "^PIAWARE_ENABLED=" /opt/adsb/.env; then
                sed -i "s|^PIAWARE_ENABLED=.*|PIAWARE_ENABLED=true|" /opt/adsb/.env
            else
                echo "PIAWARE_ENABLED=true" >> /opt/adsb/.env
            fi
            
            echo ""
            echo "Restarting web interface..."
            systemctl restart taknet-ps-web 2>/dev/null || service taknet-ps-web restart 2>/dev/null || echo "⚠️  Please restart web manually: sudo systemctl restart taknet-ps-web"
            
            echo ""
            echo "✅ FlightAware configured!"
            echo "   Visit web interface to complete setup and deploy PiAware container."
        fi
    fi
    
else
    echo ""
    echo "=========================================="
    echo "❌ FAILED TO GENERATE FEEDER ID"
    echo "=========================================="
    echo ""
    echo "The PiAware container didn't return a Feeder ID."
    echo ""
    echo "Possible causes:"
    echo "1. Network connectivity issues to FlightAware servers"
    echo "2. Firewall blocking outbound connections"
    echo "3. FlightAware servers are experiencing issues"
    echo ""
    echo "Debugging information saved to: /tmp/piaware-generation.log"
    echo ""
    echo "To check what happened:"
    echo "  cat /tmp/piaware-generation.log | grep -i 'error\|feeder\|timeout'"
    echo ""
    echo "ALTERNATIVE METHOD:"
    echo "Get a Feeder ID manually from FlightAware:"
    echo "  1. Create account: https://flightaware.com"
    echo "  2. Claim feeder: https://flightaware.com/adsb/piaware/claim"
    echo "  3. Enter coordinates: Lat $LAT, Lon $LONG"
    echo "  4. Copy the Feeder ID they give you"
    echo "  5. Enter it in TAKNET-PS web interface"
    echo ""
    
    # Show relevant log excerpts
    echo "Recent log entries:"
    echo "$OUTPUT" | tail -20
fi

echo ""
echo "=========================================="
echo "Script complete!"
echo "=========================================="
