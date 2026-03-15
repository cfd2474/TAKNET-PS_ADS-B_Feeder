#!/usr/bin/env python3
"""
TAKNET-PS Feeder Tunnel Client
Connects outbound to the aggregator and forwards HTTP requests to the local web app.
Enables remote access by web address without router port forwarding.
"""

import json
import base64
import socket
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

# Optional: websocket-client. Fail with clear message if not installed.
try:
    import websocket
except ImportError:
    print("tunnel_client: websocket-client not installed. Run: pip3 install websocket-client", file=sys.stderr)
    sys.exit(2)

ENV_FILE = Path("/opt/adsb/config/.env")
STATUS_FILE = Path("/opt/adsb/var/tunnel-status.json")
LOCAL_HOST = "127.0.0.1"
LOCAL_PORT = 80
# Hop-by-hop headers we should not forward to localhost
SKIP_HEADERS = frozenset(
    k.lower()
    for k in (
        "connection",
        "keep-alive",
        "proxy-authenticate",
        "proxy-authorization",
        "te",
        "trailers",
        "transfer-encoding",
        "upgrade",
    )
)


def read_env():
    """Read .env into a dict."""
    out = {}
    if not ENV_FILE.exists():
        return out
    with open(ENV_FILE) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                out[key.strip()] = value.strip()
    return out


def get_config():
    """Return (tunnel_url, feeder_id). If tunnel_url is falsy, tunnel is disabled.
    Default: use TAKNET_PS_SERVER_HOST_FALLBACK (public) so tunnel works without NetBird.
    Set TUNNEL_AGGREGATOR_URL= (empty) to disable; set to a host to override default.
    """
    env = read_env()
    url = env.get("TUNNEL_AGGREGATOR_URL")
    if url is None:
        # Not set: default to public aggregator host so tunnel is on and works without VPN
        url = (env.get("TAKNET_PS_SERVER_HOST_FALLBACK") or "").strip()
    else:
        url = (url or "").strip()
    if not url:
        return "", ""
    # Ensure wss:// or ws://
    if not url.startswith(("ws://", "wss://")):
        url = "wss://" + url
    # Append /tunnel if no path
    if url.rstrip("/").endswith(("com", "net", "org")) or "/" not in url.split("//", 1)[-1]:
        url = url.rstrip("/") + "/tunnel"
    feeder_id = (env.get("TUNNEL_FEEDER_ID") or env.get("MLAT_SITE_NAME") or "").strip()
    if not feeder_id:
        try:
            feeder_id = socket.gethostname() or "feeder"
        except Exception:
            feeder_id = "feeder"
    # Sanitize for URL path: replace spaces with dashes
    feeder_id = feeder_id.replace(" ", "-").lower()
    return url, feeder_id


def log(msg):
    """Print to stderr so systemd captures it (journalctl -u tunnel-client)."""
    print(f"tunnel_client: {msg}", file=sys.stderr)


def write_status(connected, feeder_id=None, error=None):
    """Write tunnel status for dashboard and troubleshooting."""
    try:
        STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)
        if connected and feeder_id:
            STATUS_FILE.write_text(
                json.dumps({
                    "connected": True,
                    "feeder_id": feeder_id,
                    "since": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                }) + "\n"
            )
        elif STATUS_FILE.exists():
            STATUS_FILE.write_text(
                json.dumps({
                    "connected": False,
                    "error": error,
                    "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                }) + "\n"
            )
        else:
            STATUS_FILE.write_text(
                json.dumps({"connected": False, "error": error}) + "\n"
            )
    except Exception as e:
        log(f"Could not write status file: {e}")


def forward_request(method, path, headers, body_b64):
    """Forward request to local web app; return (status, headers_dict, body_base64)."""
    body = base64.b64decode(body_b64) if body_b64 else b""
    url = f"http://{LOCAL_HOST}:{LOCAL_PORT}{path}"
    req_headers = {}
    for k, v in (headers or {}).items():
        if k.lower() in SKIP_HEADERS:
            continue
        req_headers[k] = v
    # Avoid urllib default headers that might override
    if "Host" not in req_headers:
        req_headers["Host"] = f"{LOCAL_HOST}:{LOCAL_PORT}"
    req = urllib.request.Request(url, data=body if method in ("POST", "PUT", "PATCH") else None, method=method, headers=req_headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            status = resp.getcode()
            resp_headers = dict(resp.headers)
            resp_body = resp.read()
    except urllib.error.HTTPError as e:
        status = e.code
        resp_headers = dict(e.headers) if e.headers else {}
        try:
            resp_body = e.read()
        except Exception:
            resp_body = b""
    except Exception as e:
        status = 502
        resp_headers = {"Content-Type": "text/plain"}
        resp_body = f"Bad Gateway: {e}".encode()
    # Drop hop-by-hop and normalize
    out_headers = {}
    for k, v in resp_headers.items():
        if k.lower() in SKIP_HEADERS:
            continue
        out_headers[k] = v
    body_b64_out = base64.b64encode(resp_body).decode("ascii") if resp_body else ""
    return status, out_headers, body_b64_out


def run_once(ws_url, feeder_id):
    """Connect, register, and process messages until disconnect. Returns True if should reconnect."""
    log(f"Connecting to {ws_url} as feeder_id={feeder_id}")
    write_status(False, error="connecting")
    try:
        ws = websocket.create_connection(ws_url, timeout=30)
    except Exception as e:
        log(f"Connect failed: {e}")
        write_status(False, error=str(e))
        return True
    try:
        ws.send(json.dumps({"type": "register", "feeder_id": feeder_id}))
        log("Registered; connected and waiting for requests")
        write_status(True, feeder_id=feeder_id)
        while True:
            raw = ws.recv()
            if not raw:
                return True
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue
            t = msg.get("type")
            if t == "ping":
                ws.send(json.dumps({"type": "pong"}))
                continue
            if t == "request":
                req_id = msg.get("id")
                method = msg.get("method", "GET")
                path = msg.get("path", "/")
                headers = msg.get("headers") or {}
                body_b64 = msg.get("body") or ""
                status, resp_headers, resp_b64 = forward_request(method, path, headers, body_b64)
                ws.send(
                    json.dumps(
                        {
                            "type": "response",
                            "id": req_id,
                            "status": status,
                            "headers": resp_headers,
                            "body": resp_b64,
                        }
                    )
                )
                continue
    except websocket.WebSocketConnectionClosedException:
        log("Connection closed by server or network")
        write_status(False, error="connection closed")
        return True
    except Exception as e:
        log(f"Error: {e}")
        write_status(False, error=str(e))
        return True
    finally:
        write_status(False, error="disconnected")
        try:
            ws.close()
        except Exception:
            pass
    return True


def main():
    ws_url, feeder_id = get_config()
    if not ws_url:
        # Tunnel disabled
        sys.exit(0)
    backoff = 5
    max_backoff = 300
    while True:
        try:
            if run_once(ws_url, feeder_id):
                time.sleep(backoff)
                backoff = min(backoff * 2, max_backoff)
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"tunnel_client: {e}", file=sys.stderr)
            time.sleep(backoff)
            backoff = min(backoff * 2, max_backoff)
    sys.exit(0)


if __name__ == "__main__":
    main()
