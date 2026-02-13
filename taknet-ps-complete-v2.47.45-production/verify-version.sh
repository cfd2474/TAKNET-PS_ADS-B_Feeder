#!/bin/bash
# Version Update Verification Script
# Tests that version comparison works correctly

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  TAKNET-PS Version System Test"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

ERRORS=0

# Check 1: VERSION file exists
echo "1. Checking VERSION file..."
if [ -f "VERSION" ]; then
    VERSION_CONTENT=$(cat VERSION)
    echo -e "   ${GREEN}✓${NC} VERSION file exists: ${VERSION_CONTENT}"
else
    echo -e "   ${RED}✗${NC} VERSION file missing!"
    ERRORS=$((ERRORS + 1))
fi

# Check 2: version.json exists
echo ""
echo "2. Checking version.json..."
if [ -f "version.json" ]; then
    echo -e "   ${GREEN}✓${NC} version.json exists"
    
    # Parse version from JSON
    JSON_VERSION=$(grep '"version"' version.json | sed 's/.*"version": "\(.*\)".*/\1/')
    echo "   JSON version: ${JSON_VERSION}"
    
    # Compare with VERSION file
    if [ "$VERSION_CONTENT" = "$JSON_VERSION" ]; then
        echo -e "   ${GREEN}✓${NC} Versions match!"
    else
        echo -e "   ${RED}✗${NC} Version mismatch: VERSION=${VERSION_CONTENT}, JSON=${JSON_VERSION}"
        ERRORS=$((ERRORS + 1))
    fi
else
    echo -e "   ${RED}✗${NC} version.json missing!"
    ERRORS=$((ERRORS + 1))
fi

# Check 3: install.sh has correct version
echo ""
echo "3. Checking install.sh..."
if [ -f "install/install.sh" ]; then
    INSTALL_VERSIONS=$(grep -o "[0-9]\+\.[0-9]\+\.[0-9]\+" install/install.sh | head -5)
    INSTALL_VERSION_COUNT=$(echo "$INSTALL_VERSIONS" | sort -u | wc -l)
    
    if [ "$INSTALL_VERSION_COUNT" -eq 1 ]; then
        INSTALL_VERSION=$(echo "$INSTALL_VERSIONS" | head -1)
        echo -e "   ${GREEN}✓${NC} install.sh has consistent version: ${INSTALL_VERSION}"
        
        if [ "$INSTALL_VERSION" = "$VERSION_CONTENT" ]; then
            echo -e "   ${GREEN}✓${NC} Matches VERSION file!"
        else
            echo -e "   ${YELLOW}⚠${NC} Version mismatch: install.sh=${INSTALL_VERSION}, VERSION=${VERSION_CONTENT}"
        fi
    else
        echo -e "   ${YELLOW}⚠${NC} Multiple versions found in install.sh:"
        echo "$INSTALL_VERSIONS" | sort -u
    fi
else
    echo -e "   ${RED}✗${NC} install/install.sh missing!"
    ERRORS=$((ERRORS + 1))
fi

# Check 4: Version format validation
echo ""
echo "4. Validating version format..."
if [[ "$VERSION_CONTENT" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    echo -e "   ${GREEN}✓${NC} Version format valid: ${VERSION_CONTENT}"
else
    echo -e "   ${RED}✗${NC} Invalid version format: ${VERSION_CONTENT} (should be X.Y.Z)"
    ERRORS=$((ERRORS + 1))
fi

# Check 5: Test version comparison
echo ""
echo "5. Testing version comparison..."

test_version_compare() {
    local current=$1
    local latest=$2
    local expected=$3
    
    # Parse versions
    IFS='.' read -ra CURRENT <<< "$current"
    IFS='.' read -ra LATEST <<< "$latest"
    
    # Compare
    result="equal"
    for i in 0 1 2; do
        curr_part=${CURRENT[$i]:-0}
        lat_part=${LATEST[$i]:-0}
        
        if [ $lat_part -gt $curr_part ]; then
            result="newer"
            break
        elif [ $lat_part -lt $curr_part ]; then
            result="older"
            break
        fi
    done
    
    if [ "$result" = "$expected" ]; then
        echo -e "   ${GREEN}✓${NC} ${current} vs ${latest} = ${result} (expected ${expected})"
    else
        echo -e "   ${RED}✗${NC} ${current} vs ${latest} = ${result} (expected ${expected})"
        ERRORS=$((ERRORS + 1))
    fi
}

# Test cases
test_version_compare "2.47.3" "2.47.4" "newer"
test_version_compare "2.47.3" "2.48.0" "newer"
test_version_compare "2.47.3" "3.0.0" "newer"
test_version_compare "2.47.3" "2.47.3" "equal"
test_version_compare "2.47.4" "2.47.3" "older"
test_version_compare "2.47.10" "2.47.9" "older"

# Summary
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if [ $ERRORS -eq 0 ]; then
    echo -e "${GREEN}✓ All checks passed!${NC}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo "Ready to deploy version: ${VERSION_CONTENT}"
    echo ""
    exit 0
else
    echo -e "${RED}✗ ${ERRORS} error(s) found!${NC}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo "Please fix errors before deploying."
    echo ""
    exit 1
fi
