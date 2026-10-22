# Member 2 Module Guide: Caching Resolver & Failure Recovery
**Lead:** Atta-Ur-Rehman (`CS-24092`)  
**Core Responsibilities:**
1. Recursive Caching Resolver Engine (`src/resolver.py`)
2. Thread-Safe In-Memory Cache with Dynamic TTL Expiration
3. Concurrency Handling for Multiple Simultaneous Clients (Rubric Criterion 2, Level 4)
4. Failure Handling & Upstream Timeout Recovery (Mandatory Requirement R7)

---

## 1. Technical Overview & Role in the System
As Member 2, your module is the **intelligent heart of the multi-host network**. You sit directly between Host 1 (Client) and Host 3 (Authoritative Server). You decide whether a query can be answered immediately with sub-millisecond latency (Cache Hit) or needs upstream recursive forwarding (Cache Miss).

```
[ HOST 1: CLIENT ]
       |
       | Query (UDP 53000)
       v
+--------------------------------------------------------+
|              HOST 2: CACHING RESOLVER                  |
|          (Atta-Ur-Rehman's Core Module)                |
|                                                        |
|  1. Inspect In-Memory Thread-Safe Cache                |
|     - HIT (expires_at > now): Decrement TTL & Reply   |
|     - MISS: Forward to Host 3 (Port 53053)             |
|                                                        |
|  2. Failure Handler (Timeout / Server Failure)         |
+--------------------------------------------------------+
       |
       | Forward Query (UDP 53053) [Only on Miss]
       v
[ HOST 3: AUTH SERVER ]
```

---

## 2. In-Memory Cache Engine Design

### Thread-Safe Storage
The resolver maintains an in-memory dictionary protected by a `threading.Lock()`:
```python
import time
import threading

class DNSCache:
    def __init__(self):
        self.lock = threading.Lock()
        # Structure: domain -> {"ip": str, "expires_at": float, "initial_ttl": int}
        self.records = {}

    def get(self, domain: str):
        with self.lock:
            if domain in self.records:
                record = self.records[domain]
                now = time.time()
                remaining_ttl = int(record["expires_at"] - now)
                if remaining_ttl > 0:
                    return record["ip"], remaining_ttl
                else:
                    # Expired entry: evict from cache
                    del self.records[domain]
            return None, 0

    def put(self, domain: str, ip: str, ttl: int):
        with self.lock:
            self.records[domain] = {
                "ip": ip,
                "expires_at": time.time() + ttl,
                "initial_ttl": ttl
            }
```

### Key Technical Subtlety: Dynamic TTL Decrement
When serving a **Cache Hit**, you must **never** return the original authoritative TTL. You must return `remaining_ttl = expires_at - current_time`.
* Example: An authoritative record has TTL = 120s.
* Client 1 queries at $T=0$: Cache Miss. Stored with `expires_at = T + 120`. Client 1 receives TTL = 120.
* Client 2 queries at $T=15$: Cache Hit. Client 2 receives TTL = $120 - 15 = 105$.
* This satisfies the strict RFC DNS caching principle and is verified during evaluation!

---

## 3. Concurrency Handling (Targeting Level 4: 8–10 Marks)

Rubric Criterion 2 states: *"the system handles concurrent clients or multiple servers cleanly."*
A single-threaded `recvfrom()` loop blocks if the authoritative server is slow or experiencing packet loss.

### Implementation Pattern
Use `socketserver.ThreadingUDPServer` or Python's `concurrent.futures.ThreadPoolExecutor`:
```python
import socketserver
from protocol import MYDNSMessage, MSG_RESPONSE, STATUS_SUCCESS, STATUS_SERVER_FAILURE

class ThreadedUDPRequestHandler(socketserver.BaseRequestHandler):
    def handle(self):
        data = self.request[0]
        client_sock = self.request[1]
        client_addr = self.client_address

        query = MYDNSMessage.unpack(data)
        
        # 1. Check cache
        cached_ip, remaining_ttl = cache.get(query.domain)
        if cached_ip:
            # CACHE HIT
            resp = MYDNSMessage(
                tx_id=query.tx_id,
                msg_type=MSG_RESPONSE,
                status=STATUS_SUCCESS,
                ttl=remaining_ttl,
                domain=query.domain,
                ip_address=cached_ip
            )
            client_sock.sendto(resp.pack(), client_addr)
            return

        # 2. CACHE MISS: Forward to Authoritative Host (Host 3)
        self.forward_to_auth(query, client_sock, client_addr)
```

---

## 4. Failure Recovery & Upstream Timeout (Requirement R7)

You are responsible for implementing deliberate failure handling when Host 3 is down or unreachable:

1. When forwarding to Host 3:
   * Create a dedicated UDP client socket with a short timeout: `fwd_sock.settimeout(0.5)` (so that 2 upstream attempts take $1.0\text{s}$ total, completing before Host 1's $1.5\text{s}$ client timeout expires).
   * Try up to 2 retransmissions if no response is received.
2. If all retries time out:
   * Construct an error packet with `status = STATUS_SERVER_FAILURE` (`0x02`), `ttl = 0`, `ip_address = '0.0.0.0'`.
   * Send the `SERVER_FAILURE` packet back to the client.
3. Log the deliberate failure event:
   ```
   [RESOLVER WARN] Upstream Host 3 (192.168.43.30:53053) unreachable for domain 'portal.neduet.local'. Returning SERVER_FAILURE to 192.168.43.10.
   ```
4. This delivers empirical proof for Section 8 of the report and demonstrates intentional system resilience under adverse network conditions.

---

## 5. Getting Started Checklist
- [ ] Review `src/protocol.py` written by Member 3.
- [ ] Implement `DNSCache` with thread-safe lock and dynamic TTL decrement.
- [ ] Implement `src/resolver.py` with multi-threaded UDP request handling.
- [ ] Implement upstream query forwarding and timeout detection.
- [ ] Test locally: start `authoritative_server.py`, query resolver via client, test cache hit on second run.
- [ ] Test failure mode: kill `authoritative_server.py`, query resolver, and verify `SERVER_FAILURE` packet is received.

