#!/bin/bash
# Troubleshoot SSH access over Private Tailscale
# User can ping but SSH connection refused

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  SSH over Private Tailscale - Diagnostic Tool"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo "❌ This script must be run with sudo"
    exit 1
fi

# 1. Check Tailscale IPs
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "1. Tailscale IP Addresses"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Primary Tailscale
if command -v tailscale &> /dev/null; then
    PRIMARY_TS_IP=$(tailscale ip -4 2>/dev/null)
    if [ -n "$PRIMARY_TS_IP" ]; then
        echo "✓ Primary Tailscale IP: $PRIMARY_TS_IP"
    else
        echo "⚠️  Primary Tailscale: Not connected or not installed"
    fi
else
    echo "⚠️  Primary Tailscale: Not installed"
fi

# Private Tailscale
PRIVATE_TS_RUNNING=$(docker ps --filter "name=tailscale-private" --format "{{.Names}}" 2>/dev/null)
if [ -n "$PRIVATE_TS_RUNNING" ]; then
    PRIVATE_TS_IP=$(docker exec tailscale-private tailscale ip -4 2>/dev/null)
    if [ -n "$PRIVATE_TS_IP" ]; then
        echo "✓ Private Tailscale IP: $PRIVATE_TS_IP"
    else
        echo "⚠️  Private Tailscale container running but no IP assigned"
    fi
else
    echo "❌ Private Tailscale container is NOT running"
fi

echo ""

# 2. Check SSH Service
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "2. SSH Service Status"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

if systemctl is-active --quiet sshd; then
    echo "✓ SSH service is running"
else
    echo "❌ SSH service is NOT running"
    systemctl status sshd --no-pager | head -10
fi

echo ""

# 3. Check SSH Listening Ports
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "3. SSH Listening Configuration"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

echo "SSH is listening on:"
ss -tlnp | grep :22 || netstat -tlnp | grep :22
echo ""

# Check if SSH is listening on all interfaces or specific ones
LISTEN_ADDRESS=$(grep -i "^ListenAddress" /etc/ssh/sshd_config 2>/dev/null)
if [ -n "$LISTEN_ADDRESS" ]; then
    echo "⚠️  SSH ListenAddress is set:"
    echo "$LISTEN_ADDRESS"
    echo ""
    echo "   If SSH is bound to specific IPs, it may not listen on Tailscale interfaces."
    echo "   Consider removing ListenAddress or adding Tailscale IPs."
else
    echo "✓ No specific ListenAddress set (listening on all interfaces)"
fi

echo ""

# 4. Check SSH Configuration for TAKNET-PS Match Block
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "4. SSH Configuration - TAKNET-PS Match Block"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

if grep -q "Match User remote" /etc/ssh/sshd_config; then
    echo "✓ Found Match block for remote user:"
    echo ""
    grep -A 3 "Match User remote" /etc/ssh/sshd_config
    echo ""
    
    # Check if it's the wide subnet
    if grep -q "Match User remote Address 100.64.0.0/10" /etc/ssh/sshd_config; then
        echo "✓ Using wide Tailscale subnet (100.64.0.0/10) - CORRECT"
    elif grep -q "Match User remote Address 100.64.0.0/16" /etc/ssh/sshd_config; then
        echo "⚠️  Using narrow subnet (100.64.0.0/16) - MAY NOT WORK FOR PRIVATE TAILSCALE"
        echo "   Private Tailscale IPs may be in 100.120.x.x range"
        echo "   Run: sudo /opt/adsb/scripts/update-ssh-all-tailscale.sh"
    else
        echo "⚠️  Using custom subnet - verify it includes Private Tailscale IP"
    fi
else
    echo "❌ NO Match block found for remote user"
    echo "   Remote user SSH access is not configured!"
    echo "   Run: sudo /opt/adsb/scripts/update-ssh-all-tailscale.sh"
fi

echo ""

# 5. Check for DenyUsers
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "5. SSH Configuration - DenyUsers Check"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

if grep -q "^DenyUsers.*remote" /etc/ssh/sshd_config; then
    echo "❌ PROBLEM FOUND: DenyUsers is blocking remote user!"
    grep "^DenyUsers.*remote" /etc/ssh/sshd_config
    echo ""
    echo "   This blocks ALL SSH access for remote user."
    echo "   Run: sudo /opt/adsb/scripts/update-ssh-all-tailscale.sh"
else
    echo "✓ No DenyUsers rule blocking remote user"
fi

echo ""

# 6. Test SSH Config Syntax
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "6. SSH Configuration Syntax Test"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

if sshd -t 2>&1; then
    echo "✓ SSH configuration is valid"
else
    echo "❌ SSH configuration has ERRORS:"
    sshd -t
fi

echo ""

# 7. Check Firewall Rules
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "7. Firewall Configuration"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Check if ufw is active
if command -v ufw &> /dev/null; then
    if ufw status | grep -q "Status: active"; then
        echo "⚠️  UFW Firewall is ACTIVE"
        echo ""
        ufw status verbose | grep -E "22|SSH|ALLOW"
        echo ""
        echo "   Check if SSH is allowed from Tailscale subnet"
    else
        echo "✓ UFW is installed but inactive"
    fi
else
    echo "✓ UFW not installed"
fi

# Check if iptables has rules
IPTABLES_RULES=$(iptables -L INPUT -n | grep -c "dpt:22")
if [ "$IPTABLES_RULES" -gt 0 ]; then
    echo ""
    echo "⚠️  iptables rules found for port 22:"
    iptables -L INPUT -n -v | grep "dpt:22"
    echo ""
    echo "   Verify these rules allow Tailscale subnets"
else
    echo "✓ No iptables INPUT rules specifically for port 22"
fi

echo ""

# 8. Test SSH Access from Localhost
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "8. SSH Access Test from Localhost"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Test Primary Tailscale IP
if [ -n "$PRIMARY_TS_IP" ]; then
    echo "Testing SSH to Primary Tailscale IP ($PRIMARY_TS_IP)..."
    timeout 3 bash -c "echo | nc -w 1 $PRIMARY_TS_IP 22" 2>/dev/null
    if [ $? -eq 0 ]; then
        echo "✓ SSH port 22 is OPEN on Primary Tailscale IP"
    else
        echo "❌ SSH port 22 is CLOSED on Primary Tailscale IP"
    fi
    echo ""
fi

# Test Private Tailscale IP
if [ -n "$PRIVATE_TS_IP" ]; then
    echo "Testing SSH to Private Tailscale IP ($PRIVATE_TS_IP)..."
    timeout 3 bash -c "echo | nc -w 1 $PRIVATE_TS_IP 22" 2>/dev/null
    if [ $? -eq 0 ]; then
        echo "✓ SSH port 22 is OPEN on Private Tailscale IP"
    else
        echo "❌ SSH port 22 is CLOSED on Private Tailscale IP"
    fi
    echo ""
fi

# 9. Check remote user
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "9. Remote User Check"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

if id "remote" &>/dev/null; then
    echo "✓ User 'remote' exists"
    
    # Check if password is set
    if grep -q "^remote:" /etc/shadow; then
        echo "✓ Password is set for remote user"
    else
        echo "❌ No password set for remote user"
        echo "   Set password: sudo passwd remote"
    fi
else
    echo "❌ User 'remote' does not exist"
fi

echo ""

# 10. Summary and Recommendations
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "10. Summary and Recommendations"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Collect issues
ISSUES_FOUND=0

# Check Private Tailscale is running
if [ -z "$PRIVATE_TS_RUNNING" ]; then
    echo "❌ ISSUE: Private Tailscale container is not running"
    echo "   Fix: Enable Private Tailscale in Settings"
    ISSUES_FOUND=$((ISSUES_FOUND + 1))
    echo ""
fi

# Check Match block exists
if ! grep -q "Match User remote" /etc/ssh/sshd_config; then
    echo "❌ ISSUE: No SSH Match block for remote user"
    echo "   Fix: sudo /opt/adsb/scripts/update-ssh-all-tailscale.sh"
    ISSUES_FOUND=$((ISSUES_FOUND + 1))
    echo ""
fi

# Check for DenyUsers
if grep -q "^DenyUsers.*remote" /etc/ssh/sshd_config; then
    echo "❌ ISSUE: DenyUsers is blocking remote user"
    echo "   Fix: sudo /opt/adsb/scripts/update-ssh-all-tailscale.sh"
    ISSUES_FOUND=$((ISSUES_FOUND + 1))
    echo ""
fi

# Check for narrow subnet
if grep -q "Match User remote Address 100.64.0.0/16" /etc/ssh/sshd_config; then
    if [ -n "$PRIVATE_TS_IP" ]; then
        # Check if Private TS IP is outside the /16 range
        FIRST_TWO=$(echo "$PRIVATE_TS_IP" | cut -d'.' -f1-2)
        if [ "$FIRST_TWO" != "100.64" ]; then
            echo "❌ ISSUE: SSH configured for 100.64.0.0/16 but Private Tailscale is $PRIVATE_TS_IP"
            echo "   Fix: sudo /opt/adsb/scripts/update-ssh-all-tailscale.sh"
            ISSUES_FOUND=$((ISSUES_FOUND + 1))
            echo ""
        fi
    fi
fi

# Check SSH config syntax
if ! sshd -t 2>&1 > /dev/null; then
    echo "❌ ISSUE: SSH configuration has syntax errors"
    echo "   Fix: Check errors above and fix /etc/ssh/sshd_config"
    ISSUES_FOUND=$((ISSUES_FOUND + 1))
    echo ""
fi

if [ $ISSUES_FOUND -eq 0 ]; then
    echo "✅ No obvious issues found with SSH configuration"
    echo ""
    echo "If SSH still doesn't work, try:"
    echo "1. Restart SSH service: sudo systemctl restart sshd"
    echo "2. Check SSH logs: sudo journalctl -u sshd -n 50"
    echo "3. Test with verbose: ssh -vvv remote@$PRIVATE_TS_IP"
else
    echo "Found $ISSUES_FOUND issue(s) - see fixes above"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Diagnostic Complete"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
