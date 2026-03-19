#!/bin/bash
# TAKNET-PS: Periodic reboot checker
# Intended to be called frequently by cron (e.g. every minute).

PY="/opt/adsb/scripts/periodic_reboot.py"
if [ ! -f "$PY" ]; then
  exit 0
fi

exec /usr/bin/python3 "$PY" >> /var/log/taknet-periodic-reboot.cron.log 2>&1

