#!/usr/bin/env python3
"""
TAKNET-PS Feeder Tunnel Client
Connects outbound to the aggregator and forwards HTTP requests to the local web app.
Enables remote access by web address without router port forwarding.
"""

import json
import base64
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
import urllib.error
import re
from pathlib import Path

# Port where map (tar1090) and stats (graphs1090) are served; aggregator uses Host header for proxy
WEB_UI_PORT = 8080

# Optional: websocket-client. Fail with clear message if not installed.
try:
    import websocket
except ImportError:
    print("tunnel_client: websocket-client not installed. Run: pip3 install websocket-client", file=sys.stderr)
    sys.exit(2)

ENV_FILE = Path("/opt/adsb/config/.env")
STATUS_FILE = Path("/opt/adsb/var/tunnel-status.json")
LOCAL_HOST = "127.0.0.1"
# Local Flask app runs on 5000; hitting it directly avoids nginx proxying issues for tunneled requests
LOCAL_PORT = 5000
# Local tar1090/graphs1090 stack (map/stats) served on 8080
TAR1090_HOST = "127.0.0.1"
TAR1090_PORT = WEB_UI_PORT
# Hop-by-hop headers we should not forward to localhost
SKIP_HEADERS = frozenset(
    k.lower()
    for k in (
        "connection",
        "keep-alive",
        "proxy-authenticate",
        "proxy-authorization",
        "te",
        "trailer",
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
                out[key.strip()] = value.strip().strip("'\"")
    return out


def sanitize_feeder_id(raw_name):
    """Strictly sanitize ID to match Aggregator expectations (version 2):
    1. Extract part before version separators ' | v' or '___v'
    2. Lowercase and replace spaces with dashes (preserve underscores)
    3. Replace any char NOT in [a-z0-9_-] with a dash
    4. Collapse multiple dashes and strip them
    """
    if not raw_name:
        return "feeder"
    
    # 1. Extract only the name before version separators
    for sep in (" | v", "___v"):
        if sep in raw_name:
            raw_name = raw_name.split(sep, 1)[0]
            break
            
    # 2. Lowercase and replace spaces with hyphens (Aggregator preserves underscores)
    s = raw_name.strip().lower().replace(" ", "-")
    
    # 3. Strict character filtering (Preserve underscores)
    s = re.sub(r"[^a-z0-9\-_]", "-", s)
    
    # 4. Collapse multiple consecutive dashes into one
    s = re.sub(r"-+", "-", s)
    
    # 5. Strip leading and trailing dashes
    return s.strip("-")


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
        
    raw_id = (env.get("TUNNEL_FEEDER_ID") or env.get("MLAT_SITE_NAME") or "").strip()
    if not raw_id:
        try:
            raw_id = socket.gethostname() or "feeder"
        except Exception:
            raw_id = "feeder"
            
    feeder_id = sanitize_feeder_id(raw_id)
    return url, feeder_id


def get_web_host():
    """Return host:port for this device's web UI (map/stats on 8080). Prefer NetBird IP so
    aggregator proxy works over VPN; else primary interface IP. No scheme, no path.
    """
    # Prefer NetBird IP when connected (same address used for Map/Stats on VPN)
    try:
        if shutil.which("netbird"):
            r = subprocess.run(
                ["netbird", "status", "--json"],
                capture_output=True, text=True, timeout=5,
            )
            if r.returncode == 0 and r.stdout.strip():
                info = json.loads(r.stdout)
                nb_ip = (
                    info.get("netbirdIp")
                    or (info.get("localPeerState") or {}).get("ip")
                    or info.get("ip")
                )
                if nb_ip:
                    nb_ip = nb_ip.split("/")[0].strip()
                    mgmt = info.get("managementState", info.get("management", {}))
                    connected = (
                        mgmt.get("connected", False)
                        if isinstance(mgmt, dict)
                        else (isinstance(mgmt, str) and mgmt.lower() == "connected")
                    )
                    if connected and nb_ip:
                        return f"{nb_ip}:{WEB_UI_PORT}"
            # Plain-text fallback
            r = subprocess.run(["netbird", "status"], capture_output=True, text=True, timeout=5)
            if r.returncode == 0 and "Management: Connected" in (r.stdout or ""):
                for line in (r.stdout or "").splitlines():
                    if "NetBird IP:" in line:
                        nb_ip = line.split("NetBird IP:")[-1].strip().split("/")[0]
                        if nb_ip:
                            return f"{nb_ip}:{WEB_UI_PORT}"
                        break
            # Interface wt0 as fallback for NetBird
            r = subprocess.run(
                ["ip", "addr", "show", "wt0"],
                capture_output=True, text=True, timeout=3,
            )
            if r.returncode == 0 and "inet " in (r.stdout or ""):
                for line in (r.stdout or "").splitlines():
                    line = line.strip()
                    if line.startswith("inet "):
                        nb_ip = line.split()[1].split("/")[0]
                        if nb_ip:
                            return f"{nb_ip}:{WEB_UI_PORT}"
                        break
    except Exception:
        pass
    # Primary IP (route to internet)
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(2)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        if ip and ip != "127.0.0.1":
            return f"{ip}:{WEB_UI_PORT}"
    except Exception:
        pass
    return f"127.0.0.1:{WEB_UI_PORT}"


def log(msg):
    """Print to stderr so systemd captures it (journalctl -u tunnel-client)."""
    print(f"tunnel_client: {msg}", file=sys.stderr)
    sys.stderr.flush()


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


def strip_feeder_prefix(path):
    """Remove one /feeder/<id> prefix when the aggregator forwards prefixed paths.

    Local nginx uses exact paths like ``location = /logo.png``; a request for
    ``/feeder/my-id/logo.png`` would otherwise miss and fall through to Flask (404).
    """
    if not path:
        return path
    qsep = path.find("?")
    q = ""
    if qsep >= 0:
        q = path[qsep:]
        path = path[:qsep]
    if not path.startswith("/feeder/"):
        return path + q
    parts = [p for p in path.split("/") if p]
    if len(parts) < 2 or parts[0] != "feeder":
        return path + q
    if len(parts) == 2:
        return "/" + q if q else "/"
    return "/" + "/".join(parts[2:]) + q


def infer_target(path, headers):
    """Infer which local backend should receive a tunneled request."""
    hdrs = headers or {}
    target = (hdrs.get("X-Tunnel-Target") or hdrs.get("x-tunnel-target") or "").strip().lower()
    if target in ("tar1090", "dashboard"):
        return target
    p = (path or "/").split("?", 1)[0] or "/"
    if (
        p == "/"
        or p.startswith("/graphs1090")
        or p.startswith("/data/")
        or p.startswith("/db2/")
        or p.startswith("/tracks/")
        or p.startswith("/tar1090/")
    ):
        return "tar1090"
    return "dashboard"


def _strip_outbound_headers(headers):
    out = {}
    for k, v in (headers or {}).items():
        kl = k.lower()
        if kl in SKIP_HEADERS:
            continue
        # Never forward a potentially stale content-length; urllib will compute as needed.
        if kl == "content-length":
            continue
        out[k] = v
    return out


def forward_request(method, path, headers, body_b64):
    """Forward request to local backend.

    Returns (status, headers_dict, body_base64, target, upstream_base, path_used).
    """
    body = base64.b64decode(body_b64) if body_b64 else b""
    path = strip_feeder_prefix(path)
    target = infer_target(path, headers)
    if target == "tar1090":
        upstream_host, upstream_port = TAR1090_HOST, TAR1090_PORT
    else:
        upstream_host, upstream_port = LOCAL_HOST, LOCAL_PORT
    upstream_base = f"http://{upstream_host}:{upstream_port}"
    url = f"{upstream_base}{path}"

    req_headers = _strip_outbound_headers(headers)
    # Preserve Host from aggregator if present; otherwise set a sane default.
    if "Host" not in req_headers:
        req_headers["Host"] = f"{upstream_host}:{upstream_port}"

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
        kl = k.lower()
        if kl in SKIP_HEADERS or kl == "content-length":
            continue
        out_headers[k] = v
    body_b64_out = base64.b64encode(resp_body).decode("ascii") if resp_body else ""
    return status, out_headers, body_b64_out, target, upstream_base, path


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
        host_value = get_web_host()
        register_msg = {"type": "register", "feeder_id": feeder_id, "host": host_value}
        ws.send(json.dumps(register_msg))
        log(f"Registered; connected and waiting for requests (host={host_value})")
        write_status(True, feeder_id=feeder_id)
        while True:
            try:
                # Use a timeout so we can send proactive pongs to keep the connection alive
                ws.settimeout(30.0)
                raw = ws.recv()
            except (socket.timeout, websocket.WebSocketTimeoutException):
                # Proactively send a pong if no activity for 30s
                ws.send(json.dumps({"type": "pong"}))
                continue

            if not raw:
                return True
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue
            t = msg.get("type")
            # Note: Server uses standard WS pings; we send proactive JSON pongs above.
            # Do not handle "ping" JSON messages as the server no longer sends them.
            if t == "request":
                req_id = msg.get("id")
                method = msg.get("method", "GET")
                path = msg.get("path", "/")
                headers = msg.get("headers") or {}
                body_b64 = msg.get("body") or ""
                status, resp_headers, resp_b64, target, upstream_base, path_up = forward_request(
                    method, path, headers, body_b64
                )
                log(
                    f"[tunnel-proxy] id={req_id} path={path_up}"
                    + (f" (from {path})" if path != path_up else "")
                    + f" target={target} upstream={upstream_base} status={status}"
                )
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
