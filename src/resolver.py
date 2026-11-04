import math
import threading
import time


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