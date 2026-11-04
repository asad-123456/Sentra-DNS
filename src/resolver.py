import argparse
import math
import socket
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from protocol import (
    HEADER_SIZE, MSG_ERROR, MSG_QUERY, MSG_RESPONSE, STATUS_FORMAT_ERROR,
    STATUS_SERVER_FAILURE, STATUS_SUCCESS, TYPE_A, MYDNSMessage,
)


class DNSCache:
    """Thread-safe TTL cache. Keys are lowercase domains.

    get() returns (value, remaining_ttl_seconds) or None on a miss/expiry.
    The clock is injectable so tests can fake the passage of time.
    """

    def __init__(self, clock=time.monotonic):
        self._clock = clock
        self._lock = threading.Lock()
        self._entries = {}  # key -> (value, expires_at)

    @staticmethod
    def _key(domain):
        return domain.strip().lower()

    def put(self, domain, value, ttl):
        """Store value for ttl seconds. A ttl <= 0 is never cached."""
        if ttl <= 0:
            return
        with self._lock:
            self._entries[self._key(domain)] = (value, self._clock() + ttl)

    def get(self, domain):
        key = self._key(domain)
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                return None
            value, expires_at = entry
            remaining = expires_at - self._clock()
            if remaining <= 0:
                del self._entries[key]
                return None
            return value, int(math.ceil(remaining))

    def purge_expired(self):
        """Remove expired entries and return how many were removed."""
        now = self._clock()
        with self._lock:
            dead = [k for k, (_, exp) in self._entries.items() if exp <= now]
            for k in dead:
                del self._entries[k]
            return len(dead)

    def clear(self):
        with self._lock:
            self._entries.clear()

    def __len__(self):
        with self._lock:
            return len(self._entries)

BAD_DOMAIN = "bad.request"  # placeholder domain for ERROR replies (ADR-016)


def build_error_reply(data):
    """Build a MSG_ERROR / FORMAT_ERROR reply for a bad client datagram.

    The TxID is copied from the first 2 bytes if there are at least 2;
    otherwise it is 0. The domain is always the placeholder bad.request.
    """
    tx_id = 0
    if isinstance(data, (bytes, bytearray)) and len(data) >= 2:
        tx_id = int.from_bytes(data[:2], "big")
    return MYDNSMessage(
        tx_id, MSG_ERROR, TYPE_A, STATUS_FORMAT_ERROR, 0, BAD_DOMAIN
    ).pack()


def validate_client_datagram(data):
    """Validate one datagram from a client.

    Returns (query, None) if it is a well-formed MSG_QUERY, or
    (None, error_reply_bytes) if it is malformed. Nothing malformed is
    ever forwarded upstream.
    """
    try:
        msg = MYDNSMessage.unpack(data)
    except (ValueError, TypeError):
        return None, build_error_reply(data)

    # unpack() accepts RESPONSE and ERROR packets; a client may only send QUERY.
    if msg.msg_type != MSG_QUERY:
        return None, build_error_reply(data)

    # unpack() ignores trailing bytes; we require an exact length so the
    # original bytes we forward upstream are clean.
    if len(data) != HEADER_SIZE + 1 + len(msg.domain):
        return None, build_error_reply(data)

    return msg, None



UPSTREAM_TIMEOUT = 1.0  # must stay below the client's 1.5 s retry timer


def forward_upstream(data, host, port, timeout=UPSTREAM_TIMEOUT):
    """Send the client's original bytes to Auth and return its reply bytes,
    or None on timeout/error. A fresh connected socket per query means only
    Auth's replies can arrive and concurrent queries never mix."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.settimeout(timeout)
        sock.connect((host, port))
        sock.send(data)
        return sock.recv(512)
    except OSError:  # includes timeout and "connection reset" (Auth down)
        return None
    finally:
        sock.close()


def parse_upstream_reply(raw, query):
    """Return the reply as a message if it is a valid answer to this query,
    else None. The TxID must match; a RESPONSE must also echo the domain."""
    try:
        msg = MYDNSMessage.unpack(raw)
    except (ValueError, TypeError):
        return None
    if msg.tx_id != query.tx_id:
        return None
    if msg.msg_type == MSG_RESPONSE:
        if msg.domain.lower() != query.domain.lower():
            return None
        return msg
    if msg.msg_type == MSG_ERROR:
        return msg
    return None


def build_failure_reply(query):
    return MYDNSMessage(
        query.tx_id, MSG_RESPONSE, TYPE_A, STATUS_SERVER_FAILURE, 0,
        query.domain, "0.0.0.0",
    ).pack()


def handle_datagram(data, cache, upstream):
    """Process one client datagram. Returns (reply_bytes, outcome_label).
    `upstream` is a function: original query bytes -> reply bytes or None."""
    query, error_reply = validate_client_datagram(data)
    if error_reply is not None:
        return error_reply, "FORMAT_ERROR"

    cached = cache.get(query.domain)
    if cached is not None:
        ip, remaining = cached
        reply = MYDNSMessage(
            query.tx_id, MSG_RESPONSE, TYPE_A, STATUS_SUCCESS, remaining,
            query.domain, ip,
        ).pack()
        return reply, "HIT"

    raw = upstream(data)
    msg = parse_upstream_reply(raw, query) if raw is not None else None
    if msg is None:
        return build_failure_reply(query), "SERVER_FAILURE"

    if msg.msg_type == MSG_RESPONSE and msg.status == STATUS_SUCCESS and msg.ttl > 0:
        cache.put(query.domain, msg.ip_address, msg.ttl)
        return msg.pack(), "MISS"
    # NXDOMAIN / TTL 0 / Auth ERROR: relay to the client, never cache.
    return msg.pack(), "RELAY/" + msg.get_status_name()


def serve(listen_host, listen_port, upstream_host, upstream_port,
          timeout=UPSTREAM_TIMEOUT, stop_event=None, on_ready=None, workers=32):
    cache = DNSCache()
    stop = stop_event or threading.Event()
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((listen_host, listen_port))
    sock.settimeout(0.5)  # lets Ctrl+C and stop_event work
    print(f"[RESOLVER] listening on {sock.getsockname()}, "
          f"upstream {upstream_host}:{upstream_port}", flush=True)
    if on_ready:
        on_ready(sock.getsockname())

    def upstream(data):
        return forward_upstream(data, upstream_host, upstream_port, timeout)

    def work(data, addr):
        try:
            t0 = time.perf_counter()
            reply, outcome = handle_datagram(data, cache, upstream)
            sock.sendto(reply, addr)
            ms = (time.perf_counter() - t0) * 1000
            print(f"[RESOLVER] {addr} {outcome} {ms:.2f}ms", flush=True)
        except Exception as e:  # never let one bad packet kill the demo
            print(f"[RESOLVER] unexpected error from {addr}: {e!r}", flush=True)

    try:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            while not stop.is_set():
                try:
                    data, addr = sock.recvfrom(2048)
                except OSError:  # timeout, or Windows UDP reset quirk
                    continue
                pool.submit(work, data, addr)
    finally:
        sock.close()


def main():
    ap = argparse.ArgumentParser(description="MYDNS/1.0 caching resolver")
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=5300)
    ap.add_argument("--upstream-host", default="127.0.0.1")
    ap.add_argument("--upstream-port", type=int, default=53053)
    ap.add_argument("--timeout", type=float, default=UPSTREAM_TIMEOUT)
    a = ap.parse_args()
    try:
        serve(a.host, a.port, a.upstream_host, a.upstream_port, a.timeout)
    except KeyboardInterrupt:
        print("\n[RESOLVER] stopped", flush=True)


if __name__ == "__main__":
    main()