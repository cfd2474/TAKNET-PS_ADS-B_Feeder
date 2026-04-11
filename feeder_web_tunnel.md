# TAKNET-PS Feeder Web Tunnel Documentation

This document serves as the definitive technical reference for the **Web Tunnel** protocol used to proxy data between the TAKNET-PS Aggregator and individual Feeders. It provides the exact specifications for connection, registration, and message routing.

## 1. Architecture Overview

The Web Tunnel enables remote access to a Feeder's local web stack without requiring public IP addresses or open firewall ports. It works by establishing a persistent, bidirectional **WebSocket connection** between the Feeder (Client) and the Tunnel Service (Server).

*   **Aggregator (Flask/Nginx)**: Receives user browser requests. Determines if the request is for a tunneled feeder.
*   **Tunnel Service (FastAPI)**: Maintains the registry of active Feeder WebSocket connections. Bridges HTTP requests coming from the Aggregator into WebSocket messages.
*   **Feeder (Tunnel Client)**: Connects outbound to the Aggregator. Receives tunneled requests, makes local HTTP calls to backend services, and returns responses.

---

## 2. WebSocket Connection Dynamics

### 2.1 Endpoint
`wss://<aggregator-domain>/tunnel`

### 2.2 Strict Requirements
1.  **Frame Type**: All messages (registration and proxied data) **must be sent as WebSocket TEXT frames**. Binary frames are not supported and may lead to connection termination.
2.  **Handshake Timeline**: The Feeder has a **30-second window** after the WebSocket `on_open` event to send the `register` message. Failure to register within this window results in the server closing the connection with code `4000`.

---

## 3. Registration Handshake

The first message sent by the Feeder **must** be a `register` type JSON object.

### Register Message Schema
```json
{
  "type": "register",
  "feeder_id": "sanitized-id-string",
  "host": "127.0.0.1:8080"
}
```

*   **`feeder_id`**: The unique identifier derived from the Feeder's configuration. It must follow the strict sanitization logic defined in Section 4.
*   **`host`**: (Recommended) The local `host:port` the feeder's web stack listens on (e.g., its NetBird IP). The Aggregator uses this string to populate the `Host` header when proxying, ensuring correct internal routing on the feeder side.

---

## 4. Deterministic ID Sanitization

The Aggregator and Feeder must use the **exact same algorithm** to derive the `feeder_id`. This prevents "Feeder Offline" errors caused by mismatched keys in the routing table.

### The Algorithm
1.  **Split by Piper**: If the source string contains a `|` (common in `MLAT_SITE_NAME`), only the part **before** the first piper is used.
2.  **Normalization**: Convert the entire string to lowercase. Replace all **Spaces** and **Underscores** with a single hyphen (`-`).
3.  **Strict Filtering**: Replace any character that is **NOT** a lowercase letter (`a-z`), a number (`0-9`), a hyphen (`-`), or an underscore (`_`) with a hyphen.
4.  **Deduping**: Collapse multiple consecutive hyphens into a single hyphen (e.g., `--` -> `-`).
5.  **Trimming**: Strip any leading or trailing hyphens from the final string.

**Example:** `"My Feeder | v1.0"` → `"my-feeder"`  
**Example:** `"Feeder_Site_#1"` → `"feeder-site-1"`

---

## 5. Message Protocol

### 5.1 Incoming Request (`Server -> Feeder`)
When a user visits `https://aggregator/feeder/<id>/path`, the Feeder receives a JSON message:
```json
{
  "type": "request",
  "id": "uuid-v4-request-identifier",
  "method": "GET",
  "path": "/api/status",
  "headers": {
    "X-Tunnel-Target": "dashboard",
    "Accept-Encoding": "identity",
    "Host": "127.0.0.1:8080"
  },
  "body": "base64_encoded_body_or_empty_string"
}
```

### 5.2 Outgoing Response (`Feeder -> Server`)
The Feeder must process the request and respond within **30 seconds**:
```json
{
  "type": "response",
  "id": "uuid-v4-request-identifier",
  "status": 200,
  "headers": {
    "Content-Type": "application/json"
  },
  "body": "base64_encoded_body_or_empty_string"
}
```

> [!NOTE]
> **Base64 Encoding**: All message bodies (HTML, JSON, Images, JS) must be Base64 encoded in both directions to ensure binary safety and transmission through JSON.

---

## 6. Target-Based Routing (`X-Tunnel-Target`)

The Aggregator injects an `X-Tunnel-Target` header into every request. The Feeder Client use this to determine the local backend port:

| Target | Description | Preferred Local Destination |
| :--- | :--- | :--- |
| `dashboard` | Feeder management UI and APIs | `http://127.0.0.1:5000` |
| `tar1090` | Map and data statistics stack | `http://127.0.0.1:8080` |

If the header is missing, the Feeder should infer the target based on the path (e.g., paths starting with `/data/` or `/graphs1090/` typically target `tar1090` on port 8080).

---

## 7. Path Mapping & Rewriting

### Prefix Stripping
The Aggregator handles URL prefixing. A request for `/feeder/my-id/api/config` arrives at the Feeder Client with a tunneled `path` of `/api/config`. The Feeder Client does **not** need to handle the `/feeder/<id>/` prefix in its internal routing.

### Content Rewriting
The Aggregator performs real-time rewriting of HTML/JS/CSS to ensure that absolute links (e.g., `/static/style.css`) are updated to work through the tunnel (e.g., `/feeder/id/static/style.css`).
- To facilitate this, the Aggregator requests `Accept-Encoding: identity`. 
- Feeders **must** return uncompressed bodies or the Aggregator will attempt to decompress them for rewriting.

---

## 8. Heartbeat & Reliability

### 8.1 JSON Pings
In addition to standard WebSocket ping frames, the server sends a JSON message: `{"type": "ping"}`. The Feeder must respond with `{"type": "pong"}` to maintain the application-level keep-alive.

### 8.2 Reconnection Logic
If the connection is lost, the Feeder Client should implement an exponential backoff (e.g., 5s starting, doubling up to a max of 300s) to avoid slamming the Tunnel Service during aggregator restarts.

### 8.3 Status Codes Reference
- **4000**: Registration error (Timeout or invalid first message).
- **4001**: Duplicate connection (Connection replaced by a newer one with same ID).
- **503 (Aggregator Response)**: Feeder is currently offline (No WebSocket registered).
- **504 (Aggregator Response)**: Gateway Timeout (Feeder failed to respond to a request within 30s).
