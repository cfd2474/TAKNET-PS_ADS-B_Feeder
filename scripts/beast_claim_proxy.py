#!/usr/bin/env python3
"""
Bridge ultrafeeder (readsb) → TAKNET-PS aggregator Beast port.

On each inbound connection, opens TCP to UPSTREAM_HOST:UPSTREAM_PORT, sends
one ASCII line TAKNET_FEEDER_CLAIM <uuid>\\n when FEEDER_CLAIM_UUID is set,
then copies bytes both ways (Beast binary unchanged after the line).

Environment:
  LISTEN_HOST     (default 0.0.0.0)
  LISTEN_PORT     (default 39904)
  UPSTREAM_HOST   (required)
  UPSTREAM_PORT   (default 30004)
  FEEDER_CLAIM_UUID  optional; standard 8-4-4-4-12 hex UUID, sent lowercase
"""
import os
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
    print(
        f"[beast-claim-proxy] listen {LISTEN_HOST}:{LISTEN_PORT} "
        f"-> {UPSTREAM_HOST}:{UPSTREAM_PORT} claim={claim_note}"
    )
    while True:
        c, a = ss.accept()
        c.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        threading.Thread(target=_handle_client, args=(c, a), daemon=True).start()


if __name__ == "__main__":
    main()
