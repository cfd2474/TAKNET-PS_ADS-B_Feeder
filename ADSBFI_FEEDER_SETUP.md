# adsb.fi Feeder Setup Guide

## Overview
This guide covers adding adsb.fi feeding to your existing readsb-based ADS-B feeder. The adsb.fi feeder client will run alongside your current setup without conflicts.

## What is adsb.fi?
adsb.fi is a community-driven, unfiltered ADS-B aggregator created as an alternative to commercial tracking services:
- Complete, unfiltered aircraft data
- Community-owned and operated
- MLAT (multilateration) support
- Privacy-focused
- Free for all users
- Optional local web interface

## Prerequisites
- Working readsb installation
- Beast output enabled on port 30005
- Active internet connection
- SSH access to your Pi

## Installation

### Step 1: Find Your Coordinates and Elevation

Use this tool to find your precise location:
https://www.freemaptools.com/elevation-finder.htm

You'll need:
- **Latitude** in decimal format (e.g., 33.6235)
- **Longitude** in decimal format (e.g., -117.1271)
- **Elevation** in meters above sea level (e.g., 439)

### Step 2: Install the adsb.fi Feed Client

Run the automated installer:

```bash
curl -L -o /tmp/feed.sh https://adsb.fi/feed.sh
sudo bash /tmp/feed.sh
```

The installer will:
1. Prompt for your antenna coordinates and elevation
2. Detect your existing readsb installation
3. Configure the feed client automatically
4. Set up systemd services for automatic startup
5. Configure MLAT client

**During installation:**
- Enter your precise coordinates when prompted
- Provide elevation in **meters** above sea level
- The script will auto-detect your readsb Beast output on `127.0.0.1:30005`
- The script will not disrupt your existing feeds

### Step 3: Verify the Feed is Working

Check that data is flowing to adsb.fi:

```bash
netstat -t -n | grep -E '30004|31090'
```

**Expected output:**
```
tcp 0 182 localhost:43530 65.109.2.208:31090 ESTABLISHED
tcp 0 410 localhost:47332 65.109.2.208:30004 ESTABLISHED
```

- **Port 30004**: ADS-B data (Beast format)
- **Port 31090**: MLAT data

### Step 4: Check Your Feed Status

Visit the adsb.fi website from a device on the same local network as your feeder:

**https://adsb.fi**

You should see **"You are feeding data"** in the lower-left corner of the screen. Click this link to view your detailed feed status.

## Optional: Install Local Web Interface

The adsb.fi installer can set up a local web interface showing only aircraft received by your feeder:

During installation, answer **yes** when prompted to install the web interface, or run:

```bash
sudo bash /usr/local/share/adsbfi/git/install-or-update-interface.sh
```

After installation, access your local interface at:
```
http://[PI_IP]/adsbfi/
```

**Features:**
- Map showing only your received aircraft
- Based on tar1090
- Performance statistics
- Range and coverage visualization
- Local aircraft tracking

## Service Management

### Check Service Status

```bash
# Check feed client status
sudo systemctl status adsbfi-feed

# Check MLAT client status
sudo systemctl status adsbfi-mlat
```

### View Logs

```bash
# Feed client logs
sudo journalctl -u adsbfi-feed -f

# MLAT client logs
sudo journalctl -u adsbfi-mlat -f
```

### Restart Services

```bash
# Restart feed client
sudo systemctl restart adsbfi-feed

# Restart MLAT client
sudo systemctl restart adsbfi-mlat
```

## Configuration

The configuration is stored in:
```
/etc/default/adsbfi
```

To modify settings:

```bash
sudo nano /etc/default/adsbfi
```

**Key settings:**
```bash
INPUT="127.0.0.1:30005"      # Beast input from readsb
INPUT_TYPE="beast"           # Data format
LAT="33.6235"                # Your latitude
LON="-117.1271"              # Your longitude
ALT="439"                    # Elevation in meters
RECEIVER_NAME="adsb-pi-92563" # Your feeder name
```

**If your readsb is on a different machine:**

Edit the INPUT line to point to your readsb server:
```bash
INPUT="READSB_IP:30005"
```

After making changes:
```bash
sudo systemctl restart adsbfi-feed
sudo systemctl restart adsbfi-mlat
```

## Updating the Feed Client

To update to the latest version:

```bash
curl -L -o /tmp/update.sh https://raw.githubusercontent.com/adsbfi/adsb-fi-scripts/master/update.sh
sudo bash /tmp/update.sh
```

Or re-run the installation script (it will detect existing installation and update):

```bash
curl -L -o /tmp/feed.sh https://adsb.fi/feed.sh
sudo bash /tmp/feed.sh
```

The update process will preserve your existing configuration.

## Troubleshooting

### Issue: Not Showing "You are feeding data"

**Wait 5-10 minutes** after installation for the connection to establish.

**Check services are running:**
```bash
sudo systemctl status adsbfi-feed
sudo systemctl status adsbfi-mlat
```

**Check network connectivity:**
```bash
ping 65.109.2.208
```

**Verify readsb is running:**
```bash
systemctl status readsb
timeout 3 nc 127.0.0.1 30005 | hexdump -C | head -5
```

### Issue: MLAT Not Syncing

**Requirements for MLAT:**
- Precise coordinates (within a few meters)
- Stable system time/NTP sync
- At least 3-4 other nearby MLAT-enabled feeders
- Consistent aircraft reception

**Check time synchronization:**
```bash
timedatectl status
```

**View MLAT logs:**
```bash
sudo journalctl -u adsbfi-mlat | grep -i sync
```

**MLAT synchronization can take 10-30 minutes** after first connection.

### Issue: Local Web Interface Not Working

**Check if lighttpd is running:**
```bash
sudo systemctl status lighttpd
```

**Verify the interface files exist:**
```bash
ls -la /usr/share/adsbfi/html/
```

**Reinstall the interface:**
```bash
sudo bash /usr/local/share/adsbfi/git/install-or-update-interface.sh
```

**Access using your Pi's IP address:**
```bash
# Find your IP
hostname -I

# Then browse to: http://[IP]/adsbfi/
```

### Issue: Services Won't Start

**Check configuration syntax:**
```bash
cat /etc/default/adsbfi
```

**Look for errors in logs:**
```bash
sudo journalctl -u adsbfi-feed -n 50
sudo journalctl -u adsbfi-mlat -n 50
```

**Common causes:**
- Invalid coordinate format
- Incorrect Beast input address
- readsb not running
- Port 30005 not accessible

### Issue: Low Aircraft Count

**Verify readsb is seeing aircraft:**
```bash
curl -s http://127.0.0.1/tar1090/data/aircraft.json | grep -o '"flight"' | wc -l
```

**Check that Beast data is available:**
```bash
timeout 3 nc 127.0.0.1 30005 | hexdump -C | head -10
```

If readsb shows aircraft but adsb.fi doesn't:
- Check feed client is running
- Verify network connection to 65.109.2.208
- Check logs for errors

## Uninstalling

To remove the adsb.fi feeder:

```bash
# Stop and disable services
sudo systemctl stop adsbfi-feed adsbfi-mlat
sudo systemctl disable adsbfi-feed adsbfi-mlat

# Remove service files
sudo rm /etc/systemd/system/adsbfi-feed.service
sudo rm /etc/systemd/system/adsbfi-mlat.service

# Remove configuration
sudo rm /etc/default/adsbfi

# Remove client software
sudo rm -rf /usr/local/share/adsbfi

# Remove web interface (if installed)
sudo bash /usr/local/share/tar1090/uninstall.sh adsbfi

# Reload systemd
sudo systemctl daemon-reload
```

## Benefits

- **Unfiltered data**: Complete aircraft coverage
- **Community-driven**: Created by enthusiasts, for enthusiasts
- **Privacy-focused**: No commercial data selling
- **Free forever**: No paid tiers or subscriptions
- **MLAT support**: Multilateration for non-ADS-B aircraft
- **No account required**: Start feeding immediately
- **Local interface**: Optional web interface for your feeder

## Port Usage

The adsb.fi feeder uses:

| Port | Direction | Purpose | Protocol |
|------|-----------|---------|----------|
| 30005 | Input (from readsb) | Beast data | TCP |
| 30004 | Output (to adsb.fi) | ADS-B feed | TCP |
| 31090 | Output (to adsb.fi) | MLAT feed | TCP |

## Comparison with Other Services

**adsb.fi vs ADS-B Exchange:**
- Both provide unfiltered data
- Both are community-focused
- adsb.fi created as alternative during ADS-B Exchange transition
- Similar features and goals
- Can feed both simultaneously

**adsb.fi vs airplanes.live:**
- Both are community-driven alternatives
- Both provide unfiltered data
- airplanes.live has more polished web interface
- adsb.fi has optional local web interface
- Can feed both simultaneously

**Why Feed Multiple Services?**
- Redundancy - if one service has issues, others continue
- Support the community - help multiple projects
- No downside - minimal extra resource usage
- Each service may have unique features

## Related Links

- **Main Website**: https://adsb.fi
- **Network Map**: https://adsb.fi/network
- **GitHub**: https://github.com/adsbfi/adsb-fi-scripts
- **Discord**: Check adsb.fi website for community links

## Key Takeaways

1. **Simple installation** - Single script handles everything
2. **No account needed** - Anonymous feeding supported
3. **Works alongside other feeders** - Won't interfere with existing feeds
4. **Community-focused** - Created by enthusiasts, for enthusiasts
5. **Optional local interface** - Monitor your own feeder performance
6. **Unfiltered data** - Complete aircraft coverage
7. **Privacy-respecting** - No commercial data exploitation

---

*Last updated: January 2026*
