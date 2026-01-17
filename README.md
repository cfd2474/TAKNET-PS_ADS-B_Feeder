# TAK-ADSB-Feeder

Automated installer for Raspberry Pi ADS-B feeders with Tailscale integration and **local tar1090 web interface**. Feed real-time aircraft tracking data to your aggregation server over a secure mesh network while monitoring individual feeder performance.

---

## ⚠️ IMPORTANT: Read This First

**DO NOT skip ahead to installation!** This document contains critical information about:
- Required hardware and software configuration
- Proper hostname setup for network identification
- Tailscale authentication requirements
- Your geographic coordinates and antenna altitude

**Take 10 minutes to read through completely before starting.**

---

## ✨ What's New in v5.4

- 📡 **MLAT opt-out option** - Choose to disable MLAT during installation to conserve bandwidth
- ⚠️ **Data usage warnings** - Clear guidance about MLAT bandwidth consumption for metered connections
- 🎛️ **Flexible MLAT control** - Enable/disable MLAT post-installation with simple commands
- 💾 **Smart service management** - MLAT installed but not enabled if opted out

### Previous Updates

**v5.3 - Bug Fixes**
- 🐛 **Script path resolution** - Fixed absolute path capture for reliable self-updates
- 🧹 **Temporary directory cleanup** - Improved cleanup of temp files during installation

**v5.2 - Self-Update System**
- 🔄 **Self-updating installer** - Update with `./adsb_feeder_installer.sh --update`
- 🛠️ **System update command** - `adsb-update` for easy component updates
- 📦 **Modular updates** - Update individual components or everything at once
- 🔍 **Version checking** - See current version with `--version` flag

**v5.0/v5.1 - Infrastructure**
- 📁 **Dedicated installation directory** at `/opt/TAK_ADSB/` for organized deployments
- 📊 **vnstat network monitoring** with 90-day data retention
- 👤 **Remote management user** (`remote:adsb`) for easier administration
- 🔒 **SSH security** - Remote user restricted to Tailscale network only
- 🔧 **Improved directory structure** with binaries, data, and logs separated
- 🔒 **Pre-configured sudo access** for common service management commands

**v4.0 - Local Web Interface**
- 🌐 **Local tar1090 web interface** on each Pi feeder
- 📊 **Per-feeder statistics** and coverage visualization
- 📍 **Dual monitoring**: View individual Pi coverage AND network-wide aggregation
- 🔍 **Better diagnostics** with local aircraft counts and performance metrics
- 🚀 **Network-wide aggregation** to central server

## 📋 What This Installer Does

The installer automatically:
- ✅ Creates dedicated `/opt/TAK_ADSB/` installation directory
- ✅ Installs and configures Tailscale VPN
- ✅ Installs vnstat for network bandwidth monitoring (90-day retention)
- ✅ Creates remote management user with Tailscale-only SSH access
- ✅ Installs self-update functionality for easy maintenance
- ✅ Installs RTL-SDR drivers and tools
- ✅ Builds and installs `readsb` ADS-B decoder
- ✅ Builds and installs `mlat-client` for multilateration (optional)
- ✅ Installs `tar1090` locally on each Pi
- ✅ Installs `lighttpd` web server
- ✅ Creates systemd services for automatic startup
- ✅ Connects to your aggregation server
- ✅ Verifies everything is working

**Installation time: 15-20 minutes**

## 🛠️ Requirements

### Hardware
- **Raspberry Pi 3B or newer** (4B recommended for best performance)
- **RTL-SDR USB dongle** (FlightAware Pro Stick or Pro Stick Plus recommended)
- **1090 MHz ADS-B antenna** (outdoor installation preferred)
- **MicroSD card** (16GB minimum, 32GB recommended)
- **Power supply** (5V 2.5A minimum, official Raspberry Pi PSU recommended)

### Software - CRITICAL
- **Raspberry Pi OS Bookworm Lite** (64-bit **strongly** recommended)
  - Download: https://www.raspberrypi.com/software/operating-systems/
  - Use **Raspberry Pi Imager** to flash your SD card
  - **Enable SSH** during image creation
  - **Set WiFi credentials** if not using ethernet
  
- **Proper hostname configuration** (see below)
- **Internet connection** (WiFi or Ethernet)

### 🏷️ Hostname Setup - DO THIS FIRST!

**Before running the installer**, set a meaningful hostname for easy identification:

**Recommended naming convention:**
```
adsb-pi-[ZIPCODE]
```

Examples:
- `adsb-pi-92882` (Corona, CA)
- `adsb-pi-10001` (New York, NY)
- `adsb-pi-90210` (Beverly Hills, CA)

**How to set hostname using Raspberry Pi Imager:**
1. Click the gear icon (⚙️) for advanced options
2. Set hostname: `adsb-pi-XXXXX` (replace XXXXX with your zip code)
3. Enable SSH and set your WiFi credentials
4. Flash the SD card

**How to change hostname on existing installation:**
```bash
sudo hostnamectl set-hostname adsb-pi-92882
sudo reboot
```

**Why this matters:**
- Your feeder will be identified as `adsb-pi-92882_abc123` on the network
- Makes it easy to identify which physical location each feeder represents
- Essential when managing multiple feeders across different locations
- Helps with troubleshooting and network monitoring

## 📖 Documentation

Before proceeding, review these guides:
- **[QUICK_START.md](QUICK_START.md)** - Fast-track setup guide with detailed steps
- **[DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md)** - Complete reference for scaling to multiple feeders

## 🔧 Configuration Information Needed

**Before running the installer**, gather this information:

### 1. Tailscale Authentication (Optional but Recommended)
- **If you have a Tailscale auth key**: Have it ready to paste
- **If you don't have a key**: Press Enter when prompted, you'll authenticate via browser or skip completely.
- Contact [Michael Leckliter](mailto:michael.leckliter@yahoo.com) if you need an auth key

### 2. MLAT Configuration (NEW in v5.4)
During installation, you'll be asked whether to enable MLAT:
- **Enable MLAT (default)**: Improves position accuracy via multilateration
  - Requires more network bandwidth
  - **Not recommended** for metered connections (LTE/cellular with data caps)
- **Disable MLAT**: Conserves bandwidth for limited data plans
  - Can be enabled later with simple commands
  - MLAT client still installed, just not activated

### 3. Geographic Coordinates (REQUIRED)
You'll need your **precise** location for MLAT (multilateration) to work:

- **Latitude** (e.g., `33.834378`)
- **Longitude** (e.g., `-117.573072`)
- **Altitude in meters** (antenna height above sea level, e.g., `395`)

**Finding your coordinates:**
1. Use Google Maps: Right-click your location → Click the coordinates
2. For altitude, use: https://whatismyelevation.com/

> **📏 Critical: Use ANTENNA altitude, not ground elevation!**
>
> Calculate as: **Ground Elevation + Building Height + Mast Height**
>
> Example: Ground = 350m, roof = 15m, mast = 5m → **Total = 370m**

### 4. Pre-Configured Network Settings
These are already set in the installer:
- **Installation Directory**: `/opt/TAK_ADSB/`
- **Aggregator IP**: `100.117.34.88` (Tailscale)
- **Beast Port**: `30004`
- **MLAT Port**: `30105`
- **Remote User**: `remote` (password: `adsb`)
- **SSH Security**: Remote user accessible only from Tailscale network (100.x.x.x)

## 🚀 Installation Instructions

**Only proceed if you have:**
- ✅ Raspberry Pi OS Bookworm Lite installed
- ✅ Hostname set to `adsb-pi-[ZIPCODE]` format
- ✅ SSH access enabled
- ✅ Your geographic coordinates ready
- ✅ Decided whether to enable MLAT
- ✅ Read the requirements above

### Installation Commands

On your Raspberry Pi:
```bash
# Download the installer (force clean script)
wget -O adsb_feeder_installer.sh https://raw.githubusercontent.com/cfd2474/TAK-ADSB-Feeder/main/adsb_feeder_installer.sh

# Make it executable
chmod +x adsb_feeder_installer.sh

# Run the installer
./adsb_feeder_installer.sh
```

The installer will:
1. Prompt for Tailscale auth key (or press Enter to authenticate via browser)
2. Ask whether to enable MLAT (with bandwidth warning for metered connections)
3. Ask for your latitude, longitude, and altitude
4. Display configuration summary for your confirmation
5. Install and configure all components (15-20 minutes)
6. Start services and verify connectivity

**During installation:**
- If you didn't provide an auth key, a browser window will open for Tailscale authentication
- Consider your internet connection when deciding on MLAT
- Follow the prompts carefully
- Answer "y" to proceed when configuration is shown
- Wait for all steps to complete

## 🔗 Already Have an ADS-B Receiver?

If you're already running an existing ADS-B feeder, you can add my aggregator as an additional feed without disrupting your current setup:

- **[MLAT Setup](MLAT_config.md)** - Setup MLAT to this aggregator **Must follow this guide if you use MLAT for other services listed below**
- **[PiAware/FlightAware Instructions](piaware_feeder_instructions.md)** - Feed from PiAware SD card image or package install
- **[airplanes.live Instructions](airplanes.live_feeder_instructions.md)** - Feed from airplanes.live image
- **[Stratux Instructions](stratux_feeder_instructions.md)** - Feed from native Stratux software
- **[ADSBexchange Instructions](ADSBexchange_feeder_instructions.md)** - Feed from ADSBexchange image

All methods use SSH to create an additional feed while keeping your existing feeds working normally.

## 📡 Want to Feed to Another Service?

If you've installed this feeder and want to also share data with other aggregation services:

- **[FlightRadar24 Setup](ADDITIONAL_FEEDER_OUTPUTS/FR24_FEEDER_SETUP.md)** - Premium subscription benefits for active feeders
- **[airplanes.live Setup](ADDITIONAL_FEEDER_OUTPUTS/AIRPLANESLIVE_FEEDER_SETUP.md)** - Unfiltered community-driven network
- **[ADS-B Exchange Setup](ADDITIONAL_FEEDER_OUTPUTS/ADSBEXCHANGE_FEEDER_SETUP.md)** - World's largest unfiltered aggregator
- **[adsb.fi Setup](ADDITIONAL_FEEDER_OUTPUTS/ADSBFI_FEEDER_SETUP.md)** - Community-focused alternative network

These instructions show you how to run additional feeders alongside this installation without conflicts. All services can run simultaneously with minimal resource usage.

## 🌐 Network Architecture
```
┌─────────────────┐
│  RTL-SDR Dongle │
│   (1090 MHz)    │
└────────┬────────┘
         │
         │ USB
         │
┌────────▼────────────────┐      Tailscale VPN      ┌──────────────────┐
│    Raspberry Pi         │◄────────────────────────►│   Aggregator     │
│  adsb-pi-[ZIPCODE]      │   Beast: Port 30004      │   Server         │
│  /opt/TAK_ADSB/         │   MLAT:  Port 30105      │   (tar1090)      │
│  ┌────────────────────┐ │   (Optional)             │   (Network View) │
│  │ readsb + tar1090   │ │                          └──────────────────┘
│  │ (Local Coverage)   │ │
│  └────────────────────┘ │
│  ┌────────────────────┐ │
│  │ mlat-client        │ │
│  │ (Enable/Disable)   │ │
│  └────────────────────┘ │
│  ┌────────────────────┐ │
│  │ vnstat monitoring  │ │
│  │ (90-day history)   │ │
│  └────────────────────┘ │
│  ┌────────────────────┐ │
│  │ adsb-update tool   │ │
│  │ (self-updating)    │ │
│  └────────────────────┘ │
│   lighttpd web server   │
│   remote user access    │
│   (Tailscale only)      │
└─────────────────────────┘
     │
     │ http://TAILSCALE_IP/tar1090/
     │ (Individual feeder view)
     │
```

All communication happens over **Tailscale** - no port forwarding or public IPs needed!

## 📊 What You'll See

### Individual Feeder View
Access each Pi's local coverage at:
```
http://[TAILSCALE_IP]/tar1090/
```

Shows:
- Aircraft received by **this specific feeder**
- Individual coverage area and range
- Per-feeder message rates
- Local signal strength

### Network Aggregated View
Access the combined view at:
```
http://104.225.219.254/tar1090/
```

Shows:
- Aircraft from **ALL feeders** combined
- Network-wide coverage map
- Total aircraft count across all sites
- Aggregated statistics

### Network Statistics Dashboard
Access detailed network stats at:
```
http://104.225.219.254/graphs1090/
```

Features:
- Active feeder list (clickable for drill-down)
- Per-feeder connection status
- Network-wide aircraft counts
- Message rates and performance metrics
- **Click any feeder** to see detailed individual stats

## 🔍 Verification

After installation completes, verify everything is working:
```bash
# Check service status
sudo systemctl status readsb
sudo systemctl status mlat-client
sudo systemctl status lighttpd
sudo systemctl status vnstat

# Verify aggregator connection
netstat -tn | grep 100.117.34.88

# Check local data
curl http://localhost/tar1090/data/aircraft.json

# View live aircraft (Ctrl+C to exit)
/opt/TAK_ADSB/bin/viewadsb

# Check installer version
./adsb_feeder_installer.sh --version
```

**Find your Tailscale IP:**
```bash
tailscale ip -4
# Example output: 100.86.194.33
```

Then access your local tar1090: `http://100.86.194.33/tar1090/`

**Check network usage:**
```bash
vnstat -d    # Daily stats
vnstat -m    # Monthly stats
vnstat -l    # Live traffic (Ctrl+C to stop)
```

## 🔐 Remote Access

Each feeder includes a dedicated remote management user with SSH access **restricted to Tailscale network only**:
```bash
# SSH into your feeder (must be on Tailscale network)
ssh remote@[TAILSCALE_IP]
# Password: adsb

# Once logged in, you can:
cd /opt/TAK_ADSB              # Access installation directory
sudo systemctl restart readsb  # Restart services (passwordless)
sudo journalctl -fu readsb     # View logs (passwordless)
vnstat -d                      # Check bandwidth usage
adsb-update --help             # View update options

# Enable/disable MLAT as needed:
sudo systemctl enable mlat-client && sudo systemctl start mlat-client   # Enable MLAT
sudo systemctl stop mlat-client && sudo systemctl disable mlat-client   # Disable MLAT
sudo systemctl status mlat-client                                        # Check MLAT status
```

**Security Features:**
- Remote user can **only** SSH from Tailscale network (100.x.x.x)
- Public internet SSH attempts are automatically blocked
- Device owner accounts remain unrestricted (can SSH from anywhere)
- Passwordless sudo for common service management commands

> **🔒 Security Note:** Even if the credentials are publicly known, only machines on your Tailscale network can access the remote user account.

## 📁 Installation Directory Structure

Everything is organized under `/opt/TAK_ADSB/`:
```
/opt/TAK_ADSB/
├── bin/                      # Binaries
│   ├── readsb
│   └── viewadsb
├── scripts/                  # Installer scripts
│   └── adsb_feeder_installer.sh
├── data/                     # Runtime data
├── run/                      # Process runtime files
├── logs/                     # Service logs
├── feeder-info.txt          # Installation details
├── readsb.conf              # Configuration reference
└── mlat-client.conf         # MLAT configuration reference
```

## 🔄 Updating Your Feeder

The installer now includes **self-update functionality** for easy maintenance!

> **⚠️ Important for v4.0 and Earlier Users:**
> 
> The self-update feature (`--update` flag and `adsb-update` command) was introduced in **v5.0**. If you're running v4.0 or earlier:
> 
> 1. **Download and run the latest installer** to upgrade to v5.4:
>    ```bash
>    wget -O adsb_feeder_installer.sh https://raw.githubusercontent.com/cfd2474/TAK-ADSB-Feeder/main/adsb_feeder_installer.sh
>    chmod +x adsb_feeder_installer.sh
>    ./adsb_feeder_installer.sh
>    ```
> 2. **After upgrading to v5.x**, you can use the built-in update commands for all future updates
> 
> Check your version with: `./adsb_feeder_installer.sh --version` (this flag also requires v5.0+)

### Update the Installer Script

Before running a new installation or re-installation:
```bash
# Check current version
./adsb_feeder_installer.sh --version

# Update to latest version
./adsb_feeder_installer.sh --update

# Or download fresh copy
wget https://raw.githubusercontent.com/cfd2474/TAK-ADSB-Feeder/main/adsb_feeder_installer.sh
chmod +x adsb_feeder_installer.sh
```

### Update Installed Components

After installation, use the `adsb-update` command to keep your system current:
```bash
# Update everything (recommended)
adsb-update all

# Update specific components
adsb-update readsb          # Update only readsb decoder
adsb-update mlat            # Update only mlat-client
adsb-update tar1090         # Update only web interface
adsb-update system          # Update only system packages
adsb-update installer       # Update only installer script

# View help
adsb-update --help
```

**What gets updated:**
- `readsb` - Latest ADS-B decoder improvements
- `mlat-client` - Latest multilateration features
- `tar1090` - Latest web interface enhancements
- System packages - Security patches and bug fixes
- Installer script - Latest installer improvements

**Update Safety:**
- Services automatically stop/restart during updates
- Configuration preserved across updates
- Aggregator connection maintained
- Old versions backed up automatically

### Quick One-Liner Update

Download and run the latest installer in one command:
```bash
curl -fsSL https://raw.githubusercontent.com/cfd2474/TAK-ADSB-Feeder/main/update_feeder.sh | bash
```

This will:
- Download the latest installer
- Show version comparison
- Create backup of current version
- Optionally run installation immediately

## 🐛 Troubleshooting

### Services won't start
```bash
sudo journalctl -fu readsb
sudo journalctl -fu mlat-client
sudo journalctl -fu lighttpd
```

### Local tar1090 shows "decoder not working"
```bash
# Check if JSON files are being created
ls -la /run/readsb/

# If directory doesn't exist:
sudo mkdir -p /run/readsb
sudo chown readsb:readsb /run/readsb
sudo systemctl restart readsb
```

### No connection to aggregator
```bash
# Check Tailscale
sudo tailscale status

# Ping aggregator
ping 100.117.34.88
```

### RTL-SDR not detected
```bash
# Check USB
lsusb | grep RTL

# Should show: "Realtek Semiconductor Corp. RTL2838 DVB-T"
```

### MLAT Issues
```bash
# Check MLAT service status
sudo systemctl status mlat-client

# Enable MLAT if disabled
sudo systemctl enable mlat-client
sudo systemctl start mlat-client

# Disable MLAT to conserve bandwidth
sudo systemctl stop mlat-client
sudo systemctl disable mlat-client

# View MLAT logs
sudo journalctl -fu mlat-client
```

### Check bandwidth usage
```bash
# View daily bandwidth usage
vnstat -d

# View monthly totals
vnstat -m

# Monitor live traffic
vnstat -l
```

### Update Issues
```bash
# Check update script exists
which adsb-update

# Check installer version
/opt/TAK_ADSB/scripts/adsb_feeder_installer.sh --version

# Manually download latest installer
cd /opt/TAK_ADSB/scripts
sudo wget -O adsb_feeder_installer.sh https://raw.githubusercontent.com/cfd2474/TAK-ADSB-Feeder/main/adsb_feeder_installer.sh
sudo chmod +x adsb_feeder_installer.sh
```

See [QUICK_START.md](QUICK_START.md) for detailed troubleshooting.

## 📈 Scaling to Multiple Feeders

Each feeder gets a unique name automatically: `hostname_MAC`

**Best Practice - Use Zip Code Naming:**
1. Flash SD card with **Bookworm Lite**
2. Set hostname to `adsb-pi-ZIPCODE` (e.g., `adsb-pi-92882`) **during imaging**
3. Boot Pi and SSH in
4. Run installer
5. **Choose MLAT setting** based on connection type (disable for metered/cellular)
6. Each feeder auto-connects to aggregator
7. **Each feeder gets its own tar1090** at its Tailscale IP
8. **Remote access** available via `ssh remote@[TAILSCALE_IP]` (Tailscale only)
9. **Easy updates** with `adsb-update all` on each feeder

**Example deployment:**
- `adsb-pi-92882` → Corona, CA location (MLAT enabled - fiber internet)
- `adsb-pi-90210` → Beverly Hills, CA location (MLAT disabled - LTE connection)
- `adsb-pi-10001` → New York, NY location (MLAT enabled - cable internet)

**Access all feeders from the aggregator dashboard:**
- Main stats: `http://104.225.219.254/graphs1090/`
- Click any feeder to see individual stats and coverage

**Monitor bandwidth across all feeders:**
- SSH into each feeder as `remote` user (from Tailscale network)
- Run `vnstat -d` to see 90-day bandwidth history
- Useful for cellular/metered connection planning
- Disable MLAT on high-bandwidth feeders to reduce data usage

**Mass Update Strategy:**
```bash
# SSH into each feeder and run:
adsb-update all

# Or create a script to update all feeders:
for ip in 100.x.x.x 100.y.y.y 100.z.z.z; do
  ssh remote@$ip "adsb-update all"
done
```

**Managing MLAT Across Fleet:**
```bash
# Enable MLAT on a feeder
ssh remote@100.x.x.x "sudo systemctl enable mlat-client && sudo systemctl start mlat-client"

# Disable MLAT on metered connection
ssh remote@100.y.y.y "sudo systemctl stop mlat-client && sudo systemctl disable mlat-client"

# Check MLAT status across all feeders
for ip in 100.x.x.x 100.y.y.y 100.z.z.z; do
  echo "=== $ip ==="
  ssh remote@$ip "sudo systemctl is-active mlat-client"
done
```

See [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) for mass production strategies.

## 🔒 Security

- **Tailscale** provides end-to-end encryption
- **No public ports** exposed
- **Reusable auth keys** for easy deployment
- **SSH restrictions** - Remote user accessible only from Tailscale network (100.x.x.x)
- **Local web interfaces** only accessible via Tailscale network
- **Organized permissions** with dedicated installation directory
- **Automatic updates** keep security patches current

> **🔑 Auth Key Security:** Never commit Tailscale auth keys to public repositories. The installer prompts for the key at runtime for maximum security.

> **👤 Remote User Security:** Default password is `adsb`. Even with known credentials, SSH access is restricted to Tailscale network only. Consider changing the password after installation: `sudo passwd remote`

> **🌐 Network Isolation:** The SSH restriction ensures that even if credentials are compromised, attackers cannot access feeders without being on your private Tailscale network.

## 🎯 Use Cases

**Individual Feeder Monitoring:**
- Check if a specific Pi is receiving aircraft
- Troubleshoot antenna issues at specific locations
- Compare coverage between different sites
- Verify optimal antenna placement
- Monitor bandwidth usage for cellular deployments
- Control MLAT on per-feeder basis based on connection type

**Network-Wide View:**
- See combined coverage from all feeders
- Total aircraft count across your network
- Network health and performance
- Identify coverage gaps

**Performance Optimization:**
- Compare individual feeder performance
- Identify best performing locations
- Test antenna modifications
- Optimize network placement
- Track bandwidth consumption over 90 days
- Disable MLAT on high-bandwidth or metered connections

**Remote Management:**
- Secure SSH access to all feeders via Tailscale
- Centralized administration with remote user
- Easy log access and service control
- Network statistics monitoring
- Simple update process with `adsb-update`
- Toggle MLAT on/off without reinstallation

**Fleet Maintenance:**
- Update all feeders with single command
- Monitor component versions across fleet
- Automated backup during updates
- Minimal downtime during maintenance
- Flexible MLAT configuration per deployment site

## 🤝 Contributing

Found a bug? Have a suggestion? Open an issue or pull request!

## 📝 License

This project is open source and available under the MIT License.

## 🙏 Credits

Built on top of:
- [readsb](https://github.com/wiedehopf/readsb) by wiedehopf
- [mlat-client](https://github.com/wiedehopf/mlat-client) by wiedehopf
- [tar1090](https://github.com/wiedehopf/tar1090) by wiedehopf
- [Tailscale](https://tailscale.com) for secure networking
- [vnstat](https://humdi.net/vnstat/) for network monitoring

Special thanks to the ADS-B community for their continued development and support!

## 📧 Support

For issues specific to this installer, open a GitHub issue.

For readsb/mlat-client/tar1090 questions, see their respective repositories.

For Tailscale auth key requests, contact: [michael.leckliter@yahoo.com](mailto:michael.leckliter@yahoo.com)

---

**Happy plane spotting!** ✈️

**Monitor each feeder individually, view your network collectively, track your bandwidth, control MLAT per-feeder, and keep everything updated!**

*Last updated: January 16, 2025*
*Current version: v5.4*
