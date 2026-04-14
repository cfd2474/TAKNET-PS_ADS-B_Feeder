#!/usr/bin/env python3
"""
TAKNET-PS Phase B Migration Script
Migrates existing .env files to add Phase B driver variables
"""

import sys
import os

def read_env(env_file='/opt/adsb/config/.env'):
    """Read environment file"""
    env = {}
    if not os.path.exists(env_file):
        # Fallback to legacy path if new path doesn't exist
        legacy_path = '/opt/adsb/.env'
        if os.path.exists(legacy_path):
            env_file = legacy_path
        else:
            return env
    
    with open(env_file, 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                env[key.strip()] = value.strip()
    return env

def write_env(env, env_file='/opt/adsb/config/.env'):
    """Write environment file"""
    # Ensure directory exists
    os.makedirs(os.path.dirname(env_file), exist_ok=True)
    with open(env_file, 'w') as f:
        for key, value in sorted(env.items()):
            f.write(f'{key}={value}\n')

def migrate_to_phase_b():
    """Migrate existing config to Phase B format"""
    print("="*60)
    print("TAKNET-PS Phase B Migration")
    print("="*60)
    
    env_file = '/opt/adsb/config/.env'
    if not os.path.exists(env_file):
        # Fallback to legacy path
        env_file = '/opt/adsb/.env'
        
    if not os.path.exists(env_file):
        print(f"✗ Error: .env not found in /opt/adsb/config/ or /opt/adsb/")
        sys.exit(1)
    
    print(f"Using configuration file: {env_file}")
    
    # Read current config
    env = read_env(env_file)
    
    # Phase 1: SDR 1090 Migration
    if 'SDR_1090_DRIVER' not in env:
        print("\n🔄 Migrating SDR 1090 to Phase B format...")
        # Set driver (use existing TYPE or default to rtlsdr)
        env['SDR_1090_DRIVER'] = env.get('SDR_1090_TYPE', 'rtlsdr')
        # Set serial
        env['SDR_1090_SERIAL'] = env.get('SDR_1090_SERIAL', '')
        # Ensure device is set
        if 'SDR_1090_DEVICE' not in env:
            env['SDR_1090_DEVICE'] = env.get('READSB_DEVICE', '0')
        # Add USE_SOAPYSDR flag
        if 'USE_SOAPYSDR' not in env:
            env['USE_SOAPYSDR'] = 'auto'
        print("✓ SDR 1090 migration complete")
    else:
        print("✓ SDR 1090 already migrated")
    
    # Phase 2: SDR 978 (UAT) Migration
    # legacy UAT detection - check if UAT was enabled in old format
    uat_hardware_detected = False
    # Legacy indicators: UAT_RECEIVER_TYPE or UAT_RECEIVER_HOST set to something other than none/relay
    urt = env.get('UAT_RECEIVER_TYPE', '').lower()
    urh = env.get('UAT_RECEIVER_HOST', '').lower()
    if urt and urt not in ['none', 'relay']:
        uat_hardware_detected = True
    if urh and urh not in ['none', 'ultrafeeder']:
        uat_hardware_detected = True
    
    # If hardware detected, MUST ensure service is enabled
    # We override even if set to 'false' because the update might have applied a pessimistic default
    if uat_hardware_detected and env.get('DUMP978_ENABLED', 'false').lower() != 'true':
        print("✓ Detected legacy UAT configuration - FORCIBLY enabling dump978 service")
        env['DUMP978_ENABLED'] = 'true'

    if env.get('DUMP978_ENABLED', 'false').lower() == 'true':
        if 'SDR_978_DRIVER' not in env:
            print("🔄 Migrating SDR 978 (UAT) to Phase B format...")
            env['SDR_978_DRIVER'] = env.get('SDR_978_TYPE', 'rtlsdr')
            env['SDR_978_SERIAL'] = env.get('SDR_978_SERIAL', '')
            if 'SDR_978_DEVICE' not in env:
                env['SDR_978_DEVICE'] = env.get('DUMP978_DEVICE', '1')
            print("✓ SDR 978 migration complete")
    
    # Phase 3: Deployment Mode
    if 'FEEDER_DEPLOYMENT_MODE' not in env:
        env['FEEDER_DEPLOYMENT_MODE'] = 'stationary'
    
    # Write updated config (always use the new standard path)
    write_env(env, '/opt/adsb/config/.env')
    
    print("\n✓ All Migration steps verified!")
    print(f"\n📋 Configuration Summary:")
    print(f"  SDR_1090_DRIVER: {env.get('SDR_1090_DRIVER')}")
    print(f"  DUMP978_ENABLED: {env.get('DUMP978_ENABLED', 'false')}")
    if env.get('DUMP978_ENABLED') == 'true':
        print(f"  SDR_978_DRIVER: {env.get('SDR_978_DRIVER')}")
    
    print("\n⚠ Note: Configuration will use native drivers by default (auto mode)")
    print("   RTL-SDR devices will continue using READSB_DEVICE_TYPE=rtlsdr")
    print("   For Airspy/HackRF support, set USE_SOAPYSDR=true\n")

if __name__ == '__main__':
    try:
        migrate_to_phase_b()
    except KeyboardInterrupt:
        print("\n\n✗ Migration cancelled")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Migration failed: {e}")
        sys.exit(1)
