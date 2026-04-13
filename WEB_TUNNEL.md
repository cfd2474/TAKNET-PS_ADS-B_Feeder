# Web Tunnel Specification

This document defines the technical process, requirements, and protocol for the **Web Tunnel** used to proxy traffic from the TAKNET-PS Aggregator to individual Feeders. This is the primary reference for the Feeder Client AI to ensure synchronization with current development.

## 1. Overview

The Web Tunnel allows the Aggregator to serve a Feeder's local web UI and APIs over a public URL (e.g., `https://aggregator/feeder/<feeder_id>/`) without requiring the Feeder to have a public IP or open ports. 

It uses a persistent **WebSocket connection** between the Feeder (Client) and the Tunnel Service (Server). HTTP requests from the Aggregator are "tunneled" over this WebSocket as JSON messages, processed locally by the Feeder, and returned as JSON responses.

---

## 2. Architecture

The system consists of three components:

1.  **Aggregator (Flask/Nginx)**: Receives browser requests. Forwards them to the Tunnel Service via an internal REST API (`/proxy`).
2.  **Tunnel Service (FastAPI)**: Manages WebSocket connections from Feeders. Maps `feeder_id` to the active WebSocket. Bridges HTTP requests to WebSocket messages.
3.  **Feeder (Tunnel Client)**: Maintains a persistent WebSocket to the Tunnel Service. Receives `request` messages, makes local HTTP calls to its own backends, and returns `response` messages.

---

## 3. WebSocket Connection

### Endpoint
`wss://<aggregator-domain>/tunnel`

### Registration (Crucial)
Immediately upon connecting, the Feeder **must** send a `register` message. If the first message is not `register`, or if it lacks a `feeder_id`, the server will close the connection.

**Message Frame Type**: The `register` message (and all subsequent messages) **must be sent as a WebSocket TEXT frame**. Binary frames are ignored or may cause connection closure by the server.

**Register Message Format:**
```json
{
  "type": "register",
  "feeder_id": "92882-test_test_test",
  "host": "100.85.149.249:8080",
  "version": "3.0.49"
}
```

*   **`feeder_id`**: The unique identifier for the feeder (must match the ID the Aggregator expects). This should be a "clean" name **without version data**. See [ID Sanitization](#id-sanitization) below.
*   **`host`**: (Recommended) The local `host:port` the feeder's web stack listens on (e.g., NetBird IP). The Aggregator uses this for the `Host` header to ensure correct routing on the feeder side.
*   **`version`**: The current software version of the feeder. The Aggregator uses this for tracking and update alerts.

### ID Sanitization
The Aggregator applies a strict sanitization process to derive the `feeder_id`. The Feeder Client **must** use the same logic to ensure the `register` ID matches the one the dashboard generates.

**Sanitization Algorithm (Pseudo-python):**
```python
import re

def sanitize_feeder_id(raw_name):
    # 1. Lowercase and replace spaces with dashes
    s = raw_name.lower().replace(" ", "-")
    # 2. Replace any character NOT in [a-z0-9_-] with a dash
    s = re.sub(r"[^a-z0-9\-_]", "-", s)
    # 3. Collapse multiple consecutive dashes into one
    s = re.sub(r"-+", "-", s)
    # 4. Strip leading and trailing dashes
    return s.strip("-")
```

> [!IMPORTANT]
> If your MLAT Site Name is `My Feeder | v1.0`, the `raw_name` used for sanitization should be the part BEFORE the version pip (`My Feeder`). The resulting `feeder_id` would be `my-feeder`.

---

## 4. Message Protocol

All messages are JSON strings sent over the WebSocket.

### A. Incoming Request (`Server -> Feeder`)
When a request is proxied, the Feeder receives:
```json
{
  "type": "request",
  "id": "uuid-v4-string",
  "method": "GET",
  "path": "/api/status?query=1",
  "headers": {
    "X-Tunnel-Target": "dashboard",
    "Host": "127.0.0.1:8080",
    "Accept-Encoding": "identity",
    ...
  },
  "body": "base64_encoded_body_or_empty_string"
}
```

### B. Outgoing Response (`Feeder -> Server`)
The Feeder must respond within **30 seconds**:
```json
{
  "type": "response",
  "id": "uuid-v4-string",
  "status": 200,
  "headers": {
    "Content-Type": "application/json",
    ...
  },
  "body": "base64_encoded_body_or_empty_string"
}
```

### C. Heartbeat
Feeders should handle `ping`/`pong` to keep the connection alive. The server expects consistent activity.

---

## 5. Routing Requirements (`X-Tunnel-Target`)

The Aggregator includes an `X-Tunnel-Target` header to help the Feeder route the request to the correct local backend:

| Target | Description | Local Destination (Example) |
| :--- | :--- | :--- |
| `dashboard` | Feeder App pages/APIs (`/dashboard`, `/api/...`) | `http://localhost:5000` |
| `tar1090` | Map/Stats paths (`/graphs1090/`, `/data/`) | `http://localhost:8080` (nginx) |

**Logic for the Feeder Client:**
- If `X-Tunnel-Target` is `tar1090`, bypass the app backend and send directly to the local web server port (8080).
- If `X-Tunnel-Target` is `dashboard`, send to the feeder app backend.

---

## 6. Path Mapping & Rewriting

### Aggregator Side
1.  **Prefix Removal**: A request to `/feeder/<id>/api/config` has the prefix stripped. The tunneled `path` becomes `/api/config`.
2.  **HTML/JS Rewriting**: The Aggregator rewrites URLs in the response (e.g., `href="/static/..."` -> `href="/feeder/<id>/static/..."`) so subsequent browser requests stay within the tunnel.

### Feeder Side
1.  **Identity Encoding**: The Aggregator sets `Accept-Encoding: identity` to ensure it receives plain text for rewriting. The Feeder should honor this or be prepared for the Aggregator to decompress the body for rewriting.
2.  **Base URL**: Use `<base href="...">` injection (handled by Aggregator) to ensure relative links work.

---

## 7. Configuration & Requirements

- **Encoding**: Bodies must be **Base64 encoded** in both directions to safely handle binary data (images, compressed JS).
- **Timeouts**: 
    - Registration must occur within **30 seconds** of connection.
    - Proxied requests timeout after **30 seconds**.
- **Normalization**: The Aggregator may try alternate `feeder_id` formats (changing `_` to `-`) when looking up proxied paths, but the **Registration ID** should strive for an exact match to avoid overhead.

---

## 8. Error Codes & Troubleshooting

### WebSocket Close Codes
- **4000**: Registration error (Missing `feeder_id` or invalid first message). Check that you are sending the `register` message immediately after `on_open`.
- **4001**: Duplicate connection. A new connection with the same `feeder_id` has replaced the old one.

### Troubleshooting "Not Connected"
If the Aggregator Dashboard shows the feeder as offline or returns a **503 Feeder Offline** error:

1.  **Verify `feeder_id` Case**: Ensure the ID sent in the `register` message is **strictly lowercase**.
2.  **Verify Frame Type**: Ensure your WebSocket client is sending a **Text Frame**, not a Binary Frame.
3.  **Check WebSocket URL**: Ensure you are connecting to `wss://<domain>/tunnel` (no trailing slash).
4.  **Register Timeout**: You have **30 seconds** from the moment the TCP/TLS connection is established to send the `register` JSON message.
5.  **JSON Structure**: Ensure types are strings and matches the spec exactly. No extra fields should be required, but `type` and `feeder_id` are mandatory.

---

## 9. API Surface Summary

See [FEEDER_WEB_API_REFERENCE.md](file:///Users/michaelleckliter/Documents/cursor/TAKNET-PS_Aggregator/docs/FEEDER_WEB_API_REFERENCE.md) for the full list of APIs the Feeder must implement and expose through the tunnel.
