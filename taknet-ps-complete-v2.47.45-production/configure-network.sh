#!/bin/bash
# TAKNET-PS Network Configuration
# Implements mDNS hostname and WiFi fallback hotspot

set -e

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  TAKNET-PS Network Configuration"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo "❌ This script must be run with sudo"
    exit 1
fi

# 1. Install Avahi for mDNS
echo "Installing mDNS support..."
apt-get update -qq
apt-get install -y avahi-daemon avahi-utils libnss-mdns

# Configure Avahi
cat > /etc/avahi/avahi-daemon.conf << 'EOF'
[server]
host-name=taknet-ps
domain-name=local
use-ipv4=yes
use-ipv6=no
enable-dbus=yes
allow-interfaces=wlan0,eth0

[publish]
publish-addresses=yes
publish-hinfo=yes
publish-workstation=yes
publish-domain=yes

[reflector]
enable-reflector=no
EOF

# Enable and start Avahi
systemctl enable avahi-daemon
systemctl restart avahi-daemon

echo "✓ mDNS configured - Device accessible at: taknet-ps.local"

# 2. Install Nginx for reverse proxy
echo "Installing Nginx reverse proxy..."
apt-get install -y nginx

# Configure Nginx
cat > /etc/nginx/sites-available/taknet-ps << 'EOF'
server {
    listen 80 default_server;
    listen [::]:80 default_server;
    server_name taknet-ps.local _;

    # Main web UI - redirect root to /web
    location = / {
        return 301 http://$host/web;
    }

    # Web UI at /web
    location /web/ {
        proxy_pass http://127.0.0.1:5000/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Map at /map
    location /map/ {
        proxy_pass http://127.0.0.1:8080/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
    }

    # FR24 interface at /fr24
    location /fr24/ {
        proxy_pass http://127.0.0.1:8754/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
    }

    # Static files with caching
    location ~* \.(css|js|jpg|jpeg|png|gif|ico|svg|woff|woff2|ttf|eot)$ {
        proxy_pass http://127.0.0.1:5000;
        expires 1d;
        add_header Cache-Control "public, immutable";
    }
}
EOF

# Remove default site and enable taknet-ps
rm -f /etc/nginx/sites-enabled/default
ln -sf /etc/nginx/sites-available/taknet-ps /etc/nginx/sites-enabled/

# Test and reload Nginx
nginx -t
systemctl enable nginx
systemctl restart nginx

echo "✓ Nginx configured:"
echo "  - http://taknet-ps.local/web → Web UI (port 5000)"
echo "  - http://taknet-ps.local/map → tar1090 Map (port 8080)"
echo "  - http://taknet-ps.local/fr24 → FlightRadar24 (port 8754)"

# 3. Install WiFi Hotspot Dependencies
echo "Installing WiFi hotspot components..."
apt-get install -y hostapd dnsmasq iptables-persistent

# Stop services for configuration
systemctl stop hostapd
systemctl stop dnsmasq

# Backup original configs
cp /etc/dnsmasq.conf /etc/dnsmasq.conf.backup 2>/dev/null || true
cp /etc/hostapd/hostapd.conf /etc/hostapd/hostapd.conf.backup 2>/dev/null || true

# 4. Create WiFi configuration files
echo "Creating WiFi hotspot configuration..."

# hostapd config
cat > /etc/hostapd/hostapd.conf << 'EOF'
interface=wlan0
driver=nl80211
ssid=TAKNET-PS
hw_mode=g
channel=7
wmm_enabled=0
macaddr_acl=0
auth_algs=1
ignore_broadcast_ssid=0
wpa=0
EOF

# Update hostapd daemon config
cat > /etc/default/hostapd << 'EOF'
DAEMON_CONF="/etc/hostapd/hostapd.conf"
EOF

# dnsmasq config for hotspot
cat > /etc/dnsmasq-hotspot.conf << 'EOF'
interface=wlan0
dhcp-range=192.168.4.2,192.168.4.20,255.255.255.0,24h
domain=taknet-ps.local
address=/#/192.168.4.1
EOF

echo "✓ WiFi hotspot configured - SSID: TAKNET-PS (no password)"

# 5. Create captive portal web service
echo "Creating captive portal service..."

# Create captive portal directory
mkdir -p /opt/adsb/captive-portal/{templates,static}

# Captive portal Python script
cat > /opt/adsb/captive-portal/portal.py << 'EOFPYTHON'
#!/usr/bin/env python3
"""
TAKNET-PS Captive Portal
WiFi configuration wizard
"""

from flask import Flask, render_template, request, jsonify
import subprocess
import json
import time
import os

app = Flask(__name__)

@app.route('/')
def index():
    """Captive portal landing page"""
    return render_template('portal.html')

@app.route('/api/scan', methods=['GET'])
def scan_networks():
    """Scan for available WiFi networks"""
    try:
        # Scan for networks
        result = subprocess.run(
            ['iwlist', 'wlan0', 'scan'],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        networks = []
        current_network = {}
        
        for line in result.stdout.split('\n'):
            line = line.strip()
            
            if 'ESSID:' in line:
                ssid = line.split('ESSID:')[1].strip('"')
                if ssid and ssid != '':
                    current_network['ssid'] = ssid
                    
            elif 'Quality=' in line:
                quality = line.split('Quality=')[1].split()[0]
                signal_level = int(quality.split('/')[0])
                current_network['signal'] = signal_level
                
            elif 'Encryption key:' in line:
                if 'on' in line:
                    current_network['secured'] = True
                else:
                    current_network['secured'] = False
                    
                # Network complete, add to list
                if 'ssid' in current_network:
                    networks.append(current_network.copy())
                    current_network = {}
        
        # Remove duplicates and sort by signal
        unique_networks = []
        seen_ssids = set()
        
        for network in networks:
            if network['ssid'] not in seen_ssids:
                seen_ssids.add(network['ssid'])
                unique_networks.append(network)
        
        unique_networks.sort(key=lambda x: x.get('signal', 0), reverse=True)
        
        return jsonify({'success': True, 'networks': unique_networks})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/connect', methods=['POST'])
def connect_network():
    """Configure and connect to WiFi network"""
    try:
        data = request.json
        ssid = data.get('ssid')
        password = data.get('password', '')
        
        if not ssid:
            return jsonify({'success': False, 'error': 'SSID required'}), 400
        
        # Create wpa_supplicant config
        config = f'''
country=US
ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev
update_config=1

network={{
    ssid="{ssid}"
'''
        
        if password:
            # Secured network
            config += f'    psk="{password}"\n'
        else:
            # Open network
            config += '    key_mgmt=NONE\n'
        
        config += '}\n'
        
        # Write config
        with open('/etc/wpa_supplicant/wpa_supplicant.conf', 'w') as f:
            f.write(config)
        
        # Trigger reboot via systemd
        # The network-check service will handle the reconnection
        subprocess.Popen(['systemctl', 'start', 'taknet-ps-reboot.service'])
        
        return jsonify({
            'success': True,
            'message': 'Configuration saved. Device will reboot in 5 seconds...'
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8888)
EOFPYTHON

chmod +x /opt/adsb/captive-portal/portal.py

# Captive portal HTML template
cat > /opt/adsb/captive-portal/templates/portal.html << 'EOFHTML'
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>TAKNET-PS WiFi Setup</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }
        
        .container {
            background: white;
            border-radius: 20px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            max-width: 500px;
            width: 100%;
            padding: 40px;
        }
        
        h1 {
            color: #333;
            margin-bottom: 10px;
            font-size: 28px;
        }
        
        .subtitle {
            color: #666;
            margin-bottom: 30px;
            font-size: 14px;
        }
        
        .scan-button {
            width: 100%;
            padding: 15px;
            background: #667eea;
            color: white;
            border: none;
            border-radius: 10px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            margin-bottom: 20px;
            transition: background 0.3s;
        }
        
        .scan-button:hover {
            background: #5568d3;
        }
        
        .scan-button:disabled {
            background: #ccc;
            cursor: not-allowed;
        }
        
        .network-list {
            max-height: 300px;
            overflow-y: auto;
            margin-bottom: 20px;
        }
        
        .network {
            padding: 15px;
            border: 2px solid #e0e0e0;
            border-radius: 10px;
            margin-bottom: 10px;
            cursor: pointer;
            transition: all 0.3s;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }
        
        .network:hover {
            border-color: #667eea;
            background: #f8f9ff;
        }
        
        .network.selected {
            border-color: #667eea;
            background: #f0f2ff;
        }
        
        .network-info {
            flex: 1;
        }
        
        .network-name {
            font-weight: 600;
            color: #333;
            margin-bottom: 5px;
        }
        
        .network-signal {
            font-size: 12px;
            color: #666;
        }
        
        .network-secure {
            font-size: 20px;
        }
        
        .password-section {
            margin-bottom: 20px;
        }
        
        label {
            display: block;
            margin-bottom: 8px;
            color: #333;
            font-weight: 600;
        }
        
        input[type="text"],
        input[type="password"] {
            width: 100%;
            padding: 12px;
            border: 2px solid #e0e0e0;
            border-radius: 10px;
            font-size: 16px;
            transition: border-color 0.3s;
        }
        
        input:focus {
            outline: none;
            border-color: #667eea;
        }
        
        .connect-button {
            width: 100%;
            padding: 15px;
            background: #10b981;
            color: white;
            border: none;
            border-radius: 10px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            transition: background 0.3s;
        }
        
        .connect-button:hover {
            background: #059669;
        }
        
        .connect-button:disabled {
            background: #ccc;
            cursor: not-allowed;
        }
        
        .status {
            margin-top: 20px;
            padding: 15px;
            border-radius: 10px;
            text-align: center;
            font-weight: 600;
        }
        
        .status.info {
            background: #dbeafe;
            color: #1e40af;
        }
        
        .status.success {
            background: #d1fae5;
            color: #065f46;
        }
        
        .status.error {
            background: #fee2e2;
            color: #991b1b;
        }
        
        .countdown {
            font-size: 48px;
            font-weight: bold;
            margin: 20px 0;
        }
        
        .hidden {
            display: none;
        }
        
        .manual-entry {
            margin-top: 20px;
            padding: 15px;
            background: #f9fafb;
            border-radius: 10px;
        }
        
        .manual-entry label {
            font-size: 14px;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🛩️ TAKNET-PS</h1>
        <p class="subtitle">WiFi Configuration Wizard</p>
        
        <button class="scan-button" onclick="scanNetworks()" id="scanBtn">
            🔍 Scan for Networks
        </button>
        
        <div id="networkList" class="network-list"></div>
        
        <div id="manualEntry" class="manual-entry hidden">
            <label>Or enter network manually:</label>
            <input type="text" id="manualSSID" placeholder="Network Name (SSID)">
        </div>
        
        <div id="passwordSection" class="password-section hidden">
            <label>WiFi Password:</label>
            <input type="password" id="password" placeholder="Enter password">
        </div>
        
        <button class="connect-button hidden" onclick="connectNetwork()" id="connectBtn">
            🔗 Connect to Network
        </button>
        
        <div id="status"></div>
    </div>
    
    <script>
        let selectedNetwork = null;
        
        async function scanNetworks() {
            const btn = document.getElementById('scanBtn');
            const networkList = document.getElementById('networkList');
            const status = document.getElementById('status');
            
            btn.disabled = true;
            btn.textContent = '🔍 Scanning...';
            networkList.innerHTML = '';
            status.innerHTML = '';
            
            try {
                const response = await fetch('/api/scan');
                const data = await response.json();
                
                if (data.success && data.networks.length > 0) {
                    data.networks.forEach(network => {
                        const div = document.createElement('div');
                        div.className = 'network';
                        div.onclick = () => selectNetwork(network);
                        
                        const signalBars = Math.min(Math.ceil(network.signal / 20), 5);
                        const signalIcon = '📶'.repeat(signalBars);
                        
                        div.innerHTML = `
                            <div class="network-info">
                                <div class="network-name">${network.ssid}</div>
                                <div class="network-signal">${signalIcon} Signal: ${network.signal}/100</div>
                            </div>
                            <div class="network-secure">${network.secured ? '🔒' : '🔓'}</div>
                        `;
                        
                        networkList.appendChild(div);
                    });
                    
                    document.getElementById('manualEntry').classList.remove('hidden');
                } else {
                    status.innerHTML = '<div class="status error">No networks found. Please try again.</div>';
                }
            } catch (error) {
                status.innerHTML = '<div class="status error">Scan failed: ' + error.message + '</div>';
            } finally {
                btn.disabled = false;
                btn.textContent = '🔍 Scan for Networks';
            }
        }
        
        function selectNetwork(network) {
            selectedNetwork = network;
            
            // Update UI
            document.querySelectorAll('.network').forEach(n => n.classList.remove('selected'));
            event.currentTarget.classList.add('selected');
            
            // Show password field if secured
            const passwordSection = document.getElementById('passwordSection');
            if (network.secured) {
                passwordSection.classList.remove('hidden');
            } else {
                passwordSection.classList.add('hidden');
            }
            
            // Show connect button
            document.getElementById('connectBtn').classList.remove('hidden');
            document.getElementById('status').innerHTML = '';
        }
        
        async function connectNetwork() {
            const connectBtn = document.getElementById('connectBtn');
            const status = document.getElementById('status');
            
            let ssid = selectedNetwork ? selectedNetwork.ssid : document.getElementById('manualSSID').value.trim();
            let password = document.getElementById('password').value;
            
            if (!ssid) {
                status.innerHTML = '<div class="status error">Please select or enter a network name</div>';
                return;
            }
            
            connectBtn.disabled = true;
            connectBtn.textContent = '⏳ Connecting...';
            
            try {
                const response = await fetch('/api/connect', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ssid, password})
                });
                
                const data = await response.json();
                
                if (data.success) {
                    status.innerHTML = `
                        <div class="status success">
                            <div>✓ Configuration Saved!</div>
                            <div style="margin: 20px 0;">The device will reboot and attempt to connect to:</div>
                            <div style="font-size: 18px; margin: 10px 0;"><strong>${ssid}</strong></div>
                            <div style="margin: 20px 0;">Rebooting in:</div>
                            <div class="countdown" id="countdown">5</div>
                            <div style="font-size: 14px; color: #666;">If connection fails, hotspot will restart automatically.</div>
                        </div>
                    `;
                    
                    // Hide form elements
                    document.querySelectorAll('.scan-button, .network-list, .password-section, .connect-button, .manual-entry').forEach(el => {
                        el.classList.add('hidden');
                    });
                    
                    // Countdown
                    let count = 5;
                    const countdownEl = document.getElementById('countdown');
                    const interval = setInterval(() => {
                        count--;
                        countdownEl.textContent = count;
                        if (count <= 0) {
                            clearInterval(interval);
                            countdownEl.textContent = '0';
                        }
                    }, 1000);
                } else {
                    status.innerHTML = '<div class="status error">Failed: ' + data.error + '</div>';
                    connectBtn.disabled = false;
                    connectBtn.textContent = '🔗 Connect to Network';
                }
            } catch (error) {
                status.innerHTML = '<div class="status error">Connection failed: ' + error.message + '</div>';
                connectBtn.disabled = false;
                connectBtn.textContent = '🔗 Connect to Network';
            }
        }
    </script>
</body>
</html>
EOFHTML

echo "✓ Captive portal created"

# 6. Create captive portal systemd service
cat > /etc/systemd/system/captive-portal.service << 'EOF'
[Unit]
Description=TAKNET-PS Captive Portal
After=network.target hostapd.service dnsmasq.service

[Service]
Type=simple
User=root
WorkingDirectory=/opt/adsb/captive-portal
ExecStart=/usr/bin/python3 /opt/adsb/captive-portal/portal.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

# 7. Create network check service
cat > /usr/local/bin/check-network.sh << 'EOFSCRIPT'
#!/bin/bash
# Check network connectivity and start hotspot if needed

HOTSPOT_ACTIVE=false

start_hotspot() {
    echo "$(date): Starting WiFi hotspot mode..."
    
    # Stop wpa_supplicant
    systemctl stop wpa_supplicant
    
    # Configure static IP for wlan0
    ip addr flush dev wlan0
    ip addr add 192.168.4.1/24 dev wlan0
    ip link set wlan0 up
    
    # Start dnsmasq
    dnsmasq -C /etc/dnsmasq-hotspot.conf
    
    # Start hostapd
    systemctl start hostapd
    
    # Enable IP forwarding and NAT (if eth0 exists)
    if ip link show eth0 &>/dev/null; then
        echo 1 > /proc/sys/net/ipv4/ip_forward
        iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE
        iptables -A FORWARD -i eth0 -o wlan0 -m state --state RELATED,ESTABLISHED -j ACCEPT
        iptables -A FORWARD -i wlan0 -o eth0 -j ACCEPT
    fi
    
    # Start captive portal
    systemctl start captive-portal
    
    # Redirect all HTTP traffic to captive portal
    iptables -t nat -A PREROUTING -i wlan0 -p tcp --dport 80 -j DNAT --to-destination 192.168.4.1:8888
    iptables -t nat -A PREROUTING -i wlan0 -p tcp --dport 443 -j DNAT --to-destination 192.168.4.1:8888
    
    HOTSPOT_ACTIVE=true
    echo "$(date): Hotspot active - SSID: TAKNET-PS"
}

stop_hotspot() {
    echo "$(date): Stopping hotspot mode..."
    
    # Stop services
    systemctl stop captive-portal
    systemctl stop hostapd
    killall dnsmasq 2>/dev/null
    
    # Flush iptables NAT rules
    iptables -t nat -F
    iptables -F FORWARD
    
    # Restart wpa_supplicant
    systemctl start wpa_supplicant
    
    HOTSPOT_ACTIVE=false
    echo "$(date): Hotspot stopped"
}

check_connectivity() {
    # Check if we can reach the internet
    if ping -c 1 -W 3 8.8.8.8 &>/dev/null || ping -c 1 -W 3 1.1.1.1 &>/dev/null; then
        return 0
    else
        return 1
    fi
}

# Main loop
echo "$(date): Network check started"

while true; do
    if check_connectivity; then
        if [ "$HOTSPOT_ACTIVE" = true ]; then
            echo "$(date): Network connected, stopping hotspot"
            stop_hotspot
        fi
        # Check every 30 seconds when connected
        sleep 30
    else
        if [ "$HOTSPOT_ACTIVE" = false ]; then
            echo "$(date): No network connectivity detected"
            # Wait 30 seconds before starting hotspot
            sleep 30
            # Check again
            if ! check_connectivity; then
                start_hotspot
            fi
        fi
        # Check every 10 seconds when in hotspot mode
        sleep 10
    fi
done
EOFSCRIPT

chmod +x /usr/local/bin/check-network.sh

# Network check systemd service
cat > /etc/systemd/system/network-check.service << 'EOF'
[Unit]
Description=TAKNET-PS Network Connectivity Monitor
After=network.target wpa_supplicant.service

[Service]
Type=simple
ExecStart=/usr/local/bin/check-network.sh
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# 8. Create reboot service
cat > /etc/systemd/system/taknet-ps-reboot.service << 'EOF'
[Unit]
Description=TAKNET-PS Reboot After WiFi Configuration

[Service]
Type=oneshot
ExecStartPre=/bin/sleep 5
ExecStart=/sbin/reboot
EOF

# Enable services
systemctl daemon-reload
systemctl enable network-check
systemctl start network-check

echo "✓ Network monitoring service enabled"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✓ Network configuration complete!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Access your device at:"
echo "  • http://taknet-ps.local/web"
echo "  • http://taknet-ps.local/map"
echo "  • http://taknet-ps.local/fr24"
echo ""
echo "WiFi Hotspot:"
echo "  • SSID: TAKNET-PS (no password)"
echo "  • Activates automatically if no network connection"
echo "  • Captive portal provides WiFi setup wizard"
echo ""
