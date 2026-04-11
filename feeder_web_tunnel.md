# TAKNET-PS Feeder Web Tunnel Documentation

This document serves as the definitive technical reference for the **Web Tunnel** protocol used to proxy data between the TAKNET-PS Aggregator and individual Feeders. It provides the exact specifications for connection, registration, and message routing as of **v3.0.44**.

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
  "host": "100.85.x.x:8080"
}
```

*   **`feeder_id`**: The unique identifier derived from the Feeder's configuration. It must follow the strict sanitization logic defined in Section 4.
*   **`host`**: (Recommended) The primary IP/hostname and port the feeder's web stack listens on. The Aggregator uses this string to populate the `Host` header when proxying, ensuring correct internal routing on the feeder side.

---

## 4. Deterministic ID Sanitization

The Aggregator and Feeder must use the **exact same algorithm** to derive the `feeder_id`. The SPEC for v3.0.44 onwards is:

### The Algorithm
1.  **Split by Separator**: If the source string contains an MLAT separator (` | v` or `___v`), only the part **before** the separator is used. (Do not split by single pipers `|` if they appear inside the name).
2.  **Normalization**: Convert the entire string to lowercase.
3.  **Basic Replacement**: Replace all **Spaces** with a single hyphen (`-`).
4.  **Preservation**: **Underscores (`_`) must be preserved**. Do not convert them to hyphens.
5.  **Strict Filtering**: Replace any character that is **NOT** a lowercase letter (`a-z`), a number (`0-9`), a hyphen (`-`), or an underscore (`_`) with a hyphen.
6.  **Deduping**: Collapse multiple consecutive hyphens into a single hyphen (e.g., `--` -> `-`).
7.  **Trimming**: Strip any leading or trailing hyphens from the final string.

**Example:** `"My Feeder | v3.0"` → `"my-feeder"`  
**Example:** `"Feeder_Site_#1"` → `"feeder_site_1"`

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
    "Accept-Encoding": "gzip",
    "Host": "100.85.x.x:8080"
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
    "Content-Type": "text/html",
    "Content-Security-Policy": "upgrade-insecure-requests"
  },
  "body": "base64_encoded_body_or_empty_string"
}
```

---

## 6. Target-Based Routing (`X-Tunnel-Target`)

The Aggregator injects an `X-Tunnel-Target` header into every request. The Feeder Client uses this to determine the local backend port:

| Target | Description | Preferred Local Destination |
| :--- | :--- | :--- |
| `dashboard` | Feeder management UI and APIs | `http://127.0.0.1:5000` |
| `tar1090` | Map and data statistics stack | `http://127.0.0.1:8080` |

If the header is missing, the Feeder infers the target based on the path (e.g., paths starting with `/data/`, `/graphs1090/`, or `/tar1090/` target `tar1090` on port 8080).

---

## 7. Content Security Policy (Global Header Injection)

To resolve "Mixed Content" blockers for services that request resources over plain HTTP (like `tar1090` or `graphs1090`), the Feeder Client **must** inject the following header into **every tunneled response**:

`Content-Security-Policy: upgrade-insecure-requests`

This instruction tells the browser to automatically upgrade all insecure resource requests (CSS/JS/Images) to HTTPS before they leave the browser. By using a header-level policy, the Feeder ensures compatibility even for:
- **Cached Responses (304)**: The browser continues to honor the security policy.
- **Compressed Traffic (Gzip)**: No HTML parsing or body-rewriting is required.

---

## 8. Heartbeat & Reliability

### 8.1 Idle Pongs
The Feeder Client maintains connection health by sending a JSON message: `{"type": "pong"}` if the connection has been idle for 30 seconds. This prevents intermediate firewall or VPN idle-timeouts.

### 8.2 JSON Pings
The server may send a JSON message: `{"type": "ping"}`. The Feeder must respond with `{"type": "pong"}` to maintain the application-level keep-alive.

### 8.3 Reconnection Logic
If the connection is lost, the Feeder Client implements an exponential backoff (e.g., 5s starting, doubling up to a max of 300s) to avoid slamming the Tunnel Service.

---

## 9. Status Codes Reference
- **4000**: Registration error (Timeout or invalid first message).
- **4001**: Duplicate connection (Connection replaced by a newer one with same ID).
- **503 (Aggregator Response)**: Feeder is currently offline (No WebSocket registered).
- **504 (Aggregator Response)**: Gateway Timeout (Feeder failed to respond to a request within 30s).
