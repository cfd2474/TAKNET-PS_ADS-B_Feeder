#!/bin/bash
# TAKNET-PS: Refresh FR24/PiAware feed sessions daily
# Helps recover from long-lived upstream session stalls where containers keep running
# but aggregator websites show feeder as disconnected.

set -e

ENV_FILE="/opt/adsb/config/.env"
COMPOSE_FILE="/opt/adsb/config/docker-compose.yml"
LOG="/var/log/taknet-feed-refresh.log"

ts() {
    date '+%Y-%m-%d %H:%M:%S'
}

log() {
    echo "$(ts) - $1" >> "$LOG"
}

env_get() {
    local key="$1"
    grep "^${key}=" "$ENV_FILE" 2>/dev/null | cut -d'=' -f2-
}

env_true() {
    [ "$(echo "$1" | tr '[:upper:]' '[:lower:]')" = "true" ]
}

restart_if_enabled() {
    local svc="$1"
    local enabled_key="$2"
    local enabled_val
    enabled_val="$(env_get "$enabled_key")"

    if ! env_true "$enabled_val"; then
        log "$svc skipped (${enabled_key} is not true)"
        return 0
    fi

    if ! docker ps --format '{{.Names}}' | grep -qx "$svc"; then
        log "$svc enabled but container not running (skipped)"
        return 0
    fi

    if docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" restart "$svc" >> "$LOG" 2>&1; then
        log "$svc restart succeeded"
    else
        log "$svc restart failed"
    fi
}

if [ ! -f "$ENV_FILE" ] || [ ! -f "$COMPOSE_FILE" ]; then
    log "feed refresh skipped (.env or docker-compose missing)"
    exit 0
fi

log "daily feed refresh starting"
restart_if_enabled "fr24" "FR24_ENABLED"
restart_if_enabled "piaware" "PIAWARE_ENABLED"
log "daily feed refresh finished"

