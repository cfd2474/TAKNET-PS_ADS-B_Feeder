#!/usr/bin/env python3
"""
TAKNET-PS-ADSB-Feeder Config Builder v2.3
Tactical Awareness Kit Network for Enhanced Tracking – Public Safety
Builds ULTRAFEEDER_CONFIG with TAKNET-PS Server as hardcoded priority
Supports primary/fallback connection modes with automatic configuration repair
"""

import sys
import socket
from pathlib import Path

def read_env(env_file):
    """Read .env file and return as dict"""
    env_vars = {}
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                env_vars[key.strip()] = value.strip()
    return env_vars

def write_env(env_file, env_vars):
    """Write env vars back to .env file"""
    lines = []
    with open(env_file) as f:
        for line in f:
            stripped = line.strip()
            if stripped and not stripped.startswith('#') and '=' in stripped:
                key = stripped.split('=', 1)[0].strip()
                if key in env_vars:
                    lines.append(f"{key}={env_vars[key]}\n")
                else:
                    lines.append(line)
            else:
                lines.append(line)
    
    with open(env_file, 'w') as f:
        f.writelines(lines)

def ensure_taknet_config(env_vars, env_file):
    """
    Ensure TAKNET-PS configuration exists
    Builds missing values automatically to prevent user skip
    Uses FQDNs for automatic Tailscale detection
    Migrates old IP addresses to FQDNs
    Returns: (env_vars, was_repaired)
    """
    required_config = {
        'TAKNET_PS_ENABLED': 'true',
        'TAKNET_PS_SERVER_HOST_PRIMARY': 'secure.tak-solutions.com',
        'TAKNET_PS_SERVER_HOST_FALLBACK': 'adsb.tak-solutions.com',
        'TAKNET_PS_SERVER_PORT': '30004',
        'TAKNET_PS_CONNECTION_MODE': 'auto',
        'TAKNET_PS_MLAT_ENABLED': 'true',
        'TAKNET_PS_MLAT_PORT': '30105'
    }
    
    was_repaired = False
    
    # First pass: add missing keys
    for key, default_value in required_config.items():
        if key not in env_vars or not env_vars[key]:
            print(f"⚠ Missing {key}, auto-configuring: {default_value}")
            env_vars[key] = default_value
            was_repaired = True
    
    # Second pass: migrate old IP values to FQDNs
    ip_migrations = {
        '100.117.34.88': 'secure.tak-solutions.com',
        '104.225.219.254': 'adsb.tak-solutions.com',
        # Legacy domain migrations
        'tailscale.leckliter.net': 'secure.tak-solutions.com',
        'adsb.leckliter.net': 'adsb.tak-solutions.com'
    }
    
    for key in ['TAKNET_PS_SERVER_HOST_PRIMARY', 'TAKNET_PS_SERVER_HOST_FALLBACK']:
        if key in env_vars:
            old_value = env_vars[key]
            if old_value in ip_migrations:
                new_value = ip_migrations[old_value]
                print(f"✓ Migrating {key}: {old_value} → {new_value}")
                env_vars[key] = new_value
                was_repaired = True
    
    # Write back if repaired
    if was_repaired:
        write_env(env_file, env_vars)
        print("✓ TAKNET-PS configuration auto-repaired and saved")
    
    return env_vars, was_repaired

def check_host_reachable(host, port, timeout=2):
    """Check if a host:port is reachable"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((host, int(port)))
        sock.close()
        return result == 0
    except:
        return False

def check_tailscale_running():
    """
    Check if Tailscale is running and connected to TAKNET-PS tailnet
    Returns: (is_running, tailscale_ip)
    """
    import subprocess
    try:
        # Check if tailscale command exists
        result = subprocess.run(['which', 'tailscale'], 
                              capture_output=True, 
                              timeout=2)
        if result.returncode != 0:
            print("⚠ Tailscale: Not installed")
            return (False, None)
        
        # Check tailscale status
        result = subprocess.run(['tailscale', 'status', '--json'], 
                              capture_output=True, 
                              text=True, 
                              timeout=5)
        
        if result.returncode != 0:
            print("⚠ Tailscale: Not running")
            return (False, None)
        
        # Parse JSON output
        import json
        status = json.loads(result.stdout)
        
        # Check if we're connected (BackendState should be "Running")
        backend_state = status.get('BackendState', '')
        if backend_state == 'Running':
            # Get our Tailscale IP and DNS name
            self_info = status.get('Self', {})
            tailscale_ips = self_info.get('TailscaleIPs', [])
            dns_name = self_info.get('DNSName', '').rstrip('.')  # Remove trailing dot
            
            if tailscale_ips:
                # CRITICAL: Verify we're on the TAKNET-PS tailnet
                expected_suffix = 'tail4d77be.ts.net'
                
                if dns_name.endswith(expected_suffix):
                    # Correct tailnet!
                    print(f"✓ Tailscale: Running on TAKNET-PS tailnet ({tailscale_ips[0]})")
                    print(f"  DNS: {dns_name}")
                    return (True, tailscale_ips[0])
                else:
                    # Wrong tailnet - private or different network
                    print(f"❌ Tailscale: Connected to WRONG tailnet!")
                    print(f"   Current: {dns_name}")
                    print(f"   Expected: *.{expected_suffix}")
                    print(f"   This is NOT the TAKNET-PS network.")
                    print(f"   Falling back to public IP connection.")
                    return (False, None)
        
        print(f"⚠ Tailscale: State={backend_state}")
        return (False, None)
        
    except subprocess.TimeoutExpired:
        print("⚠ Tailscale: Check timed out")
        return (False, None)
    except Exception as e:
        print(f"⚠ Tailscale: Check failed: {e}")
        return (False, None)

def select_taknet_host(env_vars):
    """
    Select TAKNET-PS Server host based on Tailscale status
    NEW: Uses FQDNs instead of IPs
    - Tailscale running: secure.tak-solutions.com
    - Tailscale not running: adsb.tak-solutions.com
    Returns: (selected_host, connection_type)
    """
    mode = env_vars.get('TAKNET_PS_CONNECTION_MODE', 'auto').lower()
    primary = env_vars.get('TAKNET_PS_SERVER_HOST_PRIMARY', '').strip()
    fallback = env_vars.get('TAKNET_PS_SERVER_HOST_FALLBACK', '').strip()
    port = env_vars.get('TAKNET_PS_SERVER_PORT', '30004').strip()
    
    # Force modes (for debugging/override)
    if mode == 'primary' and primary:
        print(f"ℹ TAKNET-PS: Forced to primary: {primary}")
        return (primary, 'primary-forced')
    
    if mode == 'fallback' and fallback:
        print(f"ℹ TAKNET-PS: Forced to fallback: {fallback}")
        return (fallback, 'fallback-forced')
    
    # Auto mode - detect Tailscale and select appropriate FQDN
    if mode == 'auto':
        tailscale_running, tailscale_ip = check_tailscale_running()
        
        if tailscale_running:
            # Tailscale is running - use primary (secure.tak-solutions.com)
            print(f"✓ TAKNET-PS: Tailscale active, using primary: {primary}")
            return (primary, 'tailscale-active')
        else:
            # Tailscale is NOT running - use fallback (adsb.tak-solutions.com)
            print(f"⚠ TAKNET-PS: Tailscale inactive, using fallback: {fallback}")
            return (fallback, 'tailscale-inactive')
    
    # Monitor mode (Phase 2) - use primary, external monitor will handle failover
    if mode == 'monitor' and primary:
        print(f"ℹ TAKNET-PS: Monitor mode, using primary: {primary}")
        return (primary, 'monitor-mode')
    
    # Fallback to primary if nothing else works
    if primary:
        return (primary, 'primary-fallback')
    elif fallback:
        return (fallback, 'fallback-only')
    
    return (None, 'disabled')

def build_config(env_vars):
    """Build ULTRAFEEDER_CONFIG string with TAKNET-PS as priority"""
    config_parts = []
    
    # TAKNET-PS Server - ALWAYS FIRST (Priority Feed)
    if env_vars.get('TAKNET_PS_ENABLED', 'true').lower() == 'true':
        taknet_host, connection_type = select_taknet_host(env_vars)
        port = env_vars.get('TAKNET_PS_SERVER_PORT', '30004').strip()
        mlat_port = env_vars.get('TAKNET_PS_MLAT_PORT', '30105').strip()
        
        if taknet_host:
            # Beast feed
            config_parts.append(f"adsb,{taknet_host},{port},beast_reduce_plus_out")
            print(f"✓ TAKNET-PS Beast: {taknet_host}:{port} ({connection_type})")
            
            # MLAT feed (if enabled)
            if env_vars.get('TAKNET_PS_MLAT_ENABLED', 'true').lower() == 'true':
                config_parts.append(f"mlat,{taknet_host},{mlat_port},39001")
                print(f"✓ TAKNET-PS MLAT: {taknet_host}:{mlat_port}")
            else:
                print("ℹ TAKNET-PS MLAT: Disabled")
        else:
            print("✗ TAKNET-PS Server: No valid host configuration found")
    else:
        print("ℹ TAKNET-PS Server: Disabled (not recommended)")
    
    # FlightRadar24 - Uses dedicated container, not ultrafeeder
    # The FR24 container connects directly to ultrafeeder's Beast output
    if env_vars.get('FR24_ENABLED', '').lower() == 'true':
        if env_vars.get('FR24_SHARING_KEY', '').strip():
            print("✓ FlightRadar24 (via dedicated container)")
        else:
            print("⚠ FlightRadar24 enabled but no sharing key provided")
    
    # adsb.fi
    if env_vars.get('ADSBFI_ENABLED', '').lower() == 'true':
        # adsb.fi doesn't strictly require UUID - they can auto-generate
        # but it's better to track your station
        config_parts.append("adsb,feed.adsb.fi,30004,beast_reduce_plus_out")
        config_parts.append("mlat,feed.adsb.fi,31090,39003")
        print("✓ adsb.fi")
    
    # adsb.lol
    if env_vars.get('ADSBLOL_ENABLED', '').lower() == 'true':
        # adsb.lol uses feeder UUID for identification
        feeder_uuid = env_vars.get('FEEDER_UUID', '').strip()
        if feeder_uuid:
            config_parts.append("adsb,feed.adsb.lol,30004,beast_reduce_plus_out")
            config_parts.append("mlat,in.adsb.lol,31090,39001")
            print(f"✓ adsb.lol (UUID: {feeder_uuid[:8]}...)")
        else:
            print("⚠ adsb.lol enabled but no UUID found - skipping")
    
    # ADSBexchange
    if env_vars.get('ADSBX_ENABLED', '').lower() == 'true':
        # ADSBexchange uses FEEDER_UUID for identification
        feeder_uuid = env_vars.get('FEEDER_UUID', '').strip()
        if feeder_uuid:
            config_parts.append(f"adsb,feed1.adsbexchange.com,30004,beast_reduce_plus_out,uuid={feeder_uuid}")
            config_parts.append(f"mlat,feed.adsbexchange.com,31090,39004,uuid={feeder_uuid}")
            print(f"✓ ADSBexchange (UUID: {feeder_uuid[:8]}...)")
        else:
            print("⚠ ADSBexchange enabled but no UUID found - skipping")
    
    # Airplanes.Live (no UUID required - they identify by IP address)
    if env_vars.get('AIRPLANESLIVE_ENABLED', '').lower() == 'true':
        config_parts.append("adsb,feed.airplanes.live,30004,beast_reduce_plus_out")
        config_parts.append("mlat,feed.airplanes.live,31090,39002")
        print("✓ Airplanes.Live")
    
    return ';'.join(config_parts)

def build_docker_compose(env_vars):
    """Build docker-compose.yml with conditional FR24 service"""
    compose = {
        'networks': {
            'adsb_net': {'driver': 'bridge'}
        },
        'services': {
            'ultrafeeder': {
                'image': 'ghcr.io/sdr-enthusiasts/docker-adsb-ultrafeeder:latest',
                'container_name': 'ultrafeeder',
                'hostname': 'ultrafeeder',
                'restart': 'unless-stopped',
                'networks': ['adsb_net'],
                'ports': ['8080:80', '9273-9274:9273-9274'],
                'environment': [
                    'TZ=${FEEDER_TZ:-UTC}',
                    'LAT=${FEEDER_LAT}',
                    'LONG=${FEEDER_LONG}',
                    'ALT=${FEEDER_ALT_M}m',
                    'UUID=${FEEDER_UUID}',
                    'READSB_DEVICE_TYPE=rtlsdr',
                    'READSB_RTLSDR_DEVICE=${READSB_DEVICE:-0}',
                    'READSB_GAIN=${READSB_GAIN:-autogain}',
                    'READSB_RX_LOCATION_ACCURACY=2',
                    'READSB_STATS_RANGE=true',
                    'MLAT_USER=${MLAT_SITE_NAME:-feeder}',
                    'UPDATE_TAR1090=true',
                    'TAR1090_ENABLE_AC_DB=true',
                    'TAR1090_FLIGHTAWARELINKS=true',
                    'TAR1090_SITESHOW=true',
                    'ULTRAFEEDER_CONFIG=${ULTRAFEEDER_CONFIG}',
                    'PROMETHEUS_ENABLE=true'
                ],
                'devices': ['/dev/bus/usb:/dev/bus/usb'],
                'volumes': [
                    '/opt/adsb/ultrafeeder:/opt/adsb',
                    '/run/readsb:/run/readsb',
                    '/proc/diskstats:/proc/diskstats:ro'
                ],
                'tmpfs': [
                    '/run:exec,size=256M',
                    '/tmp:size=128M'
                ]
            }
        }
    }
    
    # Always include FR24 service (can be started/stopped via docker compose)
    compose['services']['fr24'] = {
        'image': 'ghcr.io/sdr-enthusiasts/docker-flightradar24:latest',
        'container_name': 'fr24',
        'hostname': 'fr24',
        'restart': 'unless-stopped',
        'networks': ['adsb_net'],
        'depends_on': ['ultrafeeder'],
        'ports': ['8754:8754'],
        'environment': [
            'BEASTHOST=ultrafeeder',
            'BEASTPORT=30005',
            'FR24KEY=${FR24_KEY}',
            'MLAT=yes'
        ],
        'tmpfs': ['/var/log']
    }
    
    # Always include PiAware service (can be started/stopped via docker compose)
    compose['services']['piaware'] = {
        'image': 'ghcr.io/sdr-enthusiasts/docker-piaware:latest',
        'container_name': 'piaware',
        'hostname': 'piaware',
        'restart': 'unless-stopped',
        'networks': ['adsb_net'],
        'depends_on': ['ultrafeeder'],
        'ports': ['8082:80'],
        'environment': [
            'TZ=${FEEDER_TZ}',
            'FEEDER_ID=${PIAWARE_FEEDER_ID}',
            'RECEIVER_TYPE=relay',
            'BEASTHOST=ultrafeeder',
            'BEASTPORT=30005',
            'ALLOW_MLAT=yes',
            'MLAT_RESULTS=yes'
        ],
        'tmpfs': [
            '/run:exec,size=64M',
            '/var/log'
        ]
    }
    
    # Always include ADSBHub service (can be started/stopped via docker compose)
    compose['services']['adsbhub'] = {
        'image': 'ghcr.io/sdr-enthusiasts/docker-adsbhub:latest',
        'container_name': 'adsbhub',
        'hostname': 'adsbhub',
        'restart': 'unless-stopped',
        'networks': ['adsb_net'],
        'depends_on': ['ultrafeeder'],
        'environment': [
            'TZ=${FEEDER_TZ}',
            'SBSHOST=ultrafeeder',
            'CLIENTKEY=${ADSBHUB_STATION_KEY}'
        ]
    }
    
    return compose

def write_docker_compose(compose_dict, compose_file):
    """Write docker-compose.yml from dict"""
    import yaml
    with open(compose_file, 'w') as f:
        yaml.dump(compose_dict, f, default_flow_style=False, sort_keys=False)

def main():
    env_file = Path("/opt/adsb/config/.env")
    
    if not env_file.exists():
        print(f"✗ Error: {env_file} not found")
        sys.exit(1)
    
    # Read environment
    env_vars = read_env(env_file)
    
    # Ensure TAKNET-PS config exists (auto-repair if missing)
    env_vars, was_repaired = ensure_taknet_config(env_vars, env_file)
    
    # Build config
    config_str = build_config(env_vars)
    
    # Update ULTRAFEEDER_CONFIG
    env_vars['ULTRAFEEDER_CONFIG'] = config_str
    
    # Write back to .env
    write_env(env_file, env_vars)
    
    # Build and write docker-compose.yml
    compose_dict = build_docker_compose(env_vars)
    compose_file = Path("/opt/adsb/config/docker-compose.yml")
    write_docker_compose(compose_dict, compose_file)
    
    print(f"\n✓ Configuration built successfully")
    if was_repaired:
        print("✓ Missing TAKNET-PS settings were automatically configured")
    print(f"Active feeds: {len(config_str.split(';')) if config_str else 0}")

if __name__ == "__main__":
    main()
