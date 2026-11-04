import math
import threading
import time
from protocol import (
    HEADER_SIZE, MSG_ERROR, MSG_QUERY, STATUS_FORMAT_ERROR, TYPE_A, MYDNSMessage,
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