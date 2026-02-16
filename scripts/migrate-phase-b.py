#!/usr/bin/env python3
"""
TAKNET-PS Phase B Migration Script
Migrates existing .env files to add Phase B driver variables
"""

import sys
import os

def read_env(env_file='/opt/adsb/.env'):
    """Read environment file"""
    env = {}
    if not os.path.exists(env_file):
        return env
    
    with open(env_file, 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                env[key.strip()] = value.strip()
    return env

def write_env(env, env_file='/opt/adsb/.env'):
    """Write environment file"""
    with open(env_file, 'w') as f:
        for key, value in sorted(env.items()):
            f.write(f'{key}={value}\n')

def migrate_to_phase_b():
    """Migrate existing config to Phase B format"""
    print("="*60)
    print("TAKNET-PS Phase B Migration")
    print("="*60)
    
    env_file = '/opt/adsb/.env'
    if not os.path.exists(env_file):
        print(f"✗ Error: {env_file} not found")
        sys.exit(1)
    
    # Read current config
    env = read_env(env_file)
    
    # Check if already migrated
    if 'SDR_1090_DRIVER' in env:
        print("✓ Already migrated to Phase B")
        return
    
    print("\n📋 Current Configuration:")
    print(f"  SDR_1090_TYPE: {env.get('SDR_1090_TYPE', 'Not set')}")
    print(f"  SDR_1090_DEVICE: {env.get('SDR_1090_DEVICE', 'Not set')}")
    print(f"  READSB_DEVICE: {env.get('READSB_DEVICE', 'Not set')}")
    
    # Migrate SDR_1090 variables
    print("\n🔄 Migrating to Phase B format...")
    
    # Set driver (use existing TYPE or default to rtlsdr)
    env['SDR_1090_DRIVER'] = env.get('SDR_1090_TYPE', 'rtlsdr')
    
    # Set serial (empty for now, will be detected)
    env['SDR_1090_SERIAL'] = env.get('SDR_1090_SERIAL', '')
    
    # Ensure device is set
    if 'SDR_1090_DEVICE' not in env:
        env['SDR_1090_DEVICE'] = env.get('READSB_DEVICE', '0')
    
    # Migrate SDR_978 variables if 978 is enabled
    if env.get('DUMP978_ENABLED', 'false') == 'true':
        env['SDR_978_DRIVER'] = env.get('SDR_978_TYPE', 'rtlsdr')
        env['SDR_978_SERIAL'] = env.get('SDR_978_SERIAL', '')
        if 'SDR_978_DEVICE' not in env:
            env['SDR_978_DEVICE'] = env.get('DUMP978_DEVICE', '1')
    
    # Add USE_SOAPYSDR flag (default to auto)
    if 'USE_SOAPYSDR' not in env:
        env['USE_SOAPYSDR'] = 'auto'
    
    # Write updated config
    write_env(env, env_file)
    
    print("\n✓ Migration Complete!")
    print(f"\n📋 New Configuration:")
    print(f"  SDR_1090_DRIVER: {env['SDR_1090_DRIVER']}")
    print(f"  SDR_1090_SERIAL: {env['SDR_1090_SERIAL']}")
    print(f"  SDR_1090_DEVICE: {env['SDR_1090_DEVICE']}")
    print(f"  USE_SOAPYSDR: {env['USE_SOAPYSDR']}")
    
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
