#!/usr/bin/env python3
"""
ADS-B Feeder Web Configuration Interface
Standalone version for separate testing and development

Optimized for Raspberry Pi 3B with minimal resource usage:
- Lightweight Flask backend
- Simple HTML/CSS/JS frontend (no build step)
- JSON file-based configuration
- Systemd service integration

Port: 8080 (configurable)
Access: http://TAILSCALE_IP:8080 or http://localhost:8080

Author: Mike (cfd2474)
Version: 0.1.0-alpha
"""

from flask import Flask, render_template_string, request, jsonify, send_from_directory
import json
import subprocess
import os
import re
from datetime import datetime

app = Flask(__name__)

# ============================================================================
# CONFIGURATION
# ============================================================================

INSTALL_DIR = "/opt/TAK_ADSB"
CONFIG_FILE = f"{INSTALL_DIR}/config/outputs.json"
READSB_SERVICE = "/etc/systemd/system/readsb.service"
MLAT_SERVICE_PREFIX = "/etc/systemd/system/mlat-client"

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def load_config():
    """Load configuration from JSON file"""
    if not os.path.exists(CONFIG_FILE):
        return {
            "version": "1.0",
            "feeder_info": {},
            "outputs": [],
            "mlat_clients": []
        }
    
    try:
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading config: {e}")
        return {"version": "1.0", "outputs": [], "mlat_clients": []}

def save_config(config):
    """Save configuration to JSON file"""
    try:
        os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=2)
        return True
    except Exception as e:
        print(f"Error saving config: {e}")
        return False

def get_service_status(service_name):
    """Check if a systemd service is active"""
    try:
        result = subprocess.run(
            ['systemctl', 'is-active', service_name],
            capture_output=True,
            text=True,
            timeout=5
        )
        return result.stdout.strip() == 'active'
    except:
        return False

def parse_readsb_service():
    """Parse current readsb service to extract connectors"""
    connectors = []
    try:
        with open(READSB_SERVICE, 'r') as f:
            content = f.read()
            # Find --net-connector arguments
            pattern = r'--net-connector\s+([^,]+),(\d+),(\w+)'
            matches = re.findall(pattern, content)
            for host, port, conn_type in matches:
                connectors.append({
                    'host': host.strip(),
                    'port': int(port),
                    'type': conn_type.strip()
                })
    except Exception as e:
        print(f"Error parsing readsb service: {e}")
    
    return connectors

def generate_readsb_service(config):
    """Generate readsb systemd service from configuration"""
    feeder = config.get('feeder_info', {})
    outputs = [o for o in config.get('outputs', []) if o.get('enabled', False)]
    
    # Build connector strings
    connectors = []
    for output in outputs:
        if output.get('type') == 'beast':
            connectors.append(
                f"--net-connector {output['host']},{output['port']},beast_out"
            )
    
    # Read template or build from scratch
    lat = feeder.get('latitude', 0)
    lon = feeder.get('longitude', 0)
    
    service_content = f"""[Unit]
Description=readsb ADS-B decoder with multiple outputs
Wants=network.target tailscaled.service
After=network.target tailscaled.service

[Service]
User=readsb
Type=simple
Restart=always
RestartSec=30
ExecStart={INSTALL_DIR}/bin/readsb \\
    --device-type rtlsdr \\
    --gain -10 \\
    --ppm 0 \\
    --net \\
    --lat {lat} \\
    --lon {lon} \\
    --max-range 360 \\
    {' '.join(connectors)} \\
    --net-bo-port 30005 \\
    --write-json /run/readsb \\
    --write-json-every 1 \\
    --stats-every 3600
SyslogIdentifier=readsb
Nice=-5

[Install]
WantedBy=default.target
"""
    
    return service_content

def apply_configuration():
    """Apply configuration by regenerating and restarting services"""
    try:
        config = load_config()
        
        # Generate new readsb service
        service_content = generate_readsb_service(config)
        
        # Write service file (requires sudo)
        with open('/tmp/readsb.service.new', 'w') as f:
            f.write(service_content)
        
        # Copy to systemd directory
        subprocess.run(
            ['sudo', 'cp', '/tmp/readsb.service.new', READSB_SERVICE],
            check=True
        )
        
        # Reload systemd
        subprocess.run(['sudo', 'systemctl', 'daemon-reload'], check=True)
        
        # Restart readsb
        subprocess.run(['sudo', 'systemctl', 'restart', 'readsb'], check=True)
        
        return True, "Configuration applied successfully"
    except Exception as e:
        return False, f"Error applying configuration: {str(e)}"

# ============================================================================
# HTML TEMPLATE (Optimized for Pi 3B - minimal JavaScript)
# ============================================================================

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ADS-B Feeder Configuration</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;
            background: #f5f7fa;
            color: #2c3e50;
            line-height: 1.6;
        }
        
        .container {
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
        }
        
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            border-radius: 10px;
            margin-bottom: 30px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }
        
        .header h1 {
            font-size: 28px;
            margin-bottom: 10px;
        }
        
        .header p {
            opacity: 0.9;
            font-size: 14px;
        }
        
        .status-bar {
            background: white;
            padding: 20px;
            border-radius: 10px;
            margin-bottom: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 15px;
        }
        
        .status-item {
            display: flex;
            align-items: center;
            gap: 10px;
        }
        
        .status-indicator {
            width: 12px;
            height: 12px;
            border-radius: 50%;
            animation: pulse 2s infinite;
        }
        
        .status-indicator.active {
            background: #2ecc71;
        }
        
        .status-indicator.inactive {
            background: #e74c3c;
        }
        
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }
        
        .section {
            background: white;
            padding: 25px;
            border-radius: 10px;
            margin-bottom: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        
        .section-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
            padding-bottom: 15px;
            border-bottom: 2px solid #f0f0f0;
        }
        
        .section-title {
            font-size: 20px;
            font-weight: 600;
            color: #2c3e50;
        }
        
        .output-card {
            border: 2px solid #e0e0e0;
            border-radius: 8px;
            padding: 20px;
            margin-bottom: 15px;
            transition: all 0.3s ease;
        }
        
        .output-card:hover {
            border-color: #667eea;
            box-shadow: 0 4px 8px rgba(102, 126, 234, 0.1);
        }
        
        .output-card.primary {
            border-left: 4px solid #667eea;
            background: #f8f9ff;
        }
        
        .output-card.disabled {
            opacity: 0.6;
            background: #f9f9f9;
        }
        
        .output-header {
            display: flex;
            justify-content: space-between;
            align-items: start;
            margin-bottom: 15px;
        }
        
        .output-title {
            font-size: 18px;
            font-weight: 600;
            color: #2c3e50;
        }
        
        .badge {
            display: inline-block;
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 12px;
            font-weight: 600;
            text-transform: uppercase;
        }
        
        .badge.primary {
            background: #667eea;
            color: white;
        }
        
        .badge.enabled {
            background: #2ecc71;
            color: white;
        }
        
        .badge.disabled {
            background: #95a5a6;
            color: white;
        }
        
        .output-details {
            margin: 15px 0;
            font-size: 14px;
            color: #666;
        }
        
        .output-details div {
            margin: 5px 0;
        }
        
        .output-details strong {
            color: #2c3e50;
            display: inline-block;
            width: 100px;
        }
        
        .button-group {
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
        }
        
        button {
            background: #667eea;
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 6px;
            font-size: 14px;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.3s ease;
            display: inline-flex;
            align-items: center;
            gap: 8px;
        }
        
        button:hover {
            background: #5568d3;
            transform: translateY(-2px);
            box-shadow: 0 4px 8px rgba(102, 126, 234, 0.3);
        }
        
        button:active {
            transform: translateY(0);
        }
        
        button.secondary {
            background: #95a5a6;
        }
        
        button.secondary:hover {
            background: #7f8c8d;
        }
        
        button.danger {
            background: #e74c3c;
        }
        
        button.danger:hover {
            background: #c0392b;
        }
        
        button.success {
            background: #2ecc71;
        }
        
        button.success:hover {
            background: #27ae60;
        }
        
        .modal {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0,0,0,0.5);
            z-index: 1000;
            overflow-y: auto;
        }
        
        .modal-content {
            background: white;
            max-width: 600px;
            margin: 50px auto;
            padding: 30px;
            border-radius: 10px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.3);
        }
        
        .modal-header {
            font-size: 24px;
            font-weight: 600;
            margin-bottom: 20px;
            padding-bottom: 15px;
            border-bottom: 2px solid #f0f0f0;
        }
        
        .form-group {
            margin-bottom: 20px;
        }
        
        label {
            display: block;
            margin-bottom: 8px;
            font-weight: 500;
            color: #2c3e50;
        }
        
        input[type="text"],
        input[type="number"],
        select {
            width: 100%;
            padding: 10px 15px;
            border: 2px solid #e0e0e0;
            border-radius: 6px;
            font-size: 14px;
            transition: border-color 0.3s ease;
        }
        
        input:focus,
        select:focus {
            outline: none;
            border-color: #667eea;
        }
        
        .checkbox-group {
            display: flex;
            align-items: center;
            gap: 10px;
        }
        
        .checkbox-group input[type="checkbox"] {
            width: 20px;
            height: 20px;
            cursor: pointer;
        }
        
        .alert {
            padding: 15px 20px;
            border-radius: 6px;
            margin-bottom: 20px;
            display: none;
        }
        
        .alert.success {
            background: #d4edda;
            border-left: 4px solid #2ecc71;
            color: #155724;
        }
        
        .alert.error {
            background: #f8d7da;
            border-left: 4px solid #e74c3c;
            color: #721c24;
        }
        
        .empty-state {
            text-align: center;
            padding: 60px 20px;
            color: #95a5a6;
        }
        
        .empty-state svg {
            width: 80px;
            height: 80px;
            margin-bottom: 20px;
            opacity: 0.5;
        }
        
        @media (max-width: 768px) {
            .container {
                padding: 10px;
            }
            
            .header {
                padding: 20px;
            }
            
            .status-bar {
                flex-direction: column;
                align-items: stretch;
            }
            
            .output-header {
                flex-direction: column;
                gap: 10px;
            }
            
            .button-group {
                flex-direction: column;
            }
            
            button {
                width: 100%;
                justify-content: center;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <!-- Header -->
        <div class="header">
            <h1>🛩️ ADS-B Feeder Configuration</h1>
            <p>Manage aggregator outputs and MLAT clients • v0.1.0-alpha</p>
        </div>

        <!-- Alert Messages -->
        <div id="alert" class="alert"></div>

        <!-- Status Bar -->
        <div class="status-bar">
            <div class="status-item">
                <span class="status-indicator" id="readsb-status"></span>
                <span><strong>readsb:</strong> <span id="readsb-text">Checking...</span></span>
            </div>
            <div class="status-item">
                <span class="status-indicator" id="mlat-status"></span>
                <span><strong>mlat-client:</strong> <span id="mlat-text">Checking...</span></span>
            </div>
            <button onclick="refreshStatus()">🔄 Refresh Status</button>
        </div>

        <!-- Outputs Section -->
        <div class="section">
            <div class="section-header">
                <h2 class="section-title">Beast Outputs</h2>
                <button onclick="showAddOutputModal()">+ Add Output</button>
            </div>
            <div id="outputs-container">
                <div class="empty-state">
                    <p>Loading outputs...</p>
                </div>
            </div>
        </div>

        <!-- MLAT Section -->
        <div class="section">
            <div class="section-header">
                <h2 class="section-title">MLAT Clients</h2>
                <button onclick="showAddMLATModal()">+ Add MLAT Client</button>
            </div>
            <div id="mlat-container">
                <div class="empty-state">
                    <p>Loading MLAT clients...</p>
                </div>
            </div>
        </div>

        <!-- Actions -->
        <div class="section">
            <div class="section-header">
                <h2 class="section-title">Actions</h2>
            </div>
            <div class="button-group">
                <button class="success" onclick="applyConfiguration()">✓ Apply Configuration & Restart Services</button>
                <button class="secondary" onclick="downloadConfig()">💾 Download Configuration</button>
            </div>
        </div>
    </div>

    <!-- Add Output Modal -->
    <div id="output-modal" class="modal">
        <div class="modal-content">
            <div class="modal-header">Add Beast Output</div>
            <form id="output-form">
                <div class="form-group">
                    <label>Name:</label>
                    <input type="text" id="output-name" required placeholder="e.g., FlightRadar24">
                </div>
                <div class="form-group">
                    <label>Host:</label>
                    <input type="text" id="output-host" required placeholder="e.g., feed.fr24.com">
                </div>
                <div class="form-group">
                    <label>Port:</label>
                    <input type="number" id="output-port" value="30004" required>
                </div>
                <div class="form-group checkbox-group">
                    <input type="checkbox" id="output-enabled" checked>
                    <label for="output-enabled" style="margin-bottom: 0;">Enabled</label>
                </div>
                <div class="button-group">
                    <button type="submit" class="success">Save Output</button>
                    <button type="button" class="secondary" onclick="closeModal('output-modal')">Cancel</button>
                </div>
            </form>
        </div>
    </div>

    <!-- Add MLAT Modal -->
    <div id="mlat-modal" class="modal">
        <div class="modal-content">
            <div class="modal-header">Add MLAT Client</div>
            <form id="mlat-form">
                <div class="form-group">
                    <label>Name:</label>
                    <input type="text" id="mlat-name" required placeholder="e.g., FR24 MLAT">
                </div>
                <div class="form-group">
                    <label>Server:</label>
                    <input type="text" id="mlat-server" required placeholder="e.g., mlat.fr24.com:30105">
                </div>
                <div class="form-group checkbox-group">
                    <input type="checkbox" id="mlat-enabled" checked>
                    <label for="mlat-enabled" style="margin-bottom: 0;">Enabled</label>
                </div>
                <div class="button-group">
                    <button type="submit" class="success">Save MLAT Client</button>
                    <button type="button" class="secondary" onclick="closeModal('mlat-modal')">Cancel</button>
                </div>
            </form>
        </div>
    </div>

    <script>
        // Global state
        let config = {};

        // Initialize on page load
        document.addEventListener('DOMContentLoaded', function() {
            loadConfiguration();
            checkServiceStatus();
            
            // Set up form handlers
            document.getElementById('output-form').addEventListener('submit', handleAddOutput);
            document.getElementById('mlat-form').addEventListener('submit', handleAddMLAT);
        });

        // Load configuration from server
        function loadConfiguration() {
            fetch('/api/config')
                .then(r => r.json())
                .then(data => {
                    config = data;
                    renderOutputs();
                    renderMLAT();
                })
                .catch(err => showAlert('Error loading configuration: ' + err.message, 'error'));
        }

        // Render Beast outputs
        function renderOutputs() {
            const container = document.getElementById('outputs-container');
            const outputs = config.outputs || [];

            if (outputs.length === 0) {
                container.innerHTML = '<div class="empty-state"><p>No outputs configured</p></div>';
                return;
            }

            container.innerHTML = outputs.map(output => `
                <div class="output-card ${output.primary ? 'primary' : ''} ${!output.enabled ? 'disabled' : ''}">
                    <div class="output-header">
                        <div>
                            <div class="output-title">${output.name}</div>
                            ${output.primary ? '<span class="badge primary">Primary</span>' : ''}
                            <span class="badge ${output.enabled ? 'enabled' : 'disabled'}">
                                ${output.enabled ? 'Enabled' : 'Disabled'}
                            </span>
                        </div>
                    </div>
                    <div class="output-details">
                        <div><strong>Host:</strong> ${output.host}</div>
                        <div><strong>Port:</strong> ${output.port}</div>
                        <div><strong>Type:</strong> ${output.type}</div>
                    </div>
                    <div class="button-group">
                        <button onclick="toggleOutput('${output.id}')">
                            ${output.enabled ? '⏸️ Disable' : '▶️ Enable'}
                        </button>
                        ${!output.primary ? `<button class="danger" onclick="deleteOutput('${output.id}')">🗑️ Delete</button>` : ''}
                    </div>
                </div>
            `).join('');
        }

        // Render MLAT clients
        function renderMLAT() {
            const container = document.getElementById('mlat-container');
            const clients = config.mlat_clients || [];

            if (clients.length === 0) {
                container.innerHTML = '<div class="empty-state"><p>No MLAT clients configured</p></div>';
                return;
            }

            container.innerHTML = clients.map(client => `
                <div class="output-card ${!client.enabled ? 'disabled' : ''}">
                    <div class="output-header">
                        <div>
                            <div class="output-title">${client.name}</div>
                            <span class="badge ${client.enabled ? 'enabled' : 'disabled'}">
                                ${client.enabled ? 'Enabled' : 'Disabled'}
                            </span>
                        </div>
                    </div>
                    <div class="output-details">
                        <div><strong>Server:</strong> ${client.server}</div>
                        <div><strong>Input:</strong> ${client.input_connect}</div>
                        <div><strong>Results:</strong> ${client.results}</div>
                    </div>
                    <div class="button-group">
                        <button onclick="toggleMLAT('${client.id}')">
                            ${client.enabled ? '⏸️ Disable' : '▶️ Enable'}
                        </button>
                        <button class="danger" onclick="deleteMLAT('${client.id}')">🗑️ Delete</button>
                    </div>
                </div>
            `).join('');
        }

        // Check service status
        function checkServiceStatus() {
            fetch('/api/services/status')
                .then(r => r.json())
                .then(data => {
                    updateStatusIndicator('readsb', data.readsb);
                    updateStatusIndicator('mlat', data.mlat_client);
                });
        }

        function updateStatusIndicator(service, active) {
            const indicator = document.getElementById(`${service}-status`);
            const text = document.getElementById(`${service}-text`);
            
            indicator.className = 'status-indicator ' + (active ? 'active' : 'inactive');
            text.textContent = active ? 'Active' : 'Inactive';
        }

        function refreshStatus() {
            checkServiceStatus();
            showAlert('Status refreshed', 'success');
        }

        // Modal functions
        function showAddOutputModal() {
            document.getElementById('output-modal').style.display = 'block';
        }

        function showAddMLATModal() {
            document.getElementById('mlat-modal').style.display = 'block';
        }

        function closeModal(modalId) {
            document.getElementById(modalId).style.display = 'none';
        }

        // Handle add output
        function handleAddOutput(e) {
            e.preventDefault();
            
            const output = {
                name: document.getElementById('output-name').value,
                type: 'beast',
                host: document.getElementById('output-host').value,
                port: parseInt(document.getElementById('output-port').value),
                enabled: document.getElementById('output-enabled').checked
            };

            fetch('/api/outputs', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(output)
            })
            .then(r => r.json())
            .then(() => {
                closeModal('output-modal');
                loadConfiguration();
                showAlert('Output added successfully', 'success');
            })
            .catch(err => showAlert('Error adding output: ' + err.message, 'error'));
        }

        // Handle add MLAT
        function handleAddMLAT(e) {
            e.preventDefault();
            
            const client = {
                name: document.getElementById('mlat-name').value,
                server: document.getElementById('mlat-server').value,
                enabled: document.getElementById('mlat-enabled').checked,
                input_connect: 'localhost:30005',
                results: 'beast,connect,localhost:30104'
            };

            fetch('/api/mlat', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(client)
            })
            .then(r => r.json())
            .then(() => {
                closeModal('mlat-modal');
                loadConfiguration();
                showAlert('MLAT client added successfully', 'success');
            })
            .catch(err => showAlert('Error adding MLAT client: ' + err.message, 'error'));
        }

        // Toggle functions
        function toggleOutput(id) {
            fetch(`/api/outputs/${id}/toggle`, {method: 'POST'})
                .then(() => {
                    loadConfiguration();
                    showAlert('Output toggled', 'success');
                })
                .catch(err => showAlert('Error toggling output: ' + err.message, 'error'));
        }

        function toggleMLAT(id) {
            fetch(`/api/mlat/${id}/toggle`, {method: 'POST'})
                .then(() => {
                    loadConfiguration();
                    showAlert('MLAT client toggled', 'success');
                })
                .catch(err => showAlert('Error toggling MLAT: ' + err.message, 'error'));
        }

        // Delete functions
        function deleteOutput(id) {
            if (!confirm('Delete this output? This will not take effect until you apply configuration.')) return;
            
            fetch(`/api/outputs/${id}`, {method: 'DELETE'})
                .then(() => {
                    loadConfiguration();
                    showAlert('Output deleted', 'success');
                })
                .catch(err => showAlert('Error deleting output: ' + err.message, 'error'));
        }

        function deleteMLAT(id) {
            if (!confirm('Delete this MLAT client? This will not take effect until you apply configuration.')) return;
            
            fetch(`/api/mlat/${id}`, {method: 'DELETE'})
                .then(() => {
                    loadConfiguration();
                    showAlert('MLAT client deleted', 'success');
                })
                .catch(err => showAlert('Error deleting MLAT: ' + err.message, 'error'));
        }

        // Apply configuration
        function applyConfiguration() {
            if (!confirm('Apply configuration and restart services? This will cause brief downtime.')) return;
            
            showAlert('Applying configuration...', 'success');
            
            fetch('/api/apply', {method: 'POST'})
                .then(r => r.json())
                .then(data => {
                    if (data.success) {
                        showAlert('Configuration applied successfully! Services restarting...', 'success');
                        setTimeout(checkServiceStatus, 3000);
                    } else {
                        showAlert('Error: ' + data.message, 'error');
                    }
                })
                .catch(err => showAlert('Error applying configuration: ' + err.message, 'error'));
        }

        // Download config
        function downloadConfig() {
            fetch('/api/config')
                .then(r => r.json())
                .then(data => {
                    const blob = new Blob([JSON.stringify(data, null, 2)], {type: 'application/json'});
                    const url = URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = 'adsb-feeder-config.json';
                    a.click();
                });
        }

        // Alert helper
        function showAlert(message, type) {
            const alert = document.getElementById('alert');
            alert.textContent = message;
            alert.className = 'alert ' + type;
            alert.style.display = 'block';
            
            setTimeout(() => {
                alert.style.display = 'none';
            }, 5000);
        }
    </script>
</body>
</html>
"""

# ============================================================================
# API ROUTES
# ============================================================================

@app.route('/')
def index():
    """Serve the main configuration page"""
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/config', methods=['GET'])
def get_config():
    """Get current configuration"""
    config = load_config()
    return jsonify(config)

@app.route('/api/outputs', methods=['POST'])
def add_output():
    """Add a new Beast output"""
    output = request.json
    config = load_config()
    
    # Generate unique ID
    output['id'] = f"output-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    output['primary'] = False  # User-added outputs are never primary
    
    config['outputs'].append(output)
    
    if save_config(config):
        return jsonify({"success": True, "id": output['id']})
    else:
        return jsonify({"success": False, "message": "Failed to save configuration"}), 500

@app.route('/api/outputs/<output_id>', methods=['DELETE'])
def delete_output(output_id):
    """Delete an output"""
    config = load_config()
    
    # Don't allow deleting primary output
    for output in config['outputs']:
        if output['id'] == output_id and output.get('primary', False):
            return jsonify({"success": False, "message": "Cannot delete primary output"}), 400
    
    config['outputs'] = [o for o in config['outputs'] if o['id'] != output_id]
    
    if save_config(config):
        return jsonify({"success": True})
    else:
        return jsonify({"success": False, "message": "Failed to save configuration"}), 500

@app.route('/api/outputs/<output_id>/toggle', methods=['POST'])
def toggle_output(output_id):
    """Enable/disable an output"""
    config = load_config()
    
    for output in config['outputs']:
        if output['id'] == output_id:
            # Don't allow disabling primary output
            if output.get('primary', False):
                return jsonify({"success": False, "message": "Cannot disable primary output"}), 400
            
            output['enabled'] = not output.get('enabled', True)
            break
    
    if save_config(config):
        return jsonify({"success": True})
    else:
        return jsonify({"success": False, "message": "Failed to save configuration"}), 500

@app.route('/api/mlat', methods=['POST'])
def add_mlat():
    """Add a new MLAT client"""
    client = request.json
    config = load_config()
    
    # Generate unique ID
    client['id'] = f"mlat-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    
    config['mlat_clients'].append(client)
    
    if save_config(config):
        return jsonify({"success": True, "id": client['id']})
    else:
        return jsonify({"success": False, "message": "Failed to save configuration"}), 500

@app.route('/api/mlat/<client_id>', methods=['DELETE'])
def delete_mlat(client_id):
    """Delete an MLAT client"""
    config = load_config()
    config['mlat_clients'] = [c for c in config.get('mlat_clients', []) if c['id'] != client_id]
    
    if save_config(config):
        return jsonify({"success": True})
    else:
        return jsonify({"success": False, "message": "Failed to save configuration"}), 500

@app.route('/api/mlat/<client_id>/toggle', methods=['POST'])
def toggle_mlat(client_id):
    """Enable/disable an MLAT client"""
    config = load_config()
    
    for client in config.get('mlat_clients', []):
        if client['id'] == client_id:
            client['enabled'] = not client.get('enabled', True)
            break
    
    if save_config(config):
        return jsonify({"success": True})
    else:
        return jsonify({"success": False, "message": "Failed to save configuration"}), 500

@app.route('/api/services/status', methods=['GET'])
def services_status():
    """Get status of all services"""
    return jsonify({
        "readsb": get_service_status('readsb'),
        "mlat_client": get_service_status('mlat-client')
    })

@app.route('/api/apply', methods=['POST'])
def apply_config():
    """Apply configuration and restart services"""
    success, message = apply_configuration()
    return jsonify({"success": success, "message": message})

# ============================================================================
# MAIN
# ============================================================================

if __name__ == '__main__':
    print("=" * 60)
    print("ADS-B Feeder Web Configuration Interface")
    print("=" * 60)
    print(f"Configuration file: {CONFIG_FILE}")
    print(f"Starting web server on port 8080...")
    print(f"Access at: http://localhost:8080")
    print(f"Or via Tailscale: http://TAILSCALE_IP:8080")
    print("=" * 60)
    print("\nPress Ctrl+C to stop\n")
    
    # Run on all interfaces, port 8080
    # Note: For production, use gunicorn or uwsgi instead of Flask dev server
    app.run(host='0.0.0.0', port=8080, debug=False, threaded=True)
