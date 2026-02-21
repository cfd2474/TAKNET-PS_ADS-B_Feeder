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

# Phase B: Valid gain values per driver type
VALID_GAINS = {
    'rtlsdr': [
        'autogain', '0.0', '0.9', '1.4', '2.7', '3.7', '7.7', '8.7',
        '12.5', '14.4', '15.7', '16.6', '19.7', '20.7', '22.9',
        '25.4', '28.0', '29.7', '32.8', '33.8', '36.4', '37.2',
        '38.6', '40.2', '42.1', '43.4', '43.9', '44.5', '48.0', '49.6'
    ],
    'airspy': ['0', '3', '6', '9', '12', '15', '18', '21'],
    'hackrf': ['0', '8', '16', '24', '32', '40', '48'],
    'ftdi': ['autogain']  # N/A for FTDI
}

# Recommended gain defaults per driver
RECOMMENDED_GAINS = {
    'rtlsdr': 'autogain',
    'airspy': '21',      # Maximum sensitivity
    'hackrf': '40',      # High gain
    'ftdi': 'autogain'
}

def validate_gain(driver, gain):
    """Validate gain value for specific driver"""
    if driver not in VALID_GAINS:
        print(f"[WARNING] Unknown driver '{driver}', accepting gain '{gain}'")
        return gain
    
    valid = VALID_GAINS[driver]
    
    # Check if gain is valid
    if gain in valid:
        return gain
    
    # For numeric gains, try to match closest valid value
    try:
        gain_float = float(gain)
        valid_floats = [float(g) for g in valid if g != 'autogain']
        if valid_floats:
            closest = min(valid_floats, key=lambda x: abs(x - gain_float))
            print(f"[WARNING] Gain {gain} not valid for {driver}, using closest: {closest}")
            return str(closest)
    except ValueError:
        pass
    
    # Fall back to recommended default
    default = RECOMMENDED_GAINS.get(driver, 'autogain')
    print(f"[WARNING] Invalid gain '{gain}' for {driver}, using default: {default}")
    return default

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
        'TAKNET_PS_SERVER_HOST_VPN': 'vpn.tak-solutions.com',
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

    # Migrate old PRIMARY key → VPN key
    if 'TAKNET_PS_SERVER_HOST_PRIMARY' in env_vars and 'TAKNET_PS_SERVER_HOST_VPN' not in env_vars:
        env_vars['TAKNET_PS_SERVER_HOST_VPN'] = 'vpn.tak-solutions.com'
        del env_vars['TAKNET_PS_SERVER_HOST_PRIMARY']
        was_repaired = True
    
    # Second pass: migrate old IP/domain values to current FQDNs
    ip_migrations = {
        '100.117.34.88': 'vpn.tak-solutions.com',
        '104.225.219.254': 'adsb.tak-solutions.com',
        'tailscale.leckliter.net': 'vpn.tak-solutions.com',
        'adsb.leckliter.net': 'adsb.tak-solutions.com',
        'secure.tak-solutions.com': 'vpn.tak-solutions.com',
    }
    
    for key in ['TAKNET_PS_SERVER_HOST_VPN', 'TAKNET_PS_SERVER_HOST_FALLBACK']:
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

def check_netbird_running():
    """
    Check if NetBird is running and connected.
    Returns: (is_running, netbird_ip)
    """
    import subprocess
    try:
        result = subprocess.run(['which', 'netbird'],
                              capture_output=True, timeout=2)
        if result.returncode != 0:
            print("⚠ NetBird: Not installed")
            return (False, None)

        connected = False
        nb_ip = None

        # Try JSON first
        result = subprocess.run(['netbird', 'status', '--json'],
                              capture_output=True, text=True, timeout=5)
        if result.returncode == 0 and result.stdout.strip():
            try:
                import json
                status = json.loads(result.stdout)
                mgmt = status.get('managementState', status.get('management', {}))
                if isinstance(mgmt, dict):
                    connected = mgmt.get('connected', False)
                elif isinstance(mgmt, str):
                    connected = mgmt.lower() == 'connected'
                nb_ip = (status.get('netbirdIp') or
                         status.get('localPeerState', {}).get('ip') or
                         status.get('ip'))
                if nb_ip and '/' in nb_ip:
                    nb_ip = nb_ip.split('/')[0]
            except Exception:
                pass

        # Plain-text fallback
        if not connected:
            plain = subprocess.run(['netbird', 'status'],
                                 capture_output=True, text=True, timeout=5)
            if plain.returncode == 0:
                output = plain.stdout
                connected = 'Management: Connected' in output
                if connected and not nb_ip:
                    for line in output.splitlines():
                        if 'NetBird IP:' in line:
                            nb_ip = line.split('NetBird IP:')[-1].strip().split('/')[0]
                            break

        # Interface fallback
        if not connected:
            iface = subprocess.run(['ip', 'addr', 'show', 'wt0'],
                                 capture_output=True, text=True, timeout=3)
            if iface.returncode == 0 and 'inet ' in iface.stdout:
                connected = True
                if not nb_ip:
                    for line in iface.stdout.splitlines():
                        line = line.strip()
                        if line.startswith('inet '):
                            nb_ip = line.split()[1].split('/')[0]
                            break

        if connected:
            print(f"✓ NetBird: Connected ({nb_ip or 'IP unknown'})")
            return (True, nb_ip)

        print("⚠ NetBird: Not connected")
        return (False, None)

    except subprocess.TimeoutExpired:
        print("⚠ NetBird: Check timed out")
        return (False, None)
    except Exception as e:
        print(f"⚠ NetBird: Check failed: {e}")
        return (False, None)


def check_tailscale_running():
    """
    Check if Tailscale is running and connected to TAKNET-PS tailnet.
    Used as secondary VPN fallback if NetBird is not active.
    Returns: (is_running, tailscale_ip)
    """
    import subprocess
    try:
        result = subprocess.run(['which', 'tailscale'],
                              capture_output=True, timeout=2)
        if result.returncode != 0:
            return (False, None)

        result = subprocess.run(['tailscale', 'status', '--json'],
                              capture_output=True, text=True, timeout=5)
        if result.returncode != 0:
            return (False, None)

        import json
        status = json.loads(result.stdout)
        backend_state = status.get('BackendState', '')

        if backend_state == 'Running':
            self_info = status.get('Self', {})
            tailscale_ips = self_info.get('TailscaleIPs', [])
            dns_name = self_info.get('DNSName', '').rstrip('.')

            if tailscale_ips:
                expected_suffix = 'tail4d77be.ts.net'
                if dns_name.endswith(expected_suffix):
                    print(f"✓ Tailscale: Running on TAKNET-PS tailnet ({tailscale_ips[0]})")
                    return (True, tailscale_ips[0])
                else:
                    print(f"⚠ Tailscale: Connected to different tailnet ({dns_name}) - skipping")
                    return (False, None)

        return (False, None)

    except Exception:
        return (False, None)


def select_taknet_host(env_vars):
    """
    Select TAKNET-PS Server host based on VPN status.
    NetBird active → vpn.tak-solutions.com
    No VPN        → adsb.tak-solutions.com
    Returns: (selected_host, connection_type)
    """
    mode = env_vars.get('TAKNET_PS_CONNECTION_MODE', 'auto').lower()
    vpn_host = env_vars.get('TAKNET_PS_SERVER_HOST_VPN', 'vpn.tak-solutions.com').strip()
    fallback  = env_vars.get('TAKNET_PS_SERVER_HOST_FALLBACK', 'adsb.tak-solutions.com').strip()

    if mode == 'vpn' and vpn_host:
        print(f"ℹ TAKNET-PS: Forced to VPN host: {vpn_host}")
        return (vpn_host, 'vpn-forced')

    if mode == 'fallback' and fallback:
        print(f"ℹ TAKNET-PS: Forced to fallback: {fallback}")
        return (fallback, 'fallback-forced')

    # Auto mode - NetBird check only
    if mode == 'auto':
        netbird_running, _ = check_netbird_running()
        if netbird_running:
            print(f"✓ TAKNET-PS: NetBird active, using VPN host: {vpn_host}")
            return (vpn_host, 'netbird-active')

        print(f"⚠ TAKNET-PS: NetBird inactive, using fallback: {fallback}")
        return (fallback, 'vpn-inactive')

    if vpn_host:
        return (vpn_host, 'vpn-fallback')
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
    
    # 978 MHz UAT Input (if dump978 enabled)
    if env_vars.get('DUMP978_ENABLED', 'false').lower() == 'true':
        config_parts.append("uat_in,dump978,30978,uat_in")
        print("✓ 978 MHz UAT (dump978 container)")
    
    return ';'.join(config_parts)

def build_dump978_service(env_vars):
    """
    Build dump978 service configuration
    Supports both RTL-SDR and FTDI UATRadio hardware
    """
    sdr_978_device = env_vars.get('SDR_978_DEVICE', '')
    sdr_978_type = env_vars.get('SDR_978_TYPE', 'rtlsdr')
    sdr_978_path = env_vars.get('SDR_978_PATH', '1')
    sdr_978_gain = env_vars.get('SDR_978_GAIN', 'autogain')
    
    # Don't create service if 978 not configured
    if not sdr_978_device or sdr_978_device == 'disabled':
        return None
    
    # Get values from env_vars
    feeder_tz = env_vars.get('FEEDER_TZ', 'UTC')
    feeder_lat = env_vars.get('FEEDER_LAT', '')
    feeder_long = env_vars.get('FEEDER_LONG', '')
    
    service = {
        'image': 'ghcr.io/sdr-enthusiasts/docker-dump978:latest',
        'container_name': 'dump978',
        'hostname': 'dump978',
        'restart': 'unless-stopped',
        'networks': ['adsb_net'],
        'environment': [
            f'TZ={feeder_tz}',
            f'LAT={feeder_lat}',
            f'LONG={feeder_long}'
        ],
        'tmpfs': [
            '/run:exec,size=64M',
            '/var/log'
        ],
        'profiles': ['dump978']
    }
    
    # Device mapping differs for RTL-SDR vs FTDI
    if sdr_978_type == 'ftdi':
        # FTDI UATRadio: Map specific device path
        service['devices'] = [f'{sdr_978_path}:{sdr_978_path}:rw']
        service['environment'].extend([
            f'DUMP978_DEVICE={sdr_978_path}',
            'DUMP978_DRIVER=hackrf',
            'DUMP978_SDR_AGC=off',
            'DUMP978_JSON_STDOUT=true'
        ])
    else:
        # RTL-SDR: Map USB bus and use device index
        service['devices'] = ['/dev/bus/usb:/dev/bus/usb']
        service['environment'].extend([
            f'DUMP978_DEVICE={sdr_978_path}',
            'DUMP978_SDR_GAIN={sdr_978_gain}',
            'DUMP978_SDR_AGC=off',
            'DUMP978_JSON_STDOUT=true'
        ])
        
        # Add gain if not autogain
        if sdr_978_gain and sdr_978_gain != 'autogain':
            service['environment'].append(f'DUMP978_GAIN={sdr_978_gain}')
    
    return service

def build_sdr_configuration(env_vars):
    """
    Phase B: Smart SDR configuration builder
    Returns environment variables for readsb based on driver type
    """
    # Get SDR configuration
    sdr_driver = env_vars.get('SDR_1090_DRIVER', 'rtlsdr')
    sdr_serial = env_vars.get('SDR_1090_SERIAL', '')
    sdr_device = env_vars.get('SDR_1090_DEVICE', '0')
    sdr_gain = env_vars.get('SDR_1090_GAIN', 'autogain')
    use_soapy = env_vars.get('USE_SOAPYSDR', 'auto')
    
    # Legacy fallback for systems without new variables
    if not sdr_driver:
        sdr_driver = env_vars.get('SDR_1090_TYPE', 'rtlsdr')
    if not sdr_device:
        sdr_device = env_vars.get('READSB_DEVICE', '0')
    if not sdr_gain:
        sdr_gain = env_vars.get('READSB_GAIN', 'autogain')
    
    print(f"[Phase B] SDR Configuration:")
    print(f"  Driver: {sdr_driver}")
    print(f"  Serial: {sdr_serial}")
    print(f"  Device: {sdr_device}")
    print(f"  Gain (raw): {sdr_gain}")
    print(f"  USE_SOAPYSDR: {use_soapy}")
    
    # Validate and adjust gain for driver type
    sdr_gain = validate_gain(sdr_driver, sdr_gain)
    print(f"  Gain (validated): {sdr_gain}")
    
    # Determine device type to use
    device_type = None
    config = {}
    
    # Decision logic
    if use_soapy == 'false':
        # Force native drivers
        print(f"[Phase B] Forced native driver mode")
        device_type = 'native'
        
    elif use_soapy == 'true':
        # Force SoapySDR
        print(f"[Phase B] Forced SoapySDR mode")
        device_type = 'soapysdr'
        
    else:  # auto mode
        # Use native for RTL-SDR, SoapySDR for others
        if sdr_driver == 'rtlsdr':
            print(f"[Phase B] Auto mode: Using native rtlsdr driver")
            device_type = 'native'
        else:
            print(f"[Phase B] Auto mode: Using SoapySDR for {sdr_driver}")
            device_type = 'soapysdr'
    
    # Build configuration based on decision
    if device_type == 'native':
        if sdr_driver == 'rtlsdr':
            config['environment'] = [
                'READSB_DEVICE_TYPE=rtlsdr',
                f'READSB_RTLSDR_DEVICE={sdr_device}',
                f'READSB_GAIN={sdr_gain}'
            ]
            print(f"[Phase B] Native RTL-SDR config: device={sdr_device}, gain={sdr_gain}")
            
        elif sdr_driver == 'airspy':
            # Airspy native mode (requires serial)
            if sdr_serial:
                config['environment'] = [
                    'READSB_DEVICE_TYPE=airspy',
                    f'READSB_AIRSPY_DEVICE={sdr_serial}',
                    f'READSB_GAIN={sdr_gain}'
                ]
                print(f"[Phase B] Native Airspy config: serial={sdr_serial}, gain={sdr_gain}")
            else:
                # Fall back to SoapySDR if no serial
                print(f"[Phase B] Warning: Airspy serial missing, falling back to SoapySDR")
                device_type = 'soapysdr'
        
        else:
            # Unknown driver, fall back to SoapySDR
            print(f"[Phase B] Warning: Unknown driver {sdr_driver}, falling back to SoapySDR")
            device_type = 'soapysdr'
    
    if device_type == 'soapysdr':
        # Build SoapySDR device string
        if sdr_serial and sdr_serial != '':
            soapy_device = f'driver={sdr_driver},serial={sdr_serial}'
        else:
            soapy_device = f'driver={sdr_driver},index={sdr_device}'
        
        config['environment'] = [
            'READSB_DEVICE_TYPE=soapysdr',
            f'READSB_SOAPY_DEVICE={soapy_device}',
            f'READSB_GAIN={sdr_gain}'
        ]
        print(f"[Phase B] SoapySDR config: {soapy_device}, gain={sdr_gain}")
    
    return config

def build_docker_compose(env_vars):
    """Build docker-compose.yml with conditional FR24 service"""
    # Get all env vars needed for ultrafeeder (write actual values, not ${VARIABLE})
    feeder_tz = env_vars.get('FEEDER_TZ', 'UTC')
    feeder_lat = env_vars.get('FEEDER_LAT', '')
    feeder_long = env_vars.get('FEEDER_LONG', '')
    feeder_alt_m = env_vars.get('FEEDER_ALT_M', '')
    feeder_uuid = env_vars.get('FEEDER_UUID', '')
    mlat_site_name = env_vars.get('MLAT_SITE_NAME', 'feeder')
    ultrafeeder_config = env_vars.get('ULTRAFEEDER_CONFIG', '')
    
    # Phase B: Smart SDR configuration
    sdr_config = build_sdr_configuration(env_vars)
    
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
                    f'TZ={feeder_tz}',
                    f'LAT={feeder_lat}',
                    f'LONG={feeder_long}',
                    f'ALT={feeder_alt_m}m',
                    f'UUID={feeder_uuid}',
                    # Phase B: Dynamic SDR configuration from build_sdr_configuration()
                    *sdr_config['environment'],
                    'READSB_RX_LOCATION_ACCURACY=2',
                    'READSB_STATS_RANGE=true',
                    f'MLAT_USER={mlat_site_name}',
                    'UPDATE_TAR1090=true',
                    'TAR1090_ENABLE_AC_DB=true',
                    'TAR1090_FLIGHTAWARELINKS=true',
                    'TAR1090_SITESHOW=true',
                    f'ULTRAFEEDER_CONFIG={ultrafeeder_config}',
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
    # Get FR24 key from env_vars and write actual value (not ${VARIABLE})
    fr24_key = env_vars.get('FR24_KEY', '').strip()
    
    # Build environment array
    fr24_env = [
        'BEASTHOST=ultrafeeder',
        'BEASTPORT=30005',
        'MLAT=yes'
    ]
    
    # Only add FR24KEY if it has a value
    if fr24_key:
        fr24_env.insert(2, f'FR24KEY={fr24_key}')
    
    compose['services']['fr24'] = {
        'image': 'ghcr.io/sdr-enthusiasts/docker-flightradar24:latest',
        'container_name': 'fr24',
        'hostname': 'fr24',
        'restart': 'unless-stopped',
        'networks': ['adsb_net'],
        'depends_on': ['ultrafeeder'],
        'ports': ['8754:8754'],
        'environment': fr24_env,
        'tmpfs': ['/var/log']
    }
    
    # Always include PiAware service (can be started/stopped via docker compose)
    # Get PiAware values from env_vars and write actual values (not ${VARIABLE})
    feeder_tz = env_vars.get('FEEDER_TZ', 'UTC')
    piaware_feeder_id = env_vars.get('PIAWARE_FEEDER_ID', '')
    
    compose['services']['piaware'] = {
        'image': 'ghcr.io/sdr-enthusiasts/docker-piaware:latest',
        'container_name': 'piaware',
        'hostname': 'piaware',
        'restart': 'unless-stopped',
        'networks': ['adsb_net'],
        'depends_on': ['ultrafeeder'],
        'ports': ['8082:80'],
        'environment': [
            f'TZ={feeder_tz}',  # Write actual value
            f'FEEDER_ID={piaware_feeder_id}',  # Write actual value
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
    # Get values from env_vars (write actual values, not ${VARIABLE})
    adsbhub_station_key = env_vars.get('ADSBHUB_STATION_KEY', '')
    
    compose['services']['adsbhub'] = {
        'image': 'ghcr.io/sdr-enthusiasts/docker-adsbhub:latest',
        'container_name': 'adsbhub',
        'hostname': 'adsbhub',
        'restart': 'unless-stopped',
        'networks': ['adsb_net'],
        'depends_on': ['ultrafeeder'],
        'environment': [
            f'TZ={feeder_tz}',  # Reuse from ultrafeeder section above
            'SBSHOST=ultrafeeder',
            f'CLIENTKEY={adsbhub_station_key}'
        ]
    }
    
    # Include dump978 service if 978 MHz is configured
    dump978_service = build_dump978_service(env_vars)
    if dump978_service:
        compose['services']['dump978'] = dump978_service
    
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
