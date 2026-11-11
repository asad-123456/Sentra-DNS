import argparse
import json
import os
import socket
import struct
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from protocol import (MYDNSMessage, MSG_QUERY, MSG_RESPONSE, MSG_ERROR, TYPE_A,
                      STATUS_SUCCESS, STATUS_NXDOMAIN, STATUS_FORMAT_ERROR)


def load_zone(path):
    with open(path, encoding="utf-8") as f:
        return {k.lower(): v for k, v in json.load(f).items()}


def lookup_zone(domain, zone_data):
    """Return the record dict for a domain, or None if the zone doesn't have it."""
    return zone_data.get(domain.lower())


def build_response(q, zone_data):
    rec = lookup_zone(q.domain, zone_data)
    if rec:
        return MYDNSMessage(q.tx_id, MSG_RESPONSE, TYPE_A, STATUS_SUCCESS,
                            rec["ttl"], q.domain, rec["ip"])
    return MYDNSMessage(q.tx_id, MSG_RESPONSE, TYPE_A, STATUS_NXDOMAIN,
                        0, q.domain, "0.0.0.0")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=53053)
    ap.add_argument("--zone", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "zone.json"))
    a = ap.parse_args()

    zone_data = load_zone(a.zone)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((a.host, a.port))
    sock.settimeout(1.0)  # lets Ctrl+C work on Windows
    print(f"[AUTH] listening on {a.host}:{a.port}, {len(zone_data)} records", flush=True)

    try:
        while True:
            try:
                data, addr = sock.recvfrom(512)
            except socket.timeout:
                continue
            except ConnectionResetError:  # Windows UDP quirk after an ICMP unreachable
                continue

            t0 = time.perf_counter()
            try:
                try:
                    q = MYDNSMessage.unpack(data)
                    # NEW (ADR-016 point 9): reject bytes beyond the length the fields imply
                    expected = 9 + len(q.domain) + (4 if q.msg_type == MSG_RESPONSE else 0)  # NEW
                    if len(data) != expected:  # NEW
                        raise ValueError(f"length {len(data)}, expected {expected} (trailing bytes)")  # NEW
                except (ValueError, TypeError, struct.error) as e:
                    tx = int.from_bytes(data[:2], "big") if len(data) >= 2 else 0
                    err = MYDNSMessage(tx, MSG_ERROR, TYPE_A, STATUS_FORMAT_ERROR,
                                       0, "bad.request")
                    sock.sendto(err.pack(), addr)
                    print(f"[AUTH] FORMAT_ERROR from {addr}: {e}", flush=True)
                    continue

                if q.msg_type != MSG_QUERY:
                    print(f"[AUTH] ignored non-QUERY from {addr}", flush=True)
                    continue

                resp = build_response(q, zone_data)
                sock.sendto(resp.pack(), addr)
                us = (time.perf_counter() - t0) * 1e6
                print(f"[AUTH] {addr} {q.domain} -> {resp.get_status_name()} "
                      f"{resp.ip_address} ttl={resp.ttl} proc={us:.0f}us", flush=True)
            except Exception as e:  # never let one bad packet kill the demo
                print(f"[AUTH] unexpected error from {addr}: {e!r}", flush=True)
    except KeyboardInterrupt:
        print("\n[AUTH] stopped", flush=True)
    finally:
        sock.close()


if __name__ == "__main__":
    main()