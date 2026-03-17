#!/usr/bin/env bash
# Enable and start/restart tunnel-client when tunnel is configured in .env.
# Matches tunnel_client.py: TUNNEL_AGGREGATOR_URL set non-empty, OR unset/absent with TAKNET_PS_SERVER_HOST_FALLBACK set.
# TUNNEL_AGGREGATOR_URL= (empty) means tunnel explicitly disabled.
UNIT="/etc/systemd/system/tunnel-client.service"
ENV="/opt/adsb/config/.env"
[ -f "$UNIT" ] || exit 0

systemctl daemon-reload 2>/dev/null || true
systemctl enable tunnel-client 2>/dev/null || true

trim() { sed 's/^[[:space:]]*//;s/[[:space:]]*$//'; }

tunnel_should_run() {
    [ -f "$ENV" ] || return 1
    if grep -q '^TUNNEL_AGGREGATOR_URL=' "$ENV" 2>/dev/null; then
        v=$(grep '^TUNNEL_AGGREGATOR_URL=' "$ENV" | head -1 | cut -d= -f2- | tr -d '\r' | trim)
        [ -n "$v" ] && return 0
        return 1
    fi
    fb=$(grep '^TAKNET_PS_SERVER_HOST_FALLBACK=' "$ENV" 2>/dev/null | head -1 | cut -d= -f2- | tr -d '\r' | trim)
    [ -n "$fb" ]
}

if tunnel_should_run; then
    systemctl restart tunnel-client 2>/dev/null || systemctl start tunnel-client 2>/dev/null || true
fi
exit 0
