#!/usr/bin/env python3
"""
TAKNET-PS-ADSB-Feeder Web Interface v2.1
Flask app with Tailscale hostname management
"""

from flask import Flask, render_template, request, jsonify, redirect, url_for
import subprocess
import os
from pathlib import Path
import json
import threading
import time
import uuid
import socket

app = Flask(__name__)

# Version information - read from VERSION file
def get_version():
    """Read version from VERSION file"""
    version_file = Path('/opt/adsb/VERSION')
    if version_file.exists():
        return version_file.read_text().strip()
    return "unknown"

VERSION = get_version()

# Global progress tracking
service_progress = {
    'service': 'idle',
    'progress': 0,
    'total': 0,
    'status': 'Ready',
    'details': ''
}
progress_lock = threading.Lock()

# Tailscale installation progress tracking
tailscale_progress = {
    'status': 'idle',  # idle, downloading, installing, registering, completed, failed
    'download_progress': 0,
    'install_progress': 0,
    'register_progress': 0,
    'message': '',
    'download_bytes': 0,
    'total_bytes': 0,
    'error': None
}
tailscale_progress_lock = threading.Lock()

def update_progress(service, progress, total=100, status='', details=''):
    """Update global progress state"""
    global service_progress
    with progress_lock:
        service_progress = {
            'service': service,
            'progress': progress,
            'total': total,
            'status': status,
            'details': details
        }

def reset_progress():
    """Reset progress to idle"""
    update_progress('idle', 0, 100, 'Ready', '')

ENV_FILE = Path("/opt/adsb/config/.env")
CONFIG_BUILDER = "/opt/adsb/scripts/config_builder.py"

# TAKNET-PS Server hardcoded connection details - NEVER allow user to change these
TAK_PROTECTED_SETTINGS = {
    'TAKNET_PS_SERVER_HOST_PRIMARY': 'secure.tak-solutions.com',
    'TAKNET_PS_SERVER_HOST_FALLBACK': 'adsb.tak-solutions.com',
    'TAKNET_PS_SERVER_PORT': '30004',
    'TAKNET_PS_CONNECTION_MODE': 'auto'
}

def read_env():
    """Read .env file and return as dict"""
    env_vars = {}
    if ENV_FILE.exists():
        with open(ENV_FILE) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    env_vars[key.strip()] = value.strip()
    return env_vars

def get_taknet_connection_status(env_vars):
    """
    Get current TAKNET-PS connection status by running Tailscale detection
    Returns dict with selected_host, connection_type, etc.
    """
    import sys
    sys.path.insert(0, '/opt/adsb/scripts')
    try:
        from config_builder import check_tailscale_running, select_taknet_host
        
        if env_vars.get('TAKNET_PS_ENABLED', 'true').lower() != 'true':
            return None
        
        # Run the same detection logic as config_builder.py
        selected_host, connection_type = select_taknet_host(env_vars)
        
        if not selected_host:
            return None
        
        return {
            'enabled': True,
            'selected_host': selected_host,
            'connection_type': connection_type,
            'port': env_vars.get('TAKNET_PS_SERVER_PORT', '30004'),
            'mlat_port': env_vars.get('TAKNET_PS_MLAT_PORT', '30105'),
            'mlat_enabled': env_vars.get('TAKNET_PS_MLAT_ENABLED', 'true').lower() == 'true'
        }
    except Exception as e:
        print(f"Error getting TAKNET-PS status: {e}")
        return None

def write_env(env_vars):
    """Write dict to .env file"""
    lines = []
    for key, value in env_vars.items():
        lines.append(f"{key}={value}\n")
    with open(ENV_FILE, 'w') as f:
        f.writelines(lines)

def update_env_var(key, value):
    """Update a single environment variable in .env file"""
    env_vars = read_env()
    env_vars[key] = value
    write_env(env_vars)

def get_or_create_feeder_uuid():
    """
    Get existing feeder UUID from .env or generate a new one.
    The UUID persists across reboots and is used by aggregators like adsb.lol
    """
    env_vars = read_env()
    
    # Check if UUID already exists
    if 'FEEDER_UUID' in env_vars and env_vars['FEEDER_UUID']:
        return env_vars['FEEDER_UUID']
    
    # Generate new UUID
    feeder_uuid = str(uuid.uuid4())
    
    # Save to .env
    env_vars['FEEDER_UUID'] = feeder_uuid
    write_env(env_vars)
    
    print(f"Generated new feeder UUID: {feeder_uuid}")
    return feeder_uuid

def get_docker_status():
    """Get Docker container status"""
    try:
        result = subprocess.run(
            ['docker', 'ps', '--format', '{{.Names}}\t{{.Status}}'],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            containers = {}
            for line in result.stdout.strip().split('\n'):
                if line:
                    name, status = line.split('\t', 1)
                    containers[name] = status
            return containers
        return {}
    except:
        return {}

def get_docker_status_all():
    """Get Docker container status for ALL containers (running and stopped)"""
    try:
        result = subprocess.run(
            ['docker', 'ps', '-a', '--format', '{{.Names}}\t{{.Status}}'],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            containers = {}
            for line in result.stdout.strip().split('\n'):
                if line:
                    parts = line.split('\t', 1)
                    if len(parts) == 2:
                        name, status = parts
                        containers[name] = status
            return containers
        return {}
    except:
        return {}

def container_exists(container_name):
    """Check if a Docker container exists (running or stopped)"""
    try:
        result = subprocess.run(
            ['docker', 'ps', '-a', '--format', '{{.Names}}'],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            containers = result.stdout.strip().split('\n')
            return container_name in containers
        return False
    except:
        return False

# Cache for service states to prevent flickering
service_state_cache = {}
service_state_cache_time = {}
SERVICE_STATE_CACHE_DURATION = 2  # seconds

def get_service_state(service_name):
    """Get detailed service state: downloading, starting, running, stopped, or not_installed"""
    global service_progress, service_state_cache, service_state_cache_time
    
    # Return cached state if still valid
    current_time = time.time()
    if service_name in service_state_cache:
        cache_age = current_time - service_state_cache_time.get(service_name, 0)
        if cache_age < SERVICE_STATE_CACHE_DURATION:
            return service_state_cache[service_name]
    
    # Check if currently being downloaded/started (tracked by progress system)
    with progress_lock:
        if service_progress['service'] == service_name:
            if service_progress['progress'] < 100:
                state = 'downloading' if service_progress['progress'] < 85 else 'starting'
                service_state_cache[service_name] = state
                service_state_cache_time[service_name] = current_time
                return state
    
    # Single atomic Docker check - get ALL container statuses at once
    docker_status_all = get_docker_status_all()
    container_name = service_name
    
    # Check if container exists and get its status
    if container_name in docker_status_all:
        status = docker_status_all[container_name]
        
        # Parse Docker status string
        if 'Up' in status:
            state = 'running'
        elif 'Restarting' in status:
            state = 'starting'
        elif 'Exited' in status or 'Created' in status:
            state = 'stopped'
        else:
            # Unknown status - default to stopped
            state = 'stopped'
    else:
        # Container doesn't exist
        state = 'not_installed'
    
    # Cache the result
    service_state_cache[service_name] = state
    service_state_cache_time[service_name] = current_time
    
    return state

def monitor_docker_progress(service_name='ultrafeeder'):
    """
    Monitor docker-compose up in real-time by streaming its output
    v2.40.6: No timeout - monitors until actually complete
    Parses actual Docker output for accurate progress
    """
    try:
        reset_progress()
        update_progress(service_name, 1, 100, 'Initializing...', 'Starting')
        
        # Run config builder first
        subprocess.run(
            ['python3', '/opt/adsb/scripts/config_builder.py'],
            capture_output=True,
            timeout=10,
            cwd='/opt/adsb'
        )
        
        update_progress(service_name, 5, 100, 'Starting Docker Compose...', 'Preparing')
        
        # Run docker compose with streaming output
        process = subprocess.Popen(
            ['docker', 'compose', 'up', '-d'],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,  # Merge stderr to stdout
            text=True,
            bufsize=1,  # Line buffered
            cwd='/opt/adsb/config'
        )
        
        current_image = None
        images_pulled = set()
        total_images = 3  # ultrafeeder, piaware, fr24
        containers_created = set()
        containers_started = set()
        
        # Read output line by line until process completes
        for line in process.stdout:
            line = line.strip()
            if not line:
                continue
            
            # Image pulling started
            if 'Pulling' in line and 'Container' not in line:
                if 'ultrafeeder' in line.lower():
                    current_image = 'ultrafeeder'
                    update_progress(service_name, 10, 100, 'Pulling ultrafeeder image...', 'Downloading')
                elif 'piaware' in line.lower():
                    current_image = 'piaware'
                    update_progress(service_name, 30, 100, 'Pulling piaware image...', 'Downloading')
                elif 'fr24' in line.lower() or 'flightradar' in line.lower():
                    current_image = 'fr24'
                    update_progress(service_name, 50, 100, 'Pulling fr24 image...', 'Downloading')
            
            # Download progress (format: " 14324c29e8df Downloading  25.5MB/100MB")
            elif 'Downloading' in line and 'MB' in line:
                try:
                    # Look for pattern like "25.5MB/100MB"
                    import re
                    match = re.search(r'(\d+\.?\d*)\s*MB\s*/\s*(\d+\.?\d*)\s*MB', line)
                    if match:
                        downloaded = float(match.group(1))
                        total = float(match.group(2))
                        
                        # Calculate base progress based on which image
                        base = 10 if current_image == 'ultrafeeder' else (30 if current_image == 'piaware' else 50)
                        img_progress = int((downloaded / total) * 18) if total > 0 else 0
                        
                        update_progress(
                            service_name,
                            base + img_progress,
                            100,
                            f'Downloading {current_image}...',
                            f'{downloaded:.1f}MB / {total:.1f}MB'
                        )
                except:
                    pass
            
            # Extract progress
            elif 'Extracting' in line:
                if current_image:
                    base = 10 if current_image == 'ultrafeeder' else (30 if current_image == 'piaware' else 50)
                    update_progress(service_name, base + 15, 100, f'Extracting {current_image}...', 'Preparing')
            
            # Image pulled completely
            elif 'Pull complete' in line or ('Pulled' in line and 'Image' in line):
                if current_image and current_image not in images_pulled:
                    images_pulled.add(current_image)
                    progress = 10 + (len(images_pulled) * 20)
                    update_progress(
                        service_name,
                        min(68, progress),
                        100,
                        f'{len(images_pulled)}/{total_images} images ready',
                        f'{current_image} ✓'
                    )
            
            # Network creation
            elif 'Network' in line and ('Creating' in line or 'Created' in line):
                update_progress(service_name, 70, 100, 'Creating network...', 'Setting up')
            
            # Container creation
            elif 'Container' in line and 'Creating' in line:
                parts = line.split()
                container_name = parts[1] if len(parts) > 1 else 'container'
                update_progress(service_name, 75, 100, f'Creating {container_name}...', 'Initializing')
            
            elif 'Container' in line and 'Created' in line:
                parts = line.split()
                container_name = parts[1] if len(parts) > 1 else 'container'
                if container_name not in containers_created:
                    containers_created.add(container_name)
                    progress = 75 + (len(containers_created) * 5)
                    update_progress(service_name, progress, 100, f'{container_name} created', 'Ready')
            
            # Container starting
            elif 'Container' in line and 'Starting' in line:
                parts = line.split()
                container_name = parts[1] if len(parts) > 1 else 'container'
                update_progress(service_name, 90, 100, f'Starting {container_name}...', 'Almost done')
            
            elif 'Container' in line and 'Started' in line:
                parts = line.split()
                container_name = parts[1] if len(parts) > 1 else 'container'
                if container_name not in containers_started:
                    containers_started.add(container_name)
                    progress = 90 + (len(containers_started) * 3)
                    update_progress(service_name, min(99, progress), 100, f'{container_name} started', '✓')
        
        # Wait for process to complete
        process.wait()
        
        # Final verification - check if ultrafeeder is actually running
        import time
        time.sleep(2)
        result = subprocess.run(
            ['docker', 'ps', '--filter', 'name=ultrafeeder', '--filter', 'status=running', '--format', '{{.Names}}'],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if 'ultrafeeder' in result.stdout:
            update_progress(service_name, 100, 100, 'Setup complete!', 'All containers running ✓')
        else:
            # Containers created but may still be initializing
            update_progress(service_name, 95, 100, 'Finalizing startup...', 'Please wait')
        
    except Exception as e:
        print(f"Docker compose monitoring error: {e}")
        import traceback
        traceback.print_exc()
        update_progress(service_name, 85, 100, 'Starting...', 'Please check dashboard')

def restart_service():
    """Restart ultrafeeder service - with real-time Docker progress monitoring (v2.40.6)"""
    import time
    try:
        # Brief delay to prevent rapid-fire restarts
        time.sleep(1)
        
        # Reset progress before starting
        reset_progress()
        
        # Start progress monitoring in background thread
        # v2.40.6: This thread now runs docker-compose directly and monitors its output
        # No more systemctl - we stream docker-compose output for real progress
        monitor_thread = threading.Thread(target=monitor_docker_progress, args=('ultrafeeder',), daemon=True)
        monitor_thread.start()
        
        print("✓ Docker Compose starting with real-time progress monitoring (v2.40.6)")
        return True
        
    except Exception as e:
        print(f"✗ Failed to initiate restart: {e}")
        return False

def rebuild_config():
    """Run config_builder.py"""
    try:
        result = subprocess.run(
            ['python3', CONFIG_BUILDER],
            timeout=10,
            capture_output=True,
            text=True,
            cwd='/opt/adsb'
        )
        if result.returncode == 0:
            print("✓ Config rebuilt successfully")
            print(result.stdout)
            return True
        else:
            print(f"✗ Config rebuild failed (code {result.returncode})")
            print(f"stderr: {result.stderr}")
            print(f"stdout: {result.stdout}")
            return False
    except subprocess.TimeoutExpired:
        print("✗ Config rebuild timed out after 10 seconds")
        return False
    except Exception as e:
        print(f"✗ Config rebuild exception: {e}")
        return False

def install_tailscale(auth_key=None, hostname=None):
    """Install and configure Tailscale with optional hostname"""
    try:
        # Use full path to tailscale binary
        tailscale_bin = '/usr/bin/tailscale'
        
        # Check if already installed
        check_result = subprocess.run(['which', 'tailscale'], 
                                     capture_output=True, timeout=5)
        
        was_just_installed = False
        if check_result.returncode != 0:
            # Install Tailscale
            print("⚙ Installing Tailscale...")
            install_cmd = 'curl -fsSL https://tailscale.com/install.sh | sh'
            install_result = subprocess.run(install_cmd, shell=True, timeout=120, 
                                          capture_output=True, text=True)
            
            if install_result.returncode != 0:
                return {'success': False, 'message': f'Installation failed: {install_result.stderr}'}
            
            # Verify installation succeeded by checking if binary exists
            if not os.path.exists(tailscale_bin):
                return {'success': False, 'message': 'Installation completed but tailscale binary not found'}
            
            print("✓ Tailscale installed successfully")
            was_just_installed = True
        
        # If auth key provided, authenticate
        if auth_key:
            # Only run 'down' if Tailscale was already installed (not if we just installed it)
            if not was_just_installed:
                print("⚙ Clearing previous Tailscale connection...")
                try:
                    subprocess.run([tailscale_bin, 'down'], timeout=10, capture_output=True)
                except Exception as e:
                    print(f"⚠ Warning: Could not run 'tailscale down': {e}")
            
            # Build up command with optional hostname
            cmd = [tailscale_bin, 'up', '--authkey', auth_key]
            
            if hostname:
                cmd.extend(['--hostname', hostname])
            
            print(f"⚙ Connecting to Tailscale network as: {hostname if hostname else 'default hostname'}...")
            # Up with new key and hostname
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode != 0:
                return {'success': False, 'message': f'Authentication failed: {result.stderr}'}
            
            print("✓ Connected to Tailscale network")
        else:
            # Just start Tailscale (no auth key provided)
            print("⚙ Starting Tailscale...")
            result = subprocess.run([tailscale_bin, 'up'], timeout=30, 
                                  capture_output=True, text=True)
            if result.returncode != 0:
                return {'success': False, 'message': f'Failed to start Tailscale: {result.stderr}'}
        
        # SECURITY: Automatically configure SSH for Tailscale-only access
        # Run the configure-ssh-tailscale.sh script
        try:
            ssh_config_script = '/opt/adsb/configure-ssh-tailscale.sh'
            if os.path.exists(ssh_config_script):
                subprocess.run(['bash', ssh_config_script], 
                             capture_output=True, 
                             timeout=10,
                             check=False)  # Don't fail if SSH config has issues
                print("✓ SSH configured for Tailscale-only access")
        except Exception as e:
            print(f"⚠️ SSH configuration failed (non-critical): {e}")
        
        return {'success': True, 'message': 'Tailscale configured successfully'}
        
    except subprocess.TimeoutExpired:
        return {'success': False, 'message': 'Installation timed out'}
    except Exception as e:
        return {'success': False, 'message': str(e)}

def get_tailscale_status():
    """Get Tailscale connection status with tailnet validation"""
    try:
        tailscale_bin = '/usr/bin/tailscale'
        
        # Check if installed
        if not os.path.exists(tailscale_bin):
            return {
                'installed': False,
                'connected': False,
                'message': 'Tailscale not installed'
            }
        
        # Get status
        result = subprocess.run([tailscale_bin, 'status', '--json'], 
                               capture_output=True, text=True, timeout=5)
        
        if result.returncode == 0:
            try:
                status_data = json.loads(result.stdout)
                
                # Check if connected (BackendState should be "Running")
                backend_state = status_data.get('BackendState', '')
                connected = backend_state == 'Running'
                
                # Get self info
                self_info = status_data.get('Self', {})
                ip = self_info.get('TailscaleIPs', [''])[0] if self_info.get('TailscaleIPs') else None
                hostname = self_info.get('DNSName', '').rstrip('.')
                
                # CRITICAL: Validate we're on TAKNET-PS tailnet
                expected_suffix = 'tail4d77be.ts.net'
                on_correct_tailnet = hostname.endswith(expected_suffix) if hostname else False
                
                if connected and not on_correct_tailnet:
                    # Connected but to WRONG tailnet
                    return {
                        'installed': True,
                        'connected': False,  # Treat as not connected
                        'wrong_tailnet': True,
                        'ip': ip,
                        'hostname': hostname,
                        'backend_state': backend_state,
                        'message': f'Connected to wrong tailnet: {hostname}. Expected: *.{expected_suffix}'
                    }
                
                return {
                    'installed': True,
                    'connected': connected and on_correct_tailnet,
                    'ip': ip,
                    'hostname': hostname,
                    'backend_state': backend_state,
                    'on_correct_tailnet': on_correct_tailnet
                }
            except json.JSONDecodeError:
                # Fall back to non-JSON status
                result = subprocess.run([tailscale_bin, 'status'], 
                                       capture_output=True, text=True, timeout=5)
                return {
                    'installed': True,
                    'connected': 'running' in result.stdout.lower(),
                    'message': 'Connected' if result.returncode == 0 else 'Not connected'
                }
        else:
            return {
                'installed': True,
                'connected': False,
                'message': 'Tailscale installed but not running'
            }
            
    except FileNotFoundError:
        return {
            'installed': False,
            'connected': False,
            'message': 'Tailscale not installed'
        }
    except Exception as e:
        return {
            'installed': False,
            'connected': False,
            'error': str(e)
        }

def update_tailscale_progress(status, download_progress=0, install_progress=0, register_progress=0, message='', download_bytes=0, total_bytes=0):
    """Update global Tailscale progress state"""
    global tailscale_progress
    with tailscale_progress_lock:
        tailscale_progress['status'] = status
        tailscale_progress['download_progress'] = download_progress
        tailscale_progress['install_progress'] = install_progress
        tailscale_progress['register_progress'] = register_progress
        tailscale_progress['message'] = message
        tailscale_progress['download_bytes'] = download_bytes
        tailscale_progress['total_bytes'] = total_bytes
        print(f"[Tailscale Progress] {status}: {message} (download: {download_progress}%, install: {install_progress}%, register: {register_progress}%)")

def install_tailscale_with_progress(auth_key=None, hostname=None):
    """Install and configure Tailscale with progress tracking"""
    try:
        tailscale_bin = '/usr/bin/tailscale'
        
        # === PHASE 1: DOWNLOAD (0-100%) ===
        check_result = subprocess.run(['which', 'tailscale'], 
                                     capture_output=True, timeout=5)
        
        was_just_installed = False
        if check_result.returncode != 0:
            # Download Tailscale with real progress tracking
            update_tailscale_progress('downloading', 0, 0, 0, 'Preparing download...', 0, 0)
            
            # Download install script first to temp file, then execute
            # This lets us track actual download progress
            import tempfile
            temp_script = tempfile.NamedTemporaryFile(mode='w', suffix='.sh', delete=False)
            temp_script_path = temp_script.name
            temp_script.close()
            
            # Download the install script with progress
            download_cmd = ['curl', '-L', '--progress-bar', 
                          'https://tailscale.com/install.sh',
                          '-o', temp_script_path]
            
            # Run download with real-time progress capture
            process = subprocess.Popen(download_cmd, 
                                     stderr=subprocess.PIPE, 
                                     text=True)
            
            # Track download progress from curl's stderr
            last_progress = 0
            for line in process.stderr:
                # Curl progress bar format: ### (percentage)
                # Example: "######################################################################## 100.0%"
                if '%' in line:
                    try:
                        # Extract percentage from progress bar
                        percent_str = line.split()[-1].replace('%', '')
                        percent = float(percent_str)
                        
                        # Estimate bytes (install script is ~30KB, but we'll show approximate download size)
                        # The actual tailscale binary download happens during script execution
                        estimated_total = 30 * 1024  # 30 KB for script
                        downloaded_bytes = int((percent / 100) * estimated_total)
                        
                        # Only update if progress changed significantly
                        if abs(percent - last_progress) >= 5:
                            update_tailscale_progress('downloading', int(percent), 0, 0, 
                                                    'Downloading install script...', 
                                                    downloaded_bytes, estimated_total)
                            last_progress = percent
                    except:
                        pass
            
            process.wait()
            
            if process.returncode != 0:
                os.unlink(temp_script_path)
                update_tailscale_progress('failed', 0, 0, 0, 'Failed to download install script', 0, 0)
                return
            
            update_tailscale_progress('downloading', 100, 0, 0, 'Script downloaded, installing packages...', 
                                    30 * 1024, 30 * 1024)
            
            # Now run the install script
            # Note: The actual binary download happens here, but we can't easily track it
            # We'll show indeterminate progress during package installation
            install_result = subprocess.run(['bash', temp_script_path], 
                                          timeout=120, 
                                          capture_output=True, 
                                          text=True)
            
            # Clean up temp file
            os.unlink(temp_script_path)
            
            if install_result.returncode != 0:
                update_tailscale_progress('failed', 0, 0, 0, 
                                        f'Installation failed: {install_result.stderr}', 0, 0)
                return
            
            # Verify installation succeeded
            if not os.path.exists(tailscale_bin):
                update_tailscale_progress('failed', 0, 0, 0, 
                                        'Installation completed but binary not found', 0, 0)
                return
            
            update_tailscale_progress('downloading', 100, 0, 0, 'Download complete', 0, 0)
            was_just_installed = True
        else:
            # Already installed, skip download phase
            update_tailscale_progress('downloading', 100, 0, 0, 'Tailscale already installed', 0, 0)
        
        time.sleep(0.5)
        
        # === PHASE 2: INSTALL (0-100%) ===
        for i in range(0, 101, 20):
            update_tailscale_progress('installing', 100, i, 0, 'Installing...', 0, 0)
            time.sleep(0.5)
        
        # Clear previous connection if needed (logout completely from old tailnet)
        if auth_key and not was_just_installed:
            try:
                # Use logout to completely disconnect from old tailnet
                # This allows connecting to a different tailnet with new auth key
                subprocess.run([tailscale_bin, 'logout'], timeout=10, capture_output=True)
                print("✓ Logged out of previous Tailscale tailnet")
            except Exception as e:
                print(f"⚠ Warning: Could not run 'tailscale logout': {e}")
        
        update_tailscale_progress('installing', 100, 100, 0, 'Installation complete', 0, 0)
        time.sleep(0.5)
        
        # === PHASE 3: REGISTER (0-100%) ===
        if auth_key:
            cmd = [tailscale_bin, 'up', '--authkey', auth_key]
            if hostname:
                cmd.extend(['--hostname', hostname])
            
            update_tailscale_progress('registering', 100, 100, 10, 
                                    'Registering to Tailscale network...', 0, 0)
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode != 0:
                update_tailscale_progress('failed', 100, 100, 0, 
                                        f'Authentication failed: {result.stderr}', 0, 0)
                return
            
            for i in range(20, 70, 10):
                update_tailscale_progress('registering', 100, 100, i, 
                                        'Registering to Tailscale network...', 0, 0)
                time.sleep(0.5)
        else:
            update_tailscale_progress('registering', 100, 100, 10, 'Starting Tailscale...', 0, 0)
            result = subprocess.run([tailscale_bin, 'up'], timeout=30, 
                                  capture_output=True, text=True)
            if result.returncode != 0:
                update_tailscale_progress('failed', 100, 100, 0, 
                                        f'Failed to start: {result.stderr}', 0, 0)
                return
            
            for i in range(20, 70, 10):
                update_tailscale_progress('registering', 100, 100, i, 'Starting Tailscale...', 0, 0)
                time.sleep(0.5)
        
        # Verify connection
        connected = False
        for attempt in range(30):
            try:
                status_result = subprocess.run([tailscale_bin, 'status', '--json'], 
                                             capture_output=True, text=True, timeout=5)
                if status_result.returncode == 0:
                    try:
                        status_data = json.loads(status_result.stdout)
                        backend_state = status_data.get('BackendState', '')
                        if backend_state == 'Running':
                            connected = True
                            update_tailscale_progress('registering', 100, 100, 95, 
                                                    'Connection verified!', 0, 0)
                            break
                    except:
                        pass
            except:
                pass
            
            time.sleep(1)
            verify_progress = 70 + min(attempt, 25)
            update_tailscale_progress('registering', 100, 100, verify_progress, 
                                    'Verifying connection...', 0, 0)
        
        if not connected:
            update_tailscale_progress('registering', 100, 100, 95, 
                                    'Verification timed out - Tailscale may still be working', 0, 0)
        
        # Configure SSH
        update_tailscale_progress('registering', 100, 100, 98, 'Configuring SSH security...', 0, 0)
        try:
            ssh_config_script = '/opt/adsb/configure-ssh-tailscale.sh'
            if os.path.exists(ssh_config_script):
                subprocess.run(['bash', ssh_config_script], 
                             capture_output=True, 
                             timeout=10,
                             check=False)
        except Exception as e:
            print(f"⚠️ SSH configuration failed (non-critical): {e}")
        
        # Success!
        update_tailscale_progress('completed', 100, 100, 100, 
                                'Tailscale connected successfully!', 0, 0)
        
        # Save hostname to .env file if it was provided
        if hostname:
            try:
                env = read_env()
                env['TAILSCALE_HOSTNAME'] = hostname
                write_env(env)
                print(f"✓ Tailscale hostname saved: {hostname}")
            except Exception as e:
                print(f"⚠️ Could not save Tailscale hostname: {e}")
        
        # CRITICAL: Rebuild ultrafeeder config to switch from public IP to Tailscale
        print("✓ Tailscale connected - rebuilding ultrafeeder config...")
        try:
            if rebuild_config():
                print("✓ Config rebuilt successfully")
                # Restart ultrafeeder to apply new Tailscale connection
                if restart_service():
                    print("✓ Ultrafeeder restarted with Tailscale connection")
                else:
                    print("⚠ Config rebuilt but service restart failed")
            else:
                print("⚠ Config rebuild failed after Tailscale install")
        except Exception as e:
            print(f"⚠ Error rebuilding config after Tailscale install: {e}")
        
    except subprocess.TimeoutExpired:
        update_tailscale_progress('failed', 0, 0, 0, 'Installation timed out', 0, 0)
    except Exception as e:
        update_tailscale_progress('failed', 0, 0, 0, str(e), 0, 0)
        update_tailscale_progress('failed', 0, 0, str(e))

def get_network_connection_mode():
    """Detect current internet connection type: wifi, ethernet, usb, or none"""
    try:
        # Check for active interfaces with internet connectivity
        result = subprocess.run(['ip', 'route', 'get', '8.8.8.8'], 
                              capture_output=True, text=True, timeout=5)
        
        if result.returncode != 0:
            return {'mode': 'none', 'interface': None, 'details': 'No internet connection'}
        
        # Parse the output to find the interface
        # Example output: "8.8.8.8 via 192.168.1.1 dev wlan0 src 192.168.1.100"
        output = result.stdout
        interface = None
        
        if ' dev ' in output:
            parts = output.split(' dev ')
            if len(parts) > 1:
                interface = parts[1].split()[0]
        
        if not interface:
            return {'mode': 'unknown', 'interface': None, 'details': 'Could not determine interface'}
        
        # Determine connection type based on interface name
        if interface.startswith('wlan') or interface.startswith('wl'):
            # WiFi connection - get SSID
            try:
                ssid_result = subprocess.run(['iwgetid', '-r'], 
                                           capture_output=True, text=True, timeout=2)
                ssid = ssid_result.stdout.strip() if ssid_result.returncode == 0 else 'Unknown'
                return {
                    'mode': 'wifi',
                    'interface': interface,
                    'details': f'Connected to {ssid}',
                    'ssid': ssid
                }
            except:
                return {
                    'mode': 'wifi',
                    'interface': interface,
                    'details': 'WiFi connected'
                }
        
        elif interface.startswith('eth') or interface.startswith('enp'):
            # Ethernet connection
            return {
                'mode': 'ethernet',
                'interface': interface,
                'details': 'Ethernet connected'
            }
        
        elif interface.startswith('usb') or interface.startswith('rndis'):
            # USB tethering
            return {
                'mode': 'usb',
                'interface': interface,
                'details': 'USB tethering'
            }
        
        elif interface.startswith('tailscale') or interface.startswith('ts'):
            # Tailscale VPN (check underlying connection)
            # Try to find the physical interface
            try:
                # Get all interfaces with IP addresses
                ip_result = subprocess.run(['ip', '-br', 'addr', 'show'], 
                                         capture_output=True, text=True, timeout=2)
                for line in ip_result.stdout.split('\n'):
                    if 'UP' in line:
                        iface_name = line.split()[0]
                        if iface_name.startswith('wlan'):
                            return {
                                'mode': 'wifi',
                                'interface': iface_name,
                                'details': 'WiFi (via Tailscale)'
                            }
                        elif iface_name.startswith('eth'):
                            return {
                                'mode': 'ethernet',
                                'interface': iface_name,
                                'details': 'Ethernet (via Tailscale)'
                            }
            except:
                pass
            
            return {
                'mode': 'vpn',
                'interface': interface,
                'details': 'Tailscale VPN'
            }
        
        else:
            # Unknown interface type
            return {
                'mode': 'other',
                'interface': interface,
                'details': f'Connected via {interface}'
            }
    
    except subprocess.TimeoutExpired:
        return {'mode': 'none', 'interface': None, 'details': 'Connection check timed out'}
    except Exception as e:
        return {'mode': 'unknown', 'interface': None, 'details': f'Error: {str(e)}'}

# Routes
@app.route('/')
def index():
    """Main page - check if configured"""
    env = read_env()
    
    # ALWAYS check SDR first (even on fresh install)
    # If no SDR device configured, go to SDR wizard
    sdr_configured = False
    if env.get('READSB_DEVICE'):
        sdr_configured = True
    else:
        # Check if any SDR_X entries exist
        for key in env.keys():
            if key.startswith('SDR_'):
                sdr_configured = True
                break
    
    if not sdr_configured:
        return redirect(url_for('setup_sdr'))
    
    # Then check if location is configured
    # Default env has FEEDER_LAT=0.0, so check if it's still default
    if env.get('FEEDER_LAT', '0.0') == '0.0' or env.get('FEEDER_LAT', '0') == '0':
        return redirect(url_for('setup'))
    
    # Everything configured, go to dashboard
    return redirect(url_for('dashboard'))

@app.route('/setup/sdr')
def setup_sdr():
    """Setup wizard - Step 1: SDR Configuration"""
    return render_template('setup-sdr.html')

@app.route('/setup')
def setup():
    """Setup wizard - Step 2: Location Configuration"""
    env = read_env()
    feeder_uuid = get_or_create_feeder_uuid()
    return render_template('setup.html', config=env, feeder_uuid=feeder_uuid)

@app.route('/loading')
def loading():
    """Loading page with real-time status"""
    return render_template('loading.html')

@app.route('/dashboard')
def dashboard():
    """Status dashboard"""
    env = read_env()
    docker_status = get_docker_status()
    taknet_status = get_taknet_connection_status(env)
    feeder_uuid = get_or_create_feeder_uuid()
    
    # Get network info
    connection_mode = get_network_connection_mode()
    network_info = {
        'hostname': env.get('TAILSCALE_HOSTNAME', socket.gethostname()),
        'machine_name': env.get('MLAT_SITE_NAME', 'Unknown'),
        'connection_mode': connection_mode.get('mode', 'unknown'),
        'connection_details': connection_mode.get('details', 'Unknown'),
        'interface': connection_mode.get('interface', 'N/A')
    }
    
    return render_template('dashboard.html', config=env, docker=docker_status, version=VERSION, taknet_status=taknet_status, feeder_uuid=feeder_uuid, network_info=network_info)

@app.route('/logs')
def logs():
    """Logs page (placeholder)"""
    return render_template('logs.html', version=VERSION)

@app.route('/about')
def about():
    """About page"""
    return render_template('about.html', version=VERSION)

@app.route('/api/logs/<source>')
def get_logs(source):
    """Fetch logs from various sources"""
    try:
        if source == 'ultrafeeder':
            # Get ultrafeeder logs from docker
            result = subprocess.run(['docker', 'logs', '--tail', '500', 'ultrafeeder'],
                                  capture_output=True, text=True, timeout=10)
            logs = result.stdout + result.stderr
            
        elif source == 'tailscale':
            # Get tailscale logs from journalctl
            result = subprocess.run(['journalctl', '-u', 'tailscaled', '-n', '500', '--no-pager'],
                                  capture_output=True, text=True, timeout=10)
            logs = result.stdout
            
        elif source == 'vnstat':
            # Get vnstat hour and day reports
            hour_result = subprocess.run(['vnstat', '-h'],
                                       capture_output=True, text=True, timeout=10)
            day_result = subprocess.run(['vnstat', '-d'],
                                      capture_output=True, text=True, timeout=10)
            logs = "=== HOURLY REPORT ===\n" + hour_result.stdout + "\n\n=== DAILY REPORT ===\n" + day_result.stdout
            
        else:
            return jsonify({'success': False, 'message': f'Unknown log source: {source}'})
        
        if not logs or logs.strip() == '':
            logs = f'No logs available for {source}'
        
        return jsonify({'success': True, 'logs': logs})
        
    except subprocess.TimeoutExpired:
        return jsonify({'success': False, 'message': 'Timeout while fetching logs'})
    except FileNotFoundError:
        return jsonify({'success': False, 'message': f'Service {source} not found or not installed'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/feeds/toggle', methods=['POST'])
def api_feeds_toggle():
    """Toggle feed on/off"""
    try:
        data = request.json
        feed_name = data.get('feed')
        enabled = data.get('enabled', False)
        
        # Map feed names to env variables
        feed_map = {
            'taknet': 'TAKNET_PS_ENABLED',
            'airplaneslive': 'AIRPLANESLIVE_ENABLED',
            'adsbfi': 'ADSBFI_ENABLED',
            'adsblol': 'ADSBLOL_ENABLED',
            'adsbexchange': 'ADSBX_ENABLED'
        }
        
        if feed_name not in feed_map:
            return jsonify({'success': False, 'message': 'Unknown feed'})
        
        env_var = feed_map[feed_name]
        value = 'true' if enabled else 'false'
        
        # Update .env file
        update_env_var(env_var, value)
        
        # For feeds that need UUID (adsb.lol, ADSBexchange), ensure UUID exists
        if feed_name in ['adsblol', 'adsbexchange'] and enabled:
            get_or_create_feeder_uuid()
        
        # Regenerate docker-compose.yml with updated feed configuration
        try:
            subprocess.run(
                ['python3', '/opt/adsb/scripts/config_builder.py'],
                cwd='/opt/adsb/config',
                timeout=30,
                check=True,
                capture_output=True
            )
        except subprocess.CalledProcessError as e:
            return jsonify({
                'success': False, 
                'message': f'Failed to regenerate config: {e.stderr.decode()}'
            })
        
        # Restart ultrafeeder with updated configuration
        try:
            subprocess.run(['docker', 'compose', 'up', '-d', 'ultrafeeder'], 
                         cwd='/opt/adsb/config',
                         timeout=30, 
                         check=True)
        except:
            pass  # Continue even if restart fails
        
        return jsonify({'success': True, 'message': f'Feed {feed_name} updated'})
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/feeds/fr24/setup', methods=['POST'])
def api_fr24_setup():
    """Setup FR24 feeder with existing key"""
    try:
        data = request.json
        feeder_id = data.get('feeder_id', '').strip()
        
        if not feeder_id:
            return jsonify({'success': False, 'message': 'Feeder ID is required'})
        
        # Update .env with FR24 key
        update_env_var('FR24_KEY', feeder_id)
        update_env_var('FR24_ENABLED', 'true')
        
        # Start FR24 container using docker compose
        # Use the correct paths - config is at /opt/adsb not /opt/taknet-ps
        compose_file = '/opt/adsb/config/docker-compose.yml'
        env_file = str(ENV_FILE)  # This is /opt/adsb/config/.env
        
        # Verify files exist before attempting docker compose
        if not Path(compose_file).exists():
            return jsonify({
                'success': False,
                'message': f'docker-compose.yml not found at: {compose_file}\n\nPlease run the installer to create the docker-compose.yml file.'
            })
        
        if not ENV_FILE.exists():
            return jsonify({
                'success': False,
                'message': f'.env file not found at: {env_file}\n\nPlease run the installer to create the .env file.'
            })
        
        result = subprocess.run(
            ['docker', 'compose', '-f', compose_file, '--env-file', env_file, 'up', '-d', 'fr24'],
            capture_output=True, text=True, timeout=60
        )
        
        if result.returncode == 0:
            return jsonify({'success': True, 'message': 'FR24 feed enabled successfully'})
        else:
            return jsonify({'success': False, 'message': f'Failed to start FR24: {result.stderr}'})
        
    except subprocess.TimeoutExpired:
        return jsonify({'success': False, 'message': 'Operation timed out'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/feeds/fr24/test', methods=['POST'])
def api_fr24_test():
    """Test FR24 key validity"""
    try:
        data = request.json
        feeder_id = data.get('feeder_id', '').strip()
        
        if not feeder_id:
            return jsonify({'success': False, 'message': 'Feeder ID is required'})
        
        # Simple validation - check if key format is reasonable
        if len(feeder_id) < 10:
            return jsonify({'success': False, 'message': 'Feeder ID appears invalid (too short)'})
        
        # Key looks valid
        return jsonify({'success': True, 'message': 'FR24 key format appears valid'})
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/feeds/fr24/register', methods=['POST'])
def api_fr24_register():
    """Register new FR24 account - smart registration with coordinate formatting"""
    try:
        data = request.json
        email = data.get('email', '').strip()
        
        if not email:
            return jsonify({'success': False, 'message': 'Email is required'})
        
        # Validate email format
        import re
        if not re.match(r'^[^\s@]+@[^\s@]+\.[^\s@]+$', email):
            return jsonify({'success': False, 'message': 'Invalid email format'})
        
        # Read current env for location data
        env = read_env()
        lat_str = env.get('FEEDER_LAT', '0')
        lon_str = env.get('FEEDER_LONG', '0')
        alt_ft_str = env.get('FEEDER_ALT_FT', '0')
        
        # Validate we have location data
        try:
            lat = float(lat_str)
            lon = float(lon_str)
            alt_ft = float(alt_ft_str)
        except ValueError:
            return jsonify({
                'success': False,
                'message': 'Invalid feeder location data. Please configure location in Settings first.'
            })
        
        if lat == 0 or lon == 0:
            return jsonify({
                'success': False,
                'message': 'Feeder location not configured. Please set up your location in Settings first.'
            })
        
        # Format coordinates to EXACTLY 4 decimal places (FR24 requirement)
        lat_formatted = f"{lat:.4f}"
        lon_formatted = f"{lon:.4f}"
        alt_formatted = str(int(alt_ft))  # Altitude in feet, no decimals
        
        # Prepare answers for fr24feed --signup
        signup_inputs = f'''{email}

yes
{lat_formatted}
{lon_formatted}
{alt_formatted}
yes
5
ultrafeeder
30005
no
no
'''
        
        # Run fr24feed --signup in Docker container
        docker_cmd = [
            'docker', 'run', '-i', '--rm',
            'ghcr.io/sdr-enthusiasts/docker-flightradar24:latest',
            'fr24feed', '--signup'
        ]
        
        try:
            result = subprocess.run(
                docker_cmd,
                input=signup_inputs,
                capture_output=True,
                text=True,
                timeout=120
            )
            
            output = result.stdout + result.stderr
            
            # Try to extract sharing key FIRST (success case)
            import re
            key_match = re.search(r'sharing key \(([a-zA-Z0-9]+)\)', output)
            
            if key_match:
                # SUCCESS: Key found and extracted
                sharing_key = key_match.group(1)
                return jsonify({
                    'success': True,
                    'sharing_key': sharing_key,
                    'message': f'Registration successful! Your sharing key: {sharing_key}'
                })
            
            # If we get here, no key was extracted
            # Check for CLEAR FAILURE indicators
            
            # ERROR 1: Three-key limit reached
            if 'limit' in output.lower() or 'maximum' in output.lower() or ('three' in output.lower() and 'feeder' in output.lower()):
                return jsonify({
                    'success': False,
                    'error_type': 'key_limit',
                    'message': f'Your FlightRadar24 account has reached the 3-feeder limit.\n\nTo add this feeder, you need to:\n1. Log in to your FR24 account with: {email}\n2. Remove an old feeder or request additional keys from FR24 support\n3. Copy your sharing key and paste it in the field above',
                    'url': 'https://www.flightradar24.com/account/data-sharing',
                    'email': email,
                    'debug_output': output[:1000]
                })
            
            # ERROR 2: Clear failure messages
            clear_failures = [
                'connection refused' in output.lower(),
                'network unreachable' in output.lower(),
                'could not connect' in output.lower(),
                'timeout' in output.lower() and 'error' in output.lower()
            ]
            
            if any(clear_failures):
                return jsonify({
                    'success': False,
                    'error_type': 'network_error',
                    'message': f'Network error during registration.\n\nYou can register manually:\n1. Log in or create account with: {email}\n2. Complete the FR24 feeder registration\n3. Copy your sharing key and paste it in the field above',
                    'url': 'https://www.flightradar24.com/share-your-data',
                    'email': email,
                    'debug_output': output[:1000]
                })
            
            # DEFAULT: Assume registration succeeded but we couldn't extract the key
            # This is the "fail-open" approach - better to assume success and let user verify
            return jsonify({
                'success': False,
                'error_type': 'key_extraction_failed',
                'message': f'We couldn\'t automatically retrieve your sharing key.\n\nNext steps:\n1. Log in with: {email}\n2. Copy your sharing key\n3. Paste it in the field above and click "Save & Enable FR24"',
                'url': 'https://www.flightradar24.com/account/data-sharing',
                'email': email,
                'registration_successful': True,
                'debug_output': output[:1000]
            })
                
        except subprocess.TimeoutExpired:
            return jsonify({
                'success': False,
                'error_type': 'timeout',
                'message': f'Registration process timed out (took over 2 minutes).\n\nThe registration may have completed successfully.\n\nNext steps:\n1. Log in to your FR24 account with: {email}\n2. Check if your feeder was registered\n3. If yes, copy your sharing key and paste it above',
                'url': 'https://www.flightradar24.com/account/data-sharing',
                'email': email
            })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error_type': 'exception',
            'message': f'Unexpected error during registration: {str(e)}\n\nYou can register manually:\n1. Visit the FR24 registration page (link below)\n2. Complete registration with your email\n3. Copy your sharing key and paste it above',
            'url': 'https://www.flightradar24.com/share-your-data'
        })

@app.route('/api/feeds/fr24/status', methods=['GET'])
def api_fr24_status():
    """Get FR24 feed enabled/disabled status"""
    try:
        env = read_env()
        enabled = env.get('FR24_ENABLED', 'false').lower() == 'true'
        
        return jsonify({
            'success': True,
            'enabled': enabled
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/feeds/fr24/toggle', methods=['POST'])
def api_fr24_toggle():
    """Toggle FR24 feed enabled/disabled"""
    try:
        data = request.json
        enabled = data.get('enabled', False)
        
        # Update .env
        update_env_var('FR24_ENABLED', 'true' if enabled else 'false')
        
        # Use the correct paths - config is at /opt/adsb not /opt/taknet-ps
        compose_file = '/opt/adsb/config/docker-compose.yml'
        env_file = str(ENV_FILE)  # This is /opt/adsb/config/.env
        
        # Verify files exist before attempting docker compose
        if not Path(compose_file).exists():
            return jsonify({
                'success': False,
                'message': f'docker-compose.yml not found at: {compose_file}\n\nPlease run the installer to create the docker-compose.yml file.'
            })
        
        if not ENV_FILE.exists():
            return jsonify({
                'success': False,
                'message': f'.env file not found at: {env_file}\n\nPlease run the installer to create the .env file.'
            })
        
        # Start or stop FR24 container using docker compose
        if enabled:
            result = subprocess.run(
                ['docker', 'compose', '-f', compose_file, '--env-file', env_file, 'up', '-d', 'fr24'],
                capture_output=True, text=True, timeout=60
            )
        else:
            result = subprocess.run(
                ['docker', 'compose', '-f', compose_file, 'stop', 'fr24'],
                capture_output=True, text=True, timeout=30
            )
        
        if result.returncode == 0:
            return jsonify({'success': True, 'message': f'FR24 feed {"enabled" if enabled else "disabled"}'})
        else:
            return jsonify({'success': False, 'message': f'Failed: {result.stderr}'})
        
    except subprocess.TimeoutExpired:
        return jsonify({'success': False, 'message': 'Operation timed out'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/feeds/piaware/setup', methods=['POST'])
def api_piaware_setup():
    """Setup PiAware feeder - smart detection: generate new ID or use existing"""
    try:
        data = request.json
        feeder_id_input = data.get('feeder_id', '').strip()
        
        # SMART DETECTION: Check if user provided a feeder ID
        if feeder_id_input:
            # User provided an existing feeder ID - use it directly
            # Validate UUID format (loose validation)
            import re
            if not re.match(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', feeder_id_input, re.IGNORECASE):
                return jsonify({
                    'success': False,
                    'message': 'Invalid FlightAware Feeder ID format. Should be UUID format like: c478b1c9-23d3-4376-1f82-47352a28cg37'
                })
            
            # Save feeder ID and enable
            update_env_var('PIAWARE_FEEDER_ID', feeder_id_input)
            update_env_var('PIAWARE_ENABLED', 'true')
            
            # Start PiAware container
            compose_file = '/opt/adsb/config/docker-compose.yml'
            env_file = str(ENV_FILE)
            
            # Verify files exist
            if not Path(compose_file).exists():
                return jsonify({
                    'success': False,
                    'message': f'docker-compose.yml not found at: {compose_file}\n\nPlease run the installer to create the docker-compose.yml file.'
                })
            
            if not ENV_FILE.exists():
                return jsonify({
                    'success': False,
                    'message': f'.env file not found at: {env_file}\n\nPlease run the installer to create the .env file.'
                })
            
            result = subprocess.run(
                ['docker', 'compose', '-f', compose_file, '--env-file', env_file, 'up', '-d', 'piaware'],
                capture_output=True, text=True, timeout=60
            )
            
            if result.returncode == 0:
                return jsonify({
                    'success': True,
                    'message': 'FlightAware feed configured successfully! Container is starting...',
                    'feeder_id': feeder_id_input,
                    'mode': 'existing'
                })
            else:
                return jsonify({
                    'success': False,
                    'message': f'Failed to start PiAware: {result.stderr}'
                })
        
        else:
            # No feeder ID provided - GENERATE NEW ONE
            # Run PiAware container temporarily to get a new feeder ID
            
            # Read location from env
            env = read_env()
            lat = env.get('FEEDER_LAT', '0')
            lon = env.get('FEEDER_LONG', '0')
            
            try:
                # v2.40.5: Real-time streaming implementation (like adsb.im method)
                # Use Popen to stream output line-by-line and exit early when ID found
                # This matches the official method: timeout 60 docker run ... | grep "my feeder ID"
                import re
                import time
                
                docker_cmd = [
                    'docker', 'run', '--rm',
                    '-e', f'LAT={lat}',
                    '-e', f'LONG={lon}',
                    'ghcr.io/sdr-enthusiasts/docker-piaware:latest'
                ]
                
                # Start process with line-buffered output
                process = subprocess.Popen(
                    docker_cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,  # Line buffered
                    universal_newlines=True
                )
                
                start_time = time.time()
                timeout = 90  # Reduced from 120 to 90 seconds (adsb.im uses 60)
                feeder_id = None
                full_output = []
                
                # Pattern to match feeder ID
                id_pattern = re.compile(r'my feeder[- ]?id is ([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})', re.IGNORECASE)
                
                # Read output line by line in real-time
                while True:
                    # Check timeout
                    if time.time() - start_time > timeout:
                        process.kill()
                        process.wait()
                        raise subprocess.TimeoutExpired(docker_cmd, timeout)
                    
                    # Read next line (with timeout)
                    line = process.stdout.readline()
                    
                    if not line:
                        # Process ended
                        break
                    
                    full_output.append(line)
                    
                    # Check for feeder ID in this line
                    match = id_pattern.search(line)
                    if match:
                        feeder_id = match.group(1)
                        # Found it! Kill the container immediately (like grep does)
                        process.kill()
                        process.wait()
                        break
                
                # Wait for process to complete (if it hasn't been killed already)
                if process.poll() is None:
                    process.wait(timeout=5)
                
                if feeder_id:
                    # Success! Got the ID
                    elapsed = time.time() - start_time
                    return jsonify({
                        'success': True,
                        'feeder_id': feeder_id,
                        'mode': 'generated',
                        'message': f'New FlightAware Feeder ID generated in {int(elapsed)} seconds: {feeder_id}',
                        'next_steps': [
                            f'Your new Feeder ID: {feeder_id}',
                            'Claim this feeder at FlightAware (link below)',
                            'Come back and enter the Feeder ID above',
                            'Click "Save & Enable FlightAware"'
                        ],
                        'claim_url': f'https://flightaware.com/adsb/piaware/claim/{feeder_id}'
                    })
                else:
                    # Failed to extract ID
                    output_str = ''.join(full_output)
                    return jsonify({
                        'success': False,
                        'error_type': 'id_extraction_failed',
                        'message': 'Could not generate Feeder ID. Please try again or get one manually from FlightAware.',
                        'url': 'https://flightaware.com/adsb/piaware/claim',
                        'debug_output': output_str[:1000] if output_str else 'No output captured'
                    })
                    
            except subprocess.TimeoutExpired:
                return jsonify({
                    'success': False,
                    'error_type': 'timeout',
                    'message': 'Timeout while generating Feeder ID (took longer than 90 seconds). This can happen if Docker image is downloading (~500MB, 5-10 min) or network is slow. Please wait for download to complete and try again.',
                    'url': 'https://flightaware.com/adsb/piaware/claim',
                    'manual_method': [
                        'Check if image is downloading: docker images | grep piaware',
                        'Or run manually: cd /tmp && bash generate-piaware-feederid.sh',
                        'Or get ID from FlightAware website (link above)'
                    ]
                })
            except Exception as e:
                return jsonify({
                    'success': False,
                    'error_type': 'exception',
                    'message': f'Error generating Feeder ID: {str(e)}',
                    'url': 'https://flightaware.com/adsb/piaware/claim'
                })
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/feeds/piaware/status', methods=['GET'])
def api_piaware_status():
    """Get FlightAware/PiAware feed enabled/disabled status"""
    try:
        env = read_env()
        enabled = env.get('PIAWARE_ENABLED', 'false').lower() == 'true'
        
        return jsonify({
            'success': True,
            'enabled': enabled
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/feeds/piaware/toggle', methods=['POST'])
def api_piaware_toggle():
    """Toggle PiAware feed enabled/disabled"""
    try:
        data = request.json
        enabled = data.get('enabled', False)
        
        # Update .env
        update_env_var('PIAWARE_ENABLED', 'true' if enabled else 'false')
        
        # Use the correct paths
        compose_file = '/opt/adsb/config/docker-compose.yml'
        env_file = str(ENV_FILE)
        
        # Verify files exist
        if not Path(compose_file).exists():
            return jsonify({
                'success': False,
                'message': f'docker-compose.yml not found at: {compose_file}\n\nPlease run the installer to create the docker-compose.yml file.'
            })
        
        if not ENV_FILE.exists():
            return jsonify({
                'success': False,
                'message': f'.env file not found at: {env_file}\n\nPlease run the installer to create the .env file.'
            })
        
        # Start or stop PiAware container using docker compose
        if enabled:
            result = subprocess.run(
                ['docker', 'compose', '-f', compose_file, '--env-file', env_file, 'up', '-d', 'piaware'],
                capture_output=True, text=True, timeout=60
            )
        else:
            result = subprocess.run(
                ['docker', 'compose', '-f', compose_file, 'stop', 'piaware'],
                capture_output=True, text=True, timeout=30
            )
        
        if result.returncode == 0:
            return jsonify({'success': True, 'message': f'FlightAware feed {"enabled" if enabled else "disabled"}'})
        else:
            return jsonify({'success': False, 'message': f'Failed: {result.stderr}'})
        
    except subprocess.TimeoutExpired:
        return jsonify({'success': False, 'message': 'Operation timed out'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

# ========================================
# ADSBHub Feed API Endpoints
# ========================================

@app.route('/api/feeds/adsbhub/setup', methods=['POST'])
def api_adsbhub_setup():
    """Configure ADSBHub feed with station key"""
    try:
        data = request.json
        station_key = data.get('station_key', '').strip()
        
        if not station_key:
            return jsonify({'success': False, 'message': 'Station key is required'})
        
        # Update .env file
        update_env_var('ADSBHUB_STATION_KEY', station_key)
        update_env_var('ADSBHUB_ENABLED', 'true')
        
        # Use the correct paths
        compose_file = '/opt/adsb/config/docker-compose.yml'
        env_file = str(ENV_FILE)
        
        # Verify files exist
        if not Path(compose_file).exists():
            return jsonify({
                'success': False,
                'message': f'docker-compose.yml not found at: {compose_file}\n\nPlease run the installer to create the docker-compose.yml file.'
            })
        
        if not ENV_FILE.exists():
            return jsonify({
                'success': False,
                'message': f'.env file not found at: {env_file}\n\nPlease run the installer to create the .env file.'
            })
        
        # Start ADSBHub container
        result = subprocess.run(
            ['docker', 'compose', '-f', compose_file, '--env-file', env_file, 'up', '-d', 'adsbhub'],
            capture_output=True, text=True, timeout=60
        )
        
        if result.returncode == 0:
            return jsonify({'success': True, 'message': 'ADSBHub feed configured successfully'})
        else:
            return jsonify({'success': False, 'message': f'Failed to start ADSBHub: {result.stderr}'})
        
    except subprocess.TimeoutExpired:
        return jsonify({'success': False, 'message': 'Operation timed out'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/feeds/adsbhub/status', methods=['GET'])
def api_adsbhub_status():
    """Get ADSBHub feed enabled/disabled status"""
    try:
        env = read_env()
        enabled = env.get('ADSBHUB_ENABLED', 'false').lower() == 'true'
        
        return jsonify({
            'success': True,
            'enabled': enabled
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/feeds/adsbhub/toggle', methods=['POST'])
def api_adsbhub_toggle():
    """Toggle ADSBHub feed enabled/disabled"""
    try:
        data = request.json
        enabled = data.get('enabled', False)
        
        # Update .env
        update_env_var('ADSBHUB_ENABLED', 'true' if enabled else 'false')
        
        # Use the correct paths
        compose_file = '/opt/adsb/config/docker-compose.yml'
        env_file = str(ENV_FILE)
        
        # Verify files exist
        if not Path(compose_file).exists():
            return jsonify({
                'success': False,
                'message': f'docker-compose.yml not found at: {compose_file}\n\nPlease run the installer to create the docker-compose.yml file.'
            })
        
        if not ENV_FILE.exists():
            return jsonify({
                'success': False,
                'message': f'.env file not found at: {env_file}\n\nPlease run the installer to create the .env file.'
            })
        
        # Start or stop ADSBHub container using docker compose
        if enabled:
            result = subprocess.run(
                ['docker', 'compose', '-f', compose_file, '--env-file', env_file, 'up', '-d', 'adsbhub'],
                capture_output=True, text=True, timeout=60
            )
        else:
            result = subprocess.run(
                ['docker', 'compose', '-f', compose_file, 'stop', 'adsbhub'],
                capture_output=True, text=True, timeout=30
            )
        
        if result.returncode == 0:
            return jsonify({'success': True, 'message': f'ADSBHub feed {"enabled" if enabled else "disabled"}'})
        else:
            return jsonify({'success': False, 'message': f'Failed: {result.stderr}'})
        
    except subprocess.TimeoutExpired:
        return jsonify({'success': False, 'message': 'Operation timed out'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/settings')
def settings():
    """Settings page"""
    env = read_env()
    return render_template('settings.html', config=env, version=VERSION)

@app.route('/feeds')
def feeds():
    """Feeds configuration page"""
    env = read_env()
    feeder_uuid = get_or_create_feeder_uuid()
    return render_template('feeds.html', config=env, feeder_uuid=feeder_uuid, version=VERSION)

@app.route('/feeds/account-required')
def feeds_account_required():
    """Account-required feeds configuration page"""
    env = read_env()
    
    # Check FR24 status
    fr24_key = env.get('FR24_KEY', '')
    fr24_enabled = env.get('FR24_ENABLED', 'false') == 'true'
    fr24_status = False
    if fr24_key and fr24_enabled:
        # Check if FR24 container is running
        try:
            result = subprocess.run(['docker', 'ps', '--filter', 'name=fr24', '--format', '{{.Names}}'],
                                  capture_output=True, text=True, timeout=5)
            fr24_status = 'fr24' in result.stdout
        except:
            fr24_status = False
    
    # Check PiAware status
    piaware_feeder_id = env.get('PIAWARE_FEEDER_ID', '')
    piaware_enabled = env.get('PIAWARE_ENABLED', 'false') == 'true'
    piaware_status = False
    if piaware_feeder_id and piaware_enabled:
        # Check if PiAware container is running
        try:
            result = subprocess.run(['docker', 'ps', '--filter', 'name=piaware', '--format', '{{.Names}}'],
                                  capture_output=True, text=True, timeout=5)
            piaware_status = 'piaware' in result.stdout
        except:
            piaware_status = False
    
    # Check ADSBHub status
    adsbhub_key = env.get('ADSBHUB_STATION_KEY', '')
    adsbhub_enabled = env.get('ADSBHUB_ENABLED', 'false') == 'true'
    adsbhub_status = False
    if adsbhub_key and adsbhub_enabled:
        # Check if ADSBHub container is running
        try:
            result = subprocess.run(['docker', 'ps', '--filter', 'name=adsbhub', '--format', '{{.Names}}'],
                                  capture_output=True, text=True, timeout=5)
            adsbhub_status = 'adsbhub' in result.stdout
        except:
            adsbhub_status = False
    
    return render_template('feeds-account-required.html', 
                         fr24_key=fr24_key,
                         fr24_enabled=fr24_enabled,
                         fr24_status=fr24_status,
                         piaware_feeder_id=piaware_feeder_id,
                         piaware_enabled=piaware_enabled,
                         piaware_status=piaware_status,
                         adsbhub_key=adsbhub_key,
                         adsbhub_enabled=adsbhub_enabled,
                         adsbhub_status=adsbhub_status)

# API Endpoints

# SDR Configuration APIs
@app.route('/api/sdr/detect', methods=['GET'])
def api_sdr_detect():
    """Detect connected SDR devices"""
    import re
    try:
        # Run rtl_test to detect devices
        result = subprocess.run(
            ['rtl_test', '-t'],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        output = result.stderr + result.stdout
        devices = []
        
        # Parse output
        device_pattern = r'(\d+):\s+([^,]+),\s+([^,]+),\s+SN:\s+(\S+)'
        matches = re.findall(device_pattern, output)
        
        for match in matches:
            index, manufacturer, product, serial = match
            device = {
                'index': int(index),
                'type': 'rtlsdr',
                'manufacturer': manufacturer.strip(),
                'product': product.strip(),
                'serial': serial.strip(),
                'useFor': '',  # Default empty
                'gain': 'autogain',  # Default
                'biastee': False  # Default
            }
            
            # Check if already configured
            env = read_env()
            device_key = f'SDR_{index}'
            if device_key in env:
                config = env[device_key].split(',')
                if len(config) >= 3:
                    device['useFor'] = config[0]
                    device['gain'] = config[1]
                    device['biastee'] = config[2].lower() == 'true'
            
            devices.append(device)
        
        return jsonify({'success': True, 'devices': devices})
        
    except subprocess.TimeoutExpired:
        return jsonify({'success': False, 'devices': [], 'error': 'Detection timed out'}), 500
    except FileNotFoundError:
        return jsonify({'success': False, 'devices': [], 'error': 'rtl_test not found'}), 500
    except Exception as e:
        return jsonify({'success': False, 'devices': [], 'error': str(e)}), 500

@app.route('/api/sdr/configure', methods=['POST'])
def api_sdr_configure():
    """Save SDR configuration"""
    try:
        data = request.json
        devices = data.get('devices', [])
        
        env = read_env()
        
        # Save each configured device
        for device in devices:
            if device.get('useFor'):
                index = device.get('index')
                use_for = device.get('useFor', '')
                gain = device.get('gain', 'autogain')
                biastee = 'true' if device.get('biastee', False) else 'false'
                
                # Store as SDR_0=1090,autogain,false
                env[f'SDR_{index}'] = f"{use_for},{gain},{biastee}"
                
                # Set primary device (first 1090 device found)
                if use_for == '1090' and 'READSB_DEVICE' not in env:
                    env['READSB_DEVICE'] = str(index)
                    env['READSB_GAIN'] = gain
                    if biastee == 'true':
                        env['READSB_ENABLE_BIASTEE'] = 'ON'
        
        write_env(env)
        return jsonify({'success': True})
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/config', methods=['GET'])
def get_config():
    """Get current configuration"""
    return jsonify(read_env())

@app.route('/api/config', methods=['POST'])
def save_config():
    """
    Save configuration
    CRITICAL: User can only toggle TAKNET_PS_ENABLED, cannot change connection details
    NOTE: Tailscale and FR24 setup are handled by their dedicated endpoints/buttons
    """
    try:
        data = request.json
        env = read_env()
        
        # PROTECT TAK CONNECTION SETTINGS
        # User can only change TAKNET_PS_ENABLED (on/off), nothing else
        tak_protected_keys = ['TAKNET_PS_SERVER_HOST', 'TAKNET_PS_SERVER_HOST_PRIMARY', 
                              'TAKNET_PS_SERVER_HOST_FALLBACK', 'TAKNET_PS_SERVER_PORT', 
                              'TAKNET_PS_CONNECTION_MODE']
        
        # Remove any protected TAK settings from user input
        for key in tak_protected_keys:
            if key in data:
                del data[key]
        
        # Update env with user data (protected TAK settings excluded)
        for key, value in data.items():
            env[key] = str(value)
        
        # Force protected TAK connection settings (always these values)
        for key, value in TAK_PROTECTED_SETTINGS.items():
            env[key] = value
        
        # Write to file
        write_env(env)
        
        # Rebuild ULTRAFEEDER_CONFIG
        rebuild_config()
        
        return jsonify({'success': True, 'message': 'Configuration saved'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/tailscale/install', methods=['POST'])
def api_install_tailscale():
    """Install/update Tailscale with optional auth key and hostname"""
    try:
        data = request.json
        auth_key = data.get('auth_key', None)
        hostname = data.get('hostname', None)
        
        # Reset progress
        global tailscale_progress
        with tailscale_progress_lock:
            tailscale_progress = {
                'status': 'downloading',
                'download_progress': 0,
                'install_progress': 0,
                'register_progress': 0,
                'message': 'Starting installation...',
                'download_bytes': 0,
                'total_bytes': 0,
                'error': None
            }
        
        # Start installation in background thread
        install_thread = threading.Thread(
            target=install_tailscale_with_progress, 
            args=(auth_key, hostname),
            daemon=True
        )
        install_thread.start()
        
        return jsonify({'success': True, 'message': 'Installation started'})
            
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/tailscale/status', methods=['GET'])
def api_tailscale_status():
    """Get Tailscale connection status"""
    try:
        result = get_tailscale_status()
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'status': str(e)}), 500

@app.route('/api/tailscale/progress', methods=['GET'])
def api_tailscale_progress():
    """Get Tailscale installation progress"""
    global tailscale_progress
    with tailscale_progress_lock:
        return jsonify(tailscale_progress)

@app.route('/api/tailscale/enable', methods=['POST'])
def api_tailscale_enable():
    """Enable Tailscale VPN"""
    try:
        env = read_env()
        env['TAILSCALE_ENABLED'] = 'true'
        write_env(env)
        
        # Rebuild config to activate Tailscale connection
        if rebuild_config():
            # Restart ultrafeeder to apply changes
            restart_service()
            return jsonify({'success': True, 'message': 'Tailscale enabled successfully'})
        else:
            return jsonify({'success': False, 'message': 'Failed to rebuild configuration'}), 500
            
    except Exception as e:
        print(f"❌ Error enabling Tailscale: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/tailscale/disable', methods=['POST'])
def api_tailscale_disable():
    """Disable Tailscale VPN"""
    try:
        # Logout from Tailscale (completely disconnect from tailnet)
        try:
            subprocess.run(['tailscale', 'logout'], timeout=10, capture_output=True, check=False)
            print("✓ Tailscale logged out")
        except Exception as e:
            print(f"⚠️ Could not logout from Tailscale: {e}")
        
        # Update config to disable
        env = read_env()
        env['TAILSCALE_ENABLED'] = 'false'
        write_env(env)
        
        # Rebuild config to use public IP fallback
        if rebuild_config():
            # Restart ultrafeeder to apply changes
            restart_service()
            return jsonify({'success': True, 'message': 'Tailscale disabled successfully'})
        else:
            return jsonify({'success': False, 'message': 'Failed to rebuild configuration'}), 500
            
    except Exception as e:
        print(f"❌ Error disabling Tailscale: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': str(e)}), 500

# =============================================================
# Private Tailscale API Endpoints
# =============================================================

@app.route('/api/private-tailscale/status', methods=['GET'])
def api_private_tailscale_status():
    """Get Private Tailscale connection status"""
    try:
        env = read_env()
        enabled = env.get('PRIVATE_TAILSCALE_ENABLED', 'false') == 'true'
        
        if not enabled:
            return jsonify({
                'success': True,
                'enabled': False,
                'connected': False,
                'message': 'Private Tailscale is disabled'
            })
        
        # Check if container is running
        result = subprocess.run(
            ['docker', 'ps', '--filter', 'name=tailscale-private', '--format', '{{.Status}}'],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if result.returncode != 0 or not result.stdout.strip():
            return jsonify({
                'success': True,
                'enabled': True,
                'connected': False,
                'message': 'Container not running'
            })
        
        # Get Tailscale status from container
        status_result = subprocess.run(
            ['docker', 'exec', 'tailscale-private', 'tailscale', 'status', '--json'],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if status_result.returncode == 0:
            status_data = json.loads(status_result.stdout)
            backend_state = status_data.get('BackendState', '')
            connected = backend_state == 'Running'
            
            if connected:
                self_info = status_data.get('Self', {})
                ip = self_info.get('TailscaleIPs', [''])[0] if self_info.get('TailscaleIPs') else None
                hostname = self_info.get('DNSName', '').rstrip('.')
                
                return jsonify({
                    'success': True,
                    'enabled': True,
                    'connected': True,
                    'ip': ip,
                    'hostname': hostname
                })
        
        return jsonify({
            'success': True,
            'enabled': True,
            'connected': False,
            'message': 'Not connected'
        })
        
    except Exception as e:
        print(f"Error checking Private Tailscale status: {e}")
        return jsonify({
            'success': False,
            'enabled': False,
            'connected': False,
            'error': str(e)
        }), 500

@app.route('/api/private-tailscale/enable', methods=['POST'])
def api_private_tailscale_enable():
    """Enable Private Tailscale"""
    try:
        data = request.json
        auth_key = data.get('auth_key')
        hostname = data.get('hostname')
        
        if not auth_key:
            return jsonify({'success': False, 'message': 'Auth key is required'}), 400
        
        # Update environment
        env = read_env()
        env['PRIVATE_TAILSCALE_ENABLED'] = 'true'
        env['PRIVATE_TS_KEY'] = auth_key
        if hostname:
            env['PRIVATE_TS_HOSTNAME'] = hostname
        write_env(env)
        
        # Start Private Tailscale container with profile
        result = subprocess.run(
            ['docker', 'compose', '--profile', 'private-tailscale', 'up', '-d', 'tailscale-private'],
            cwd='/opt/adsb/config',
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode != 0:
            return jsonify({
                'success': False,
                'message': f'Failed to start container: {result.stderr}'
            }), 500
        
        # Wait for container to get IP (up to 10 seconds)
        print("Waiting for Private Tailscale to connect...")
        for i in range(20):
            time.sleep(0.5)
            check_result = subprocess.run(
                ['docker', 'exec', 'tailscale-private', 'tailscale', 'status', '--json'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if check_result.returncode == 0:
                try:
                    status_data = json.loads(check_result.stdout)
                    if status_data.get('BackendState') == 'Running':
                        print("✓ Private Tailscale connected")
                        break
                except:
                    pass
        
        # Configure SSH for dual Tailscale access
        print("Configuring SSH for dual Tailscale access...")
        ssh_result = subprocess.run(
            ['/opt/adsb/configure-ssh-dual-tailscale.sh'],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if ssh_result.returncode == 0:
            print("✓ SSH configured for both Tailscale networks")
            print(ssh_result.stdout)
        else:
            print(f"⚠ SSH configuration warning: {ssh_result.stderr}")
            # Don't fail - container is running, SSH config is optional
        
        return jsonify({
            'success': True,
            'message': 'Private Tailscale enabled and SSH configured'
        })
            
    except Exception as e:
        print(f"Error enabling Private Tailscale: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/private-tailscale/disable', methods=['POST'])
def api_private_tailscale_disable():
    """Disable Private Tailscale"""
    try:
        # Stop and remove container
        subprocess.run(
            ['docker', 'compose', 'stop', 'tailscale-private'],
            cwd='/opt/adsb/config',
            capture_output=True,
            timeout=10
        )
        
        subprocess.run(
            ['docker', 'compose', 'rm', '-f', 'tailscale-private'],
            cwd='/opt/adsb/config',
            capture_output=True,
            timeout=10
        )
        
        # Update environment
        env = read_env()
        env['PRIVATE_TAILSCALE_ENABLED'] = 'false'
        write_env(env)
        
        # Reconfigure SSH to remove private Tailscale listener
        print("Reconfiguring SSH to remove Private Tailscale access...")
        ssh_result = subprocess.run(
            ['/opt/adsb/configure-ssh-dual-tailscale.sh'],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if ssh_result.returncode == 0:
            print("✓ SSH reconfigured - Private Tailscale access removed")
            print(ssh_result.stdout)
        else:
            print(f"⚠ SSH configuration warning: {ssh_result.stderr}")
            # Don't fail - container is stopped, SSH reconfig is cleanup
        
        return jsonify({
            'success': True,
            'message': 'Private Tailscale disabled and SSH reconfigured'
        })
        
    except Exception as e:
        print(f"Error disabling Private Tailscale: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/fr24/activate', methods=['POST'])
def api_activate_fr24():
    """Activate FR24 service - start container and monitor download"""
    try:
        env = read_env()
        
        # Check if FR24 is enabled and has key
        if env.get('FR24_ENABLED') != 'true':
            return jsonify({'success': False, 'message': 'FR24 is not enabled in configuration'}), 400
        
        if not env.get('FR24_SHARING_KEY', '').strip():
            return jsonify({'success': False, 'message': 'FR24 sharing key is not configured'}), 400
        
        # Rebuild config to update docker-compose.yml
        rebuild_config()
        
        # Start FR24 container using docker compose
        subprocess.Popen(
            ['docker', 'compose', '-f', '/opt/adsb/config/docker-compose.yml', 'up', '-d', 'fr24'],
            cwd='/opt/adsb/config',
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        # Start FR24 progress monitoring in background thread
        monitor_thread = threading.Thread(target=monitor_docker_progress, args=('fr24',), daemon=True)
        monitor_thread.start()
        print("✓ Started FR24 container and download monitoring")
        
        return jsonify({'success': True, 'message': 'FR24 service activation started'})
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/service/restart', methods=['POST'])
def api_restart_service():
    """Restart ultrafeeder service"""
    try:
        # Rebuild config first
        config_ok = rebuild_config()
        if not config_ok:
            return jsonify({
                'success': False, 
                'message': 'Configuration rebuild failed. Check logs for details.'
            }), 500
        
        # Restart service
        if restart_service():
            return jsonify({'success': True, 'message': 'Service restarting'})
        else:
            return jsonify({
                'success': False, 
                'message': 'Failed to restart ultrafeeder service. Check journalctl -u ultrafeeder for details.'
            }), 500
    except Exception as e:
        return jsonify({'success': False, 'message': f'Exception: {str(e)}'}), 500

@app.route('/api/service/ready', methods=['GET'])
def api_service_ready():
    """Check if ultrafeeder container is running and ready"""
    try:
        docker_status = get_docker_status()
        
        # Check if ultrafeeder container exists and is running
        ultrafeeder_running = False
        for container_name, status in docker_status.items():
            if 'ultrafeeder' in container_name.lower():
                # Check if status contains "Up" (Docker shows "Up X seconds/minutes")
                if 'Up' in status:
                    ultrafeeder_running = True
                    break
        
        return jsonify({
            'ready': ultrafeeder_running,
            'containers': docker_status
        })
    except Exception as e:
        return jsonify({
            'ready': False,
            'error': str(e)
        }), 500

@app.route('/api/service/progress', methods=['GET'])
def api_service_progress():
    """Get current service installation progress"""
    global service_progress
    with progress_lock:
        return jsonify(service_progress)

@app.route('/api/status', methods=['GET'])
def api_status():
    """Get system status"""
    docker_status = get_docker_status()
    env = read_env()
    
    # Parse ULTRAFEEDER_CONFIG to show active feeds
    config_str = env.get('ULTRAFEEDER_CONFIG', '')
    feeds = []
    if config_str:
        for part in config_str.split(';'):
            if part.startswith('adsb,'):
                parts = part.split(',')
                if len(parts) >= 2:
                    feeds.append(parts[1])  # hostname
    
    # Get service states
    service_states = {
        'ultrafeeder': get_service_state('ultrafeeder'),
        'fr24': get_service_state('fr24') if env.get('FR24_ENABLED') == 'true' else None,
        'piaware': get_service_state('piaware') if env.get('PIAWARE_ENABLED') == 'true' else None,
        'adsbx': get_service_state('adsbx') if env.get('ADSBX_ENABLED') == 'true' else None,
        'adsblol': get_service_state('adsblol') if env.get('ADSBLOL_ENABLED') == 'true' else None
    }
    
    return jsonify({
        'docker': docker_status,
        'feeds': feeds,
        'configured': env.get('FEEDER_LAT', '0.0') != '0.0',
        'service_states': service_states
    })

@app.route('/api/service/<service_name>/state', methods=['GET'])
def api_service_state(service_name):
    """Get state of a specific service"""
    state = get_service_state(service_name)
    return jsonify({
        'service': service_name,
        'state': state
    })

@app.route('/api/service/<service_name>/restart', methods=['POST'])
def api_restart_individual_service(service_name):
    """Restart an individual service (ultrafeeder, fr24, piaware, or tailscale)"""
    try:
        valid_services = ['ultrafeeder', 'fr24', 'piaware', 'tailscale']
        if service_name not in valid_services:
            return jsonify({
                'success': False,
                'message': f'Invalid service name. Must be one of: {", ".join(valid_services)}'
            }), 400
        
        # Rebuild config if restarting ultrafeeder
        if service_name == 'ultrafeeder':
            config_ok = rebuild_config()
            if not config_ok:
                return jsonify({
                    'success': False,
                    'message': 'Configuration rebuild failed. Check logs for details.'
                }), 500
        
        # Restart the service
        result = subprocess.run(
            ['sudo', 'systemctl', 'restart', service_name],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode == 0:
            return jsonify({
                'success': True,
                'message': f'{service_name} service restarted successfully'
            })
        else:
            return jsonify({
                'success': False,
                'message': f'Failed to restart {service_name}: {result.stderr}'
            }), 500
            
    except subprocess.TimeoutExpired:
        return jsonify({
            'success': False,
            'message': f'{service_name} restart timed out'
        }), 500
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Exception: {str(e)}'
        }), 500

@app.route('/api/service/<service_name>/status', methods=['GET'])
def api_service_status(service_name):
    """Check if a service is running"""
    try:
        valid_services = ['ultrafeeder', 'fr24', 'piaware', 'tailscale']
        if service_name not in valid_services:
            return jsonify({
                'success': False,
                'message': f'Invalid service name. Must be one of: {", ".join(valid_services)}'
            }), 400
        
        # Check service status
        result = subprocess.run(
            ['systemctl', 'is-active', service_name],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        is_running = result.returncode == 0 and result.stdout.strip() == 'active'
        
        return jsonify({
            'service': service_name,
            'running': is_running,
            'status': result.stdout.strip()
        })
        
    except Exception as e:
        return jsonify({
            'service': service_name,
            'running': False,
            'error': str(e)
        })

@app.route('/taknet-ps-status')
def taknet_ps_status():
    """TAKNET-PS connection status and statistics page"""
    try:
        return render_template('taknet-ps-status.html')
    except Exception as e:
        print(f"❌ Error rendering taknet-ps-status page: {e}")
        import traceback
        traceback.print_exc()
        return f"Error loading page: {e}", 500

@app.route('/api/taknet-ps/connection', methods=['GET'])
def api_taknet_ps_connection():
    """Get TAKNET-PS connection information"""
    try:
        env = read_env()
        
        # Get Tailscale status
        tailscale_running = False
        tailscale_ip = None
        try:
            result = subprocess.run(['tailscale', 'status', '--json'],
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                status_data = json.loads(result.stdout)
                if status_data.get('BackendState') == 'Running':
                    tailscale_running = True
                    self_info = status_data.get('Self', {})
                    tailscale_ips = self_info.get('TailscaleIPs', [])
                    if tailscale_ips:
                        tailscale_ip = tailscale_ips[0]
        except Exception as e:
            print(f"⚠ Tailscale status check failed: {e}")
            pass
        
        # Determine connection method
        connection_method = 'public_ip'
        connection_host = env.get('TAKNET_PS_SERVER_HOST_FALLBACK', 'adsb.tak-solutions.com')
        
        if tailscale_running:
            connection_method = 'tailscale'
            connection_host = env.get('TAKNET_PS_SERVER_HOST_PRIMARY', 'secure.tak-solutions.com')
        
        return jsonify({
            'success': True,
            'connection_method': connection_method,
            'connection_host': connection_host,
            'tailscale_running': tailscale_running,
            'tailscale_ip': tailscale_ip,
            'mode': env.get('TAKNET_PS_CONNECTION_MODE', 'auto')
        })
        
    except Exception as e:
        print(f"❌ Error in api_taknet_ps_connection: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/taknet-ps/stats', methods=['GET'])
def api_taknet_ps_stats():
    """Get TAKNET-PS feed status by checking ultrafeeder container connections"""
    try:
        env = read_env()
        
        # Get aggregator host based on Tailscale status
        connection_host = env.get('TAKNET_PS_SERVER_HOST_FALLBACK', 'adsb.tak-solutions.com')
        try:
            ts_result = subprocess.run(['tailscale', 'status', '--json'],
                                     capture_output=True, text=True, timeout=5)
            if ts_result.returncode == 0:
                status_data = json.loads(ts_result.stdout)
                if status_data.get('BackendState') == 'Running':
                    connection_host = env.get('TAKNET_PS_SERVER_HOST_PRIMARY', 'secure.tak-solutions.com')
        except:
            pass
        
        # Get ports
        beast_port = env.get('TAKNET_PS_SERVER_PORT', '30004')
        mlat_port = env.get('TAKNET_PS_MLAT_PORT', '30105')
        mlat_enabled = env.get('TAKNET_PS_MLAT_ENABLED') == 'true'
        
        # Check for connections inside the ultrafeeder Docker container
        def check_container_connection(port):
            """Check if ultrafeeder container has connection to aggregator on port"""
            try:
                # First, check if container is running
                container_check = subprocess.run(
                    ['docker', 'ps', '--filter', 'name=ultrafeeder', '--format', '{{.Names}}'],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                
                if 'ultrafeeder' not in container_check.stdout:
                    print("⚠ ultrafeeder container not running")
                    return False
                
                # Check for ESTABLISHED connections inside the container
                result = subprocess.run(
                    ['docker', 'exec', 'ultrafeeder', 'ss', '-tn', 'state', 'established'],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                
                if result.returncode == 0:
                    # Look for connection to our port
                    for line in result.stdout.split('\n'):
                        if f':{port}' in line:
                            # Found a connection on this port
                            print(f"✓ Found connection to port {port}: {line.strip()}")
                            return True
                    print(f"⚠ No connection found to port {port}")
                    return False
                else:
                    print(f"⚠ Failed to check connections in container: {result.stderr}")
                    return False
                    
            except subprocess.TimeoutExpired:
                print(f"⚠ Timeout checking connection to port {port}")
                return False
            except Exception as e:
                print(f"⚠ Error checking connection to port {port}: {e}")
                return False
        
        # Check BEAST connection (data feed)
        data_feed_active = check_container_connection(beast_port)
        
        # Check MLAT connection (only if enabled)
        mlat_active = False
        if mlat_enabled:
            mlat_active = check_container_connection(mlat_port)
        
        return jsonify({
            'success': True,
            'data_feed_active': data_feed_active,
            'mlat_active': mlat_active,
            'mlat_enabled': mlat_enabled,
            'connection_host': connection_host,
            'beast_port': beast_port,
            'mlat_port': mlat_port
        })
        
    except subprocess.TimeoutExpired:
        return jsonify({'success': False, 'error': 'Connection check timed out'}), 504
    except Exception as e:
        print(f"❌ Error in api_taknet_ps_stats: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/network-status', methods=['GET'])
def api_network_status():
    """Get network connectivity status"""
    import socket
    
    def check_internet():
        """Check if internet is accessible"""
        try:
            socket.create_connection(("8.8.8.8", 53), timeout=3)
            return True
        except:
            return False
    
    def get_primary_ip():
        """Get primary IP address"""
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(('8.8.8.8', 80))
            ip = s.getsockname()[0]
        except:
            ip = '127.0.0.1'
        finally:
            s.close()
        return ip
    
    has_internet = check_internet()
    ip_address = get_primary_ip()
    hostname = socket.gethostname()
    
    return jsonify({
        'internet': has_internet,
        'ip_address': ip_address,
        'hostname': hostname
    })

# ========================================
# WiFi Management API Endpoints
# ========================================

@app.route('/api/wifi/scan', methods=['GET'])
def wifi_scan():
    """Scan for available WiFi networks"""
    try:
        # Use nmcli for scanning (newer Raspberry Pi OS)
        result = subprocess.run(
            ['nmcli', '-t', '-f', 'SSID,SIGNAL,SECURITY', 'dev', 'wifi', 'list', '--rescan', 'yes'],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode != 0:
            # Fallback to iwlist if nmcli not available
            result = subprocess.run(
                ['sudo', 'iwlist', 'wlan0', 'scan'],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode != 0:
                return jsonify({'success': False, 'message': 'Failed to scan WiFi networks', 'networks': []})
            
            # Parse iwlist output
            networks = []
            current_network = {}
            
            for line in result.stdout.splitlines():
                line = line.strip()
                
                if 'ESSID:' in line:
                    ssid = line.split('ESSID:')[1].strip('"')
                    if ssid:
                        current_network['ssid'] = ssid
                
                if 'Quality=' in line:
                    quality = line.split('Quality=')[1].split()[0]
                    num, den = quality.split('/')
                    signal = int((int(num) / int(den)) * 100)
                    current_network['signal'] = signal
                
                if 'Encryption key:' in line:
                    has_encryption = 'on' in line.lower()
                    current_network['security'] = 'WPA2' if has_encryption else 'Open'
                
                if current_network and 'ssid' in current_network and 'signal' in current_network:
                    if current_network not in networks:
                        networks.append(current_network.copy())
                    current_network = {}
            
            # Sort by signal strength
            networks.sort(key=lambda x: x.get('signal', 0), reverse=True)
            
            return jsonify({'success': True, 'networks': networks[:20]})  # Top 20
        
        # Parse nmcli output
        networks = []
        seen_ssids = set()
        
        for line in result.stdout.splitlines():
            if not line.strip():
                continue
            
            parts = line.split(':')
            if len(parts) >= 3:
                ssid = parts[0].strip()
                signal = int(parts[1]) if parts[1].isdigit() else 0
                security = parts[2].strip() if parts[2] else 'Open'
                
                # Skip hidden networks and duplicates
                if ssid and ssid != '--' and ssid not in seen_ssids:
                    seen_ssids.add(ssid)
                    networks.append({
                        'ssid': ssid,
                        'signal': signal,
                        'security': security if security else 'Open'
                    })
        
        # Sort by signal strength
        networks.sort(key=lambda x: x['signal'], reverse=True)
        
        return jsonify({'success': True, 'networks': networks[:20]})  # Top 20
    
    except subprocess.TimeoutExpired:
        return jsonify({'success': False, 'message': 'WiFi scan timed out', 'networks': []})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e), 'networks': []})

@app.route('/api/wifi/saved', methods=['GET'])
def wifi_saved():
    """Get list of saved WiFi networks"""
    try:
        # Use nmcli to list saved connections
        result = subprocess.run(
            ['nmcli', '-t', '-f', 'NAME,TYPE,DEVICE', 'connection', 'show'],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode != 0:
            # Fallback: parse wpa_supplicant.conf
            wpa_conf = Path('/etc/wpa_supplicant/wpa_supplicant.conf')
            if not wpa_conf.exists():
                return jsonify({'success': True, 'networks': []})
            
            networks = []
            with open(wpa_conf) as f:
                content = f.read()
                current_network = {}
                
                for line in content.splitlines():
                    line = line.strip()
                    
                    if line.startswith('network={'):
                        current_network = {}
                    elif 'ssid=' in line and '=' in line:
                        ssid = line.split('=', 1)[1].strip('"')
                        current_network['ssid'] = ssid
                    elif 'key_mgmt=' in line:
                        key_mgmt = line.split('=', 1)[1].strip()
                        current_network['security'] = 'WPA2' if key_mgmt != 'NONE' else 'Open'
                    elif line == '}' and current_network:
                        current_network['connected'] = False  # Can't determine from file
                        networks.append(current_network)
                        current_network = {}
            
            return jsonify({'success': True, 'networks': networks})
        
        # Parse nmcli output
        networks = []
        active_device = None
        
        for line in result.stdout.splitlines():
            if not line.strip():
                continue
            
            parts = line.split(':')
            if len(parts) >= 3:
                name = parts[0].strip()
                conn_type = parts[1].strip()
                device = parts[2].strip()
                
                # Only include WiFi connections
                if conn_type == '802-11-wireless' or conn_type == 'wifi':
                    networks.append({
                        'ssid': name,
                        'connected': bool(device and device != '--'),
                        'security': 'WPA2'  # Assume WPA2 for saved networks
                    })
        
        return jsonify({'success': True, 'networks': networks})
    
    except Exception as e:
        return jsonify({'success': False, 'message': str(e), 'networks': []})

@app.route('/api/wifi/add', methods=['POST'])
def wifi_add():
    """Add a new WiFi network configuration"""
    try:
        data = request.json
        ssid = data.get('ssid', '').strip()
        password = data.get('password', '')
        security = data.get('security', 'WPA2')
        save_only = data.get('saveOnly', False)  # For remote setup - don't try to connect
        
        if not ssid:
            return jsonify({'success': False, 'message': 'SSID is required'})
        
        # Try nmcli first
        try:
            if save_only:
                # Just create the connection profile without connecting
                if security == 'OPEN':
                    # Open network (no password)
                    result = subprocess.run(
                        ['sudo', 'nmcli', 'connection', 'add', 
                         'type', 'wifi',
                         'con-name', ssid,
                         'ifname', 'wlan0',
                         'ssid', ssid,
                         '--', 
                         'wifi-sec.key-mgmt', 'none'],
                        capture_output=True,
                        text=True,
                        timeout=10
                    )
                else:
                    # Secured network
                    result = subprocess.run(
                        ['sudo', 'nmcli', 'connection', 'add',
                         'type', 'wifi',
                         'con-name', ssid,
                         'ifname', 'wlan0',
                         'ssid', ssid,
                         '--',
                         'wifi-sec.key-mgmt', 'wpa-psk',
                         'wifi-sec.psk', password],
                        capture_output=True,
                        text=True,
                        timeout=10
                    )
                
                if result.returncode == 0:
                    return jsonify({'success': True, 'message': 'WiFi configuration saved (will connect when in range)'})
                else:
                    # Fall through to wpa_supplicant method
                    raise subprocess.CalledProcessError(result.returncode, result.args)
            else:
                # Try to connect immediately (scan result selection)
                if security == 'OPEN':
                    # Open network (no password)
                    result = subprocess.run(
                        ['sudo', 'nmcli', 'dev', 'wifi', 'connect', ssid],
                        capture_output=True,
                        text=True,
                        timeout=30
                    )
                else:
                    # Secured network
                    result = subprocess.run(
                        ['sudo', 'nmcli', 'dev', 'wifi', 'connect', ssid, 'password', password],
                        capture_output=True,
                        text=True,
                        timeout=30
                    )
                
                if result.returncode == 0:
                    return jsonify({'success': True, 'message': 'Connected to WiFi network successfully!'})
                else:
                    # Parse error message
                    error_msg = result.stderr.strip() if result.stderr else result.stdout.strip()
                    
                    # Make error messages more user-friendly
                    if 'Secrets were required' in error_msg or 'authentication' in error_msg.lower():
                        return jsonify({'success': False, 'message': 'Authentication failed - check your password'})
                    elif 'not found' in error_msg.lower():
                        return jsonify({'success': False, 'message': f'Network "{ssid}" not found - try scanning again'})
                    elif 'timeout' in error_msg.lower():
                        return jsonify({'success': False, 'message': 'Connection timeout - network may be out of range'})
                    else:
                        return jsonify({'success': False, 'message': f'Connection failed: {error_msg[:100] if error_msg else "Unknown error"}'})
        
        except subprocess.TimeoutExpired:
            return jsonify({'success': False, 'message': 'Connection attempt timed out (30s) - network may be weak or out of range'})
        except (FileNotFoundError, subprocess.CalledProcessError):
            # nmcli not available or failed, use wpa_supplicant
            wpa_conf = Path('/etc/wpa_supplicant/wpa_supplicant.conf')
            
            # Create network block
            if security == 'OPEN':
                network_block = f'''
network={{
    ssid="{ssid}"
    key_mgmt=NONE
    priority=1
}}
'''
            else:
                network_block = f'''
network={{
    ssid="{ssid}"
    psk="{password}"
    key_mgmt=WPA-PSK
    priority=1
}}
'''
            
            # Append to wpa_supplicant.conf
            subprocess.run(
                ['sudo', 'bash', '-c', f'echo "{network_block}" >> {wpa_conf}'],
                check=True
            )
            
            # Restart wpa_supplicant
            subprocess.run(['sudo', 'wpa_cli', '-i', 'wlan0', 'reconfigure'], check=True)
            
            if save_only:
                return jsonify({'success': True, 'message': 'WiFi configuration saved (will connect when in range)'})
            else:
                return jsonify({'success': True, 'message': 'WiFi network configured and attempting to connect'})
    
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/wifi/remove', methods=['POST'])
def wifi_remove():
    """Remove a WiFi network configuration"""
    try:
        data = request.json
        ssid = data.get('ssid', '').strip()
        
        if not ssid:
            return jsonify({'success': False, 'message': 'SSID is required'})
        
        # Try nmcli first
        try:
            result = subprocess.run(
                ['sudo', 'nmcli', 'connection', 'delete', ssid],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                return jsonify({'success': True, 'message': 'WiFi network removed successfully'})
            else:
                return jsonify({'success': False, 'message': 'Network not found or could not be removed'})
        
        except FileNotFoundError:
            # nmcli not available, manually edit wpa_supplicant.conf
            wpa_conf = Path('/etc/wpa_supplicant/wpa_supplicant.conf')
            
            if not wpa_conf.exists():
                return jsonify({'success': False, 'message': 'WiFi configuration file not found'})
            
            # Read file
            with open(wpa_conf) as f:
                lines = f.readlines()
            
            # Remove network block for this SSID
            new_lines = []
            in_network_block = False
            skip_block = False
            
            for line in lines:
                if line.strip().startswith('network={'):
                    in_network_block = True
                    skip_block = False
                    temp_block = [line]
                elif in_network_block:
                    temp_block.append(line)
                    
                    if f'ssid="{ssid}"' in line:
                        skip_block = True
                    
                    if line.strip() == '}':
                        in_network_block = False
                        if not skip_block:
                            new_lines.extend(temp_block)
                else:
                    new_lines.append(line)
            
            # Write back
            with open(wpa_conf, 'w') as f:
                f.writelines(new_lines)
            
            # Restart wpa_supplicant
            subprocess.run(['sudo', 'wpa_cli', '-i', 'wlan0', 'reconfigure'])
            
            return jsonify({'success': True, 'message': 'WiFi network removed successfully'})
    
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/wifi/status', methods=['GET'])
def wifi_status():
    """Get WiFi radio status"""
    try:
        # Check if WiFi radio is enabled using nmcli
        result = subprocess.run(
            ['nmcli', 'radio', 'wifi'],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if result.returncode == 0:
            status = result.stdout.strip().lower()
            enabled = status == 'enabled'
            return jsonify({
                'success': True,
                'enabled': enabled,
                'status': status
            })
        else:
            return jsonify({'success': False, 'message': 'Could not check WiFi status'})
    
    except FileNotFoundError:
        return jsonify({'success': False, 'message': 'nmcli not available'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/wifi/enable', methods=['POST'])
def wifi_enable():
    """Enable WiFi radio"""
    try:
        result = subprocess.run(
            ['sudo', 'nmcli', 'radio', 'wifi', 'on'],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode == 0:
            return jsonify({'success': True, 'message': 'WiFi enabled successfully'})
        else:
            return jsonify({'success': False, 'message': 'Failed to enable WiFi'})
    
    except FileNotFoundError:
        return jsonify({'success': False, 'message': 'nmcli not available'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/wifi/disable', methods=['POST'])
def wifi_disable():
    """Disable WiFi radio"""
    try:
        result = subprocess.run(
            ['sudo', 'nmcli', 'radio', 'wifi', 'off'],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode == 0:
            return jsonify({'success': True, 'message': 'WiFi disabled successfully'})
        else:
            return jsonify({'success': False, 'message': 'Failed to disable WiFi'})
    
    except FileNotFoundError:
        return jsonify({'success': False, 'message': 'nmcli not available'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

# ============================================================================
# SYSTEM UPDATE ENDPOINTS
# ============================================================================

@app.route('/api/system/version', methods=['GET'])
def get_system_version():
    """Get current version and check for updates"""
    try:
        # Read current version
        version_file = Path('/opt/adsb/VERSION')
        current_version = 'unknown'
        if version_file.exists():
            current_version = version_file.read_text().strip()
        
        print(f"Current version from file: {current_version}")
        
        # Fetch latest version from GitHub
        repo_url = 'https://raw.githubusercontent.com/cfd2474/TAKNET-PS_ADS-B_Feeder/main/version.json'
        
        try:
            import requests
            response = requests.get(repo_url, timeout=10)
            
            if response.status_code == 200:
                latest_info = response.json()
                latest_version = latest_info.get('version', 'unknown')
                
                print(f"Latest version from GitHub: {latest_version}")
                
                # Compare versions
                update_available = False
                if current_version != 'unknown' and latest_version != 'unknown':
                    try:
                        # Parse version strings (format: X.Y.Z)
                        current_parts = [int(x) for x in current_version.split('.')]
                        latest_parts = [int(x) for x in latest_version.split('.')]
                        
                        # Pad to same length if needed (handle 2.47 vs 2.47.0)
                        while len(current_parts) < len(latest_parts):
                            current_parts.append(0)
                        while len(latest_parts) < len(current_parts):
                            latest_parts.append(0)
                        
                        # Compare major.minor.patch
                        print(f"Comparing: {current_parts} vs {latest_parts}")
                        
                        if latest_parts > current_parts:
                            update_available = True
                            print(f"Update available: {current_version} → {latest_version}")
                        else:
                            print(f"No update needed: current={current_version}, latest={latest_version}")
                    
                    except (ValueError, AttributeError) as e:
                        print(f"Version comparison error: {e}")
                        # If can't parse, do string comparison as fallback
                        update_available = (latest_version != current_version)
                
                return jsonify({
                    'success': True,
                    'current_version': current_version,
                    'latest_version': latest_version,
                    'update_available': update_available,
                    'release_info': latest_info
                })
            else:
                # Couldn't fetch from GitHub
                print(f"GitHub fetch failed: HTTP {response.status_code}")
                return jsonify({
                    'success': True,
                    'current_version': current_version,
                    'latest_version': 'unknown',
                    'update_available': False,
                    'error': 'Could not check for updates'
                })
                
        except Exception as e:
            # Network error or GitHub unavailable
            print(f"Update check error: {e}")
            return jsonify({
                'success': True,
                'current_version': current_version,
                'latest_version': 'unknown',
                'update_available': False,
                'error': f'Update check failed: {str(e)}'
            })
    
    except Exception as e:
        print(f"❌ Error in get_system_version: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/system/update', methods=['POST'])
def trigger_system_update():
    """Trigger system update process"""
    try:
        # Check if update is already running
        update_lock = Path('/tmp/taknet_update.lock')
        if update_lock.exists():
            return jsonify({
                'success': False,
                'message': 'Update already in progress'
            }), 409
        
        # Create lock file
        update_lock.touch()
        
        # Run updater script in background
        updater_script = Path('/opt/adsb/scripts/updater.sh')
        
        if not updater_script.exists():
            update_lock.unlink()
            return jsonify({
                'success': False,
                'message': 'Updater script not found'
            }), 404
        
        # Start update process in background
        # Output will be logged to /tmp/taknet_update.log
        subprocess.Popen(
            ['sudo', 'bash', str(updater_script)],
            stdout=open('/tmp/taknet_update.log', 'w'),
            stderr=subprocess.STDOUT
        )
        
        return jsonify({
            'success': True,
            'message': 'Update started',
            'log_file': '/tmp/taknet_update.log'
        })
    
    except Exception as e:
        # Clean up lock file on error
        if update_lock.exists():
            update_lock.unlink()
        
        print(f"❌ Error in trigger_system_update: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/system/update/status', methods=['GET'])
def get_update_status():
    """Get status of ongoing update"""
    try:
        update_lock = Path('/tmp/taknet_update.lock')
        log_file = Path('/tmp/taknet_update.log')
        
        is_updating = update_lock.exists()
        
        # Read last 50 lines of log
        log_tail = []
        if log_file.exists():
            with open(log_file, 'r') as f:
                log_tail = f.readlines()[-50:]
        
        return jsonify({
            'success': True,
            'is_updating': is_updating,
            'log': ''.join(log_tail)
        })
    
    except Exception as e:
        print(f"❌ Error in get_update_status: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

if __name__ == '__main__':
    # Run on all interfaces, port 5000
    app.run(host='0.0.0.0', port=5000, debug=False)
