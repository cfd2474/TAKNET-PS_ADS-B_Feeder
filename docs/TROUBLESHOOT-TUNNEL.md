# Troubleshooting: Feeder tunnel (aggregator says not connected)

If the **Dashboard** shows tunnel status **Running** but the **aggregator** says the feeder is not connected, run these on the **feeder** (SSH or local).

---

## 1. Service logs (what the client is doing)

```bash
sudo journalctl -u tunnel-client -n 100 --no-pager
```

Look for:

- **`tunnel_client: Registered; connected and waiting for requests`** — Client thinks it’s connected. If aggregator still says not connected, the problem is likely on the aggregator side.
- **`tunnel-proxy: id=... path=/... target=... status=...`** — Shows live request flow. If you don't see these when visiting the tunnel URL, the Aggregator is not correctly routing requests to your feeder.
- **`[tunnel-csp] Injected...`** — (Legacy feature in v3.0.41-43). v3.0.44 now uses header-based injection which is quieter but more robust.
- **`tunnel_client: Connection closed by server or network`** — Aggregator or network closed the connection; check aggregator logs and network.

---

## 2. Status file (did it ever register?)

```bash
cat /opt/adsb/var/tunnel-status.json
```

- **`"connected": true`** — Client has registered at least once this run. If aggregator still says offline, issue is likely on aggregator side.
- **`"connected": false`, `"error": "Connect failed: ..."`** — Feeder cannot reach the aggregator; fix URL, DNS, or firewall.
- **`"error": "connection closed"`** — Was connected then dropped; check aggregator and network.

---

## 3. Config (URL and feeder_id)

```bash
grep -E "TUNNEL_AGGREGATOR_URL|TAKNET_PS_SERVER_HOST_FALLBACK|TUNNEL_FEEDER_ID|MLAT_SITE_NAME" /opt/adsb/config/.env
```

- Tunnel URL is built from `TUNNEL_AGGREGATOR_URL` (if set) or `TAKNET_PS_SERVER_HOST_FALLBACK`, with path `/tunnel`.
- `feeder_id` is from `TUNNEL_FEEDER_ID`, or `MLAT_SITE_NAME`, or hostname. It must match what the aggregator expects (e.g. used in `/feeder/<feeder_id>/`).

---

## 4. Quick connectivity test (from feeder)

```bash
python3 -c "
import socket
# Replace with your aggregator host
host = 'adsb.tak-solutions.com'
port = 443
s = socket.create_connection((host, port), timeout=5)
print('TCP to', host, 'port', port, 'OK')
s.close()
"
```

If this fails, the feeder cannot reach the aggregator (firewall, DNS, or wrong host).

---

## 5. Auto-start after update

Install/update runs `ensure-tunnel-client.sh`: if `TAKNET_PS_SERVER_HOST_FALLBACK` is set (or `TUNNEL_AGGREGATOR_URL` is non-empty), the tunnel unit is enabled and started. Empty `TUNNEL_AGGREGATOR_URL=` disables tunnel.

## 6. Restart and re-check

After changing `.env` or fixing network:

```bash
sudo systemctl restart tunnel-client
sleep 5
sudo journalctl -u tunnel-client -n 30 --no-pager
cat /opt/adsb/var/tunnel-status.json
```

**Settings:** Dashboard → Settings → **Restart tunnel service** (or batch restart with “Remote access tunnel”).

## 7. Mixed Content / Page Loading Issues

If the page loads but is missing CSS, JS, or images:
- **Hard Refresh**: Modern browsers cache insecure responses. Perform a **Hard Refresh** (`Cmd+Shift+R` or `Ctrl+F5`) to force the browser to pick up the new **Content-Security-Policy** header introduced in v3.0.44.
- **Check Headers**: Inspect the response in your browser's Network tab. You should see `Content-Security-Policy: upgrade-insecure-requests`.

---

## Summary

| What you see | Likely cause |
|--------------|--------------|
| Log: "Connect failed: Connection refused" | Aggregator not listening on 443, or no WebSocket at `/tunnel` |
| Log: "Connect failed: ..." (TLS/SSL) | Certificate or SNI issue on aggregator |
| Log: "Registered; connected" but aggregator says offline | Aggregator not storing or listing the feeder; fix aggregator |
| Status file: "connected": false, "error": "..." | Use the error message; fix URL or network |
| Page loads but "Mixed Content" blocks | Browser cache. Perform a **Hard Refresh**. |
