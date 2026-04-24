#!/usr/bin/env python3
"""
Bridge ultrafeeder (readsb) → TAKNET-PS aggregator Beast port.

On each inbound connection, opens TCP to UPSTREAM_HOST:UPSTREAM_PORT, sends
ASCII metadata lines before Beast binary bytes:
  TAKNET_FEEDER_CLAIM <uuid>\\n when FEEDER_CLAIM_UUID is set
  TAKNET_FEEDER_MAC <aa:bb:cc:dd:ee:ff>\\n when FEEDER_MAC is valid
then copies bytes both ways (Beast stream unchanged after metadata lines).

Environment:
  LISTEN_HOST     (default 0.0.0.0)
  LISTEN_PORT     (default 39904)
  UPSTREAM_HOST   (required)
  UPSTREAM_PORT   (default 30004)
  FEEDER_CLAIM_UUID  optional; standard 8-4-4-4-12 hex UUID, sent lowercase
  FEEDER_MAC         optional; normalized to lowercase colon MAC before sending
"""
import os
import re
import socket
import threading
from typing import Optional


def _env_int(name: str, default: int) -> int:
    raw = (os.environ.get(name) or "").strip()
    if not raw:
        return default
    return int(raw, 10)


LISTEN_HOST = (os.environ.get("LISTEN_HOST") or "0.0.0.0").strip()
LISTEN_PORT = _env_int("LISTEN_PORT", 39904)
UPSTREAM_HOST = (os.environ.get("UPSTREAM_HOST") or "").strip()
UPSTREAM_PORT = _env_int("UPSTREAM_PORT", 30004)
_CLAIM = (os.environ.get("FEEDER_CLAIM_UUID") or "").strip().lower()
CLAIM_PREFIX = b"TAKNET_FEEDER_CLAIM "
CLAIM_LINE = (CLAIM_PREFIX + _CLAIM.encode("ascii") + b"\n") if _CLAIM else None
_MAC_RAW = (os.environ.get("FEEDER_MAC") or "").strip()


def normalize_mac(mac: str) -> str:
    """Return lowercase aa:bb:cc:dd:ee:ff, or empty string when invalid."""
    h = re.sub(r"[^0-9A-Fa-f]", "", mac or "")
    if len(h) != 12:
        return ""
    return ":".join(h[i:i + 2] for i in range(0, 12, 2)).lower()


_MAC = normalize_mac(_MAC_RAW)
MAC_PREFIX = b"TAKNET_FEEDER_MAC "
MAC_LINE = (MAC_PREFIX + _MAC.encode("ascii") + b"\n") if _MAC else None

_UUID = (os.environ.get("FEEDER_UUID") or "").strip().lower()
UUID_PREFIX = b"TAKNET_FEEDER_UUID "
UUID_LINE = (UUID_PREFIX + _UUID.encode("ascii") + b"\n") if _UUID else None


def _relay(src: socket.socket, dst: socket.socket) -> None:
    try:
        while True:
            data = src.recv(65536)
            if not data:
                break
            dst.sendall(data)
    except OSError:
        pass
    finally:
        try:
            dst.shutdown(socket.SHUT_WR)
        except OSError:
            pass


def _handle_client(client: socket.socket, addr) -> None:
    upstream: Optional[socket.socket] = None
    try:
        upstream = socket.create_connection((UPSTREAM_HOST, UPSTREAM_PORT), timeout=30)
        upstream.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        if CLAIM_LINE:
            upstream.sendall(CLAIM_LINE)
        if MAC_LINE:
            upstream.sendall(MAC_LINE)
        if UUID_LINE:
            upstream.sendall(UUID_LINE)
        t_a = threading.Thread(target=_relay, args=(client, upstream), daemon=True)
        t_b = threading.Thread(target=_relay, args=(upstream, client), daemon=True)
        t_a.start()
        t_b.start()
        t_a.join()
        t_b.join()
    except Exception as exc:
        print(f"[beast-claim-proxy] session {addr}: {exc}")
    finally:
        try:
            client.close()
        except OSError:
            pass
        if upstream is not None:
            try:
                upstream.close()
            except OSError:
                pass


def main() -> None:
    if not UPSTREAM_HOST:
        raise SystemExit("UPSTREAM_HOST is required")

    ss = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    ss.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    ss.bind((LISTEN_HOST, LISTEN_PORT))
    ss.listen(16)
    claim_note = "yes" if CLAIM_LINE else "no"
    mac_note = _MAC if MAC_LINE else "no"
    uuid_note = "yes" if UUID_LINE else "no"
    print(
        f"[beast-claim-proxy] listen {LISTEN_HOST}:{LISTEN_PORT} "
        f"-> {UPSTREAM_HOST}:{UPSTREAM_PORT} claim={claim_note} mac={mac_note} uuid={uuid_note}"
    )
    while True:
        c, a = ss.accept()
        c.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        threading.Thread(target=_handle_client, args=(c, a), daemon=True).start()


if __name__ == "__main__":
    main()
