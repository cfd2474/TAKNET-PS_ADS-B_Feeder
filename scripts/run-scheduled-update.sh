#!/bin/bash
# TAKNET-PS: Run update at 02:00 if scheduled (priority 2 overnight update)
# Called by cron daily at 02:00. If flag file exists, run updater and clear flag.

FLAG="/opt/adsb/var/scheduled-update"
UPDATER="/opt/adsb/scripts/updater.sh"
LOG="/var/log/taknet-scheduled-update.log"

if [ ! -f "$FLAG" ]; then
    exit 0
fi

echo "$(date '+%Y-%m-%d %H:%M:%S') - Scheduled update starting (priority 2)" >> "$LOG"
rm -f "$FLAG"

if [ ! -x "$UPDATER" ]; then
    echo "$(date '+%Y-%m-%d %H:%M:%S') - Updater not found or not executable" >> "$LOG"
    exit 1
fi

bash "$UPDATER" >> "$LOG" 2>&1
echo "$(date '+%Y-%m-%d %H:%M:%S') - Scheduled update finished" >> "$LOG"
