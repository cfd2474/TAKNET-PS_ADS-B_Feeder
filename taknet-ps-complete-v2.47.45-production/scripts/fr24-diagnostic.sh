#!/bin/bash
#
# FR24 Diagnostic Script
# Checks FR24 feeding status and identifies issues
#

echo "=========================================="
echo "FR24 Diagnostic Report"
echo "=========================================="
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

check_pass() {
    echo -e "${GREEN}✓${NC} $1"
}

check_fail() {
    echo -e "${RED}✗${NC} $1"
}

check_warn() {
    echo -e "${YELLOW}⚠${NC} $1"
}

# Check 1: FR24 container running
echo "1. Checking FR24 container status..."
if docker ps | grep -q "fr24"; then
    check_pass "FR24 container is running"
    UPTIME=$(docker ps --format "{{.Status}}" --filter "name=fr24")
    echo "   Uptime: $UPTIME"
else
    check_fail "FR24 container is NOT running"
    if docker ps -a | grep -q "fr24"; then
        echo "   Container exists but is stopped"
        echo "   Start it with: docker compose -f /opt/adsb/config/docker-compose.yml up -d fr24"
    else
        echo "   Container doesn't exist"
        echo "   Run: sudo /opt/adsb/scripts/config_builder.py"
    fi
fi
echo ""

# Check 2: FR24_KEY configured
echo "2. Checking FR24 sharing key..."
if grep -q "^FR24_KEY=." /opt/adsb/config/.env 2>/dev/null; then
    KEY=$(grep "^FR24_KEY=" /opt/adsb/config/.env | cut -d'=' -f2)
    if [ -n "$KEY" ] && [ "$KEY" != "your_key_here" ]; then
        check_pass "FR24_KEY is configured"
        echo "   Key: ${KEY:0:10}...${KEY: -4}"
    else
        check_fail "FR24_KEY is empty or placeholder"
        echo "   Set your key in the web interface"
    fi
else
    check_fail "FR24_KEY not found in .env"
    echo "   Add it via web interface"
fi
echo ""

# Check 3: Ultrafeeder running and receiving data
echo "3. Checking ultrafeeder status..."
if docker ps | grep -q "ultrafeeder"; then
    check_pass "Ultrafeeder container is running"
    
    # Check aircraft count
    AIRCRAFT_COUNT=$(curl -s http://localhost:8080/data/aircraft.json 2>/dev/null | jq '.aircraft | length' 2>/dev/null)
    if [ "$AIRCRAFT_COUNT" -gt 0 ] 2>/dev/null; then
        check_pass "Ultrafeeder is receiving aircraft data"
        echo "   Currently tracking: $AIRCRAFT_COUNT aircraft"
    else
        check_fail "Ultrafeeder is NOT receiving aircraft data"
        echo "   Check SDR connection: lsusb | grep RTL"
        echo "   Check ultrafeeder logs: docker logs ultrafeeder --tail 50"
    fi
else
    check_fail "Ultrafeeder container is NOT running"
    echo "   Start it with: docker compose -f /opt/adsb/config/docker-compose.yml up -d"
fi
echo ""

# Check 4: Network connectivity between containers
echo "4. Checking container network connectivity..."
if docker ps | grep -q "fr24"; then
    if docker exec fr24 ping -c 2 ultrafeeder >/dev/null 2>&1; then
        check_pass "FR24 can reach ultrafeeder"
    else
        check_fail "FR24 CANNOT reach ultrafeeder"
        echo "   Network issue - restart containers:"
        echo "   docker compose -f /opt/adsb/config/docker-compose.yml restart"
    fi
else
    check_warn "FR24 container not running - skipping network test"
fi
echo ""

# Check 5: FR24 container logs (recent errors)
echo "5. Checking FR24 logs for errors..."
if docker ps | grep -q "fr24"; then
    ERRORS=$(docker logs fr24 --tail 50 2>&1 | grep -i "error\|fail\|invalid\|refused" | tail -5)
    if [ -z "$ERRORS" ]; then
        check_pass "No recent errors in FR24 logs"
    else
        check_warn "Found errors in FR24 logs:"
        echo "$ERRORS" | while read line; do
            echo "   $line"
        done
    fi
    
    # Check for success indicators
    SUCCESS=$(docker logs fr24 --tail 50 2>&1 | grep -i "feeding started\|connected to\|receiving data" | tail -3)
    if [ -n "$SUCCESS" ]; then
        echo ""
        check_pass "FR24 feeding activity detected:"
        echo "$SUCCESS" | while read line; do
            echo "   $line"
        done
    fi
else
    check_warn "FR24 container not running - no logs to check"
fi
echo ""

# Check 6: MLAT configuration
echo "6. Checking MLAT configuration..."
if docker ps | grep -q "fr24"; then
    MLAT_SETTING=$(docker inspect fr24 --format '{{range .Config.Env}}{{println .}}{{end}}' | grep MLAT)
    if echo "$MLAT_SETTING" | grep -q "MLAT=yes"; then
        check_pass "MLAT is enabled"
    else
        check_warn "MLAT is disabled"
        echo "   Enable it by updating docker-compose.yml"
        echo "   Change: MLAT=no → MLAT=yes"
    fi
else
    check_warn "FR24 container not running - can't check MLAT"
fi
echo ""

# Summary
echo "=========================================="
echo "Summary & Recommendations"
echo "=========================================="
echo ""

ALL_GOOD=true

# Check if FR24 is running
if ! docker ps | grep -q "fr24"; then
    ALL_GOOD=false
    echo "1. START FR24 CONTAINER:"
    echo "   docker compose -f /opt/adsb/config/docker-compose.yml up -d fr24"
    echo ""
fi

# Check if key is set
if ! grep -q "^FR24_KEY=." /opt/adsb/config/.env 2>/dev/null; then
    ALL_GOOD=false
    echo "2. SET FR24 SHARING KEY:"
    echo "   - Go to web interface"
    echo "   - Navigate to: Feeds → Account-Required Feeds"
    echo "   - Enter your FR24 sharing key"
    echo "   - Click 'Save & Enable FR24'"
    echo ""
fi

# Check if ultrafeeder is receiving
AIRCRAFT_COUNT=$(curl -s http://localhost:8080/data/aircraft.json 2>/dev/null | jq '.aircraft | length' 2>/dev/null)
if [ "$AIRCRAFT_COUNT" = "0" ] 2>/dev/null || [ -z "$AIRCRAFT_COUNT" ]; then
    ALL_GOOD=false
    echo "3. ULTRAFEEDER NOT RECEIVING DATA:"
    echo "   - Check SDR is connected: lsusb | grep RTL"
    echo "   - Check ultrafeeder logs: docker logs ultrafeeder --tail 50"
    echo "   - Restart ultrafeeder: docker restart ultrafeeder"
    echo ""
fi

if [ "$ALL_GOOD" = true ]; then
    echo -e "${GREEN}All checks passed!${NC}"
    echo ""
    echo "If FR24 status still shows '.', wait 2-5 minutes for data to flow."
    echo "FR24 needs time to authenticate and establish the feed."
    echo ""
    echo "To monitor FR24 live:"
    echo "  docker logs -f fr24"
else
    echo "Fix the issues above, then run this script again."
fi

echo ""
echo "=========================================="
echo "Additional Commands"
echo "=========================================="
echo ""
echo "View FR24 logs (live):"
echo "  docker logs -f fr24"
echo ""
echo "View ultrafeeder logs:"
echo "  docker logs ultrafeeder --tail 50"
echo ""
echo "Restart FR24:"
echo "  docker restart fr24"
echo ""
echo "Restart all containers:"
echo "  docker compose -f /opt/adsb/config/docker-compose.yml restart"
echo ""
echo "Check FR24 web interface:"
echo "  http://localhost:8754"
echo ""
