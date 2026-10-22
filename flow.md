# Program Control & Data Flow Audit (`flow.md`)

**Project:** `MYDNS/1.0` — Mini DNS Service (Option B)  
**Course:** CS-327 Computer Communication Networks (Fall 2026)  
**Repository:** `c:\projects\Sentra_DNS`  
**Purpose:** This document provides a comprehensive audit of the execution, control, and data flows of the entire application. It maps how code moves between files and folders, documents which functions invoke which functions, and traces packet lifecycles from in-memory objects to raw wire bytes across the network.

---

## 1. Directory Structure & Component Ownership

```
c:\projects\Sentra_DNS\
├── docs/                                  # Official submission documentation
│   ├── CS-327 CCN CEP Grading Rubric.pdf
│   ├── CS-327 CCN CEP Problem Description and Instructions.pdf
│   ├── project-proposal-v4.md             # Submitted one-page proposal
│   ├── protocol_specification.md          # MYDNS/1.0 RFC specification
│   └── protocol_specification.pdf         # Formatted PDF specification
├── gemini-docs/                           # Detailed developer guides & context
│   ├── gemini.md                          # Master context memory & invariants
│   ├── Implementation Constraint.md       # Modular dependency rules
│   ├── physical_setup_guide.md            # Multi-host deployment & ports
│   ├── project_execution_plan.md          # Milestones & task breakdown
│   ├── rubric_refinements.md              # 50/50 rubric strategy guide
│   ├── member1_asadullah_client_benchmarking.md
│   ├── member2_atta_resolver_caching.md
│   ├── member3_abdur_protocol_authoritative.md
│   └── protocol_implementation_plan.md    # Step-by-step implementation & unit test plan
├── src/                                   # Application source code
│   ├── protocol.py                        # Single shared dependency: SerDes engine
│   ├── client.py                          # Host 1: Client CLI & timer engine
│   ├── resolver.py                        # Host 2: Recursive caching resolver
│   ├── authoritative_server.py            # Host 3: Authoritative zone server
│   └── zone.json                          # Host 3: Master zone database
├── tests/                                 # Verification & benchmarking suite
│   ├── test_protocol.py                   # Protocol SerDes unit tests
│   └── benchmark_runner.py                # Automated RTT benchmarking & graphing
├── Decisions.md                           # Architecture decision records
└── flow.md                                # Program control & data flow audit (This file)
```

### Network Endpoints & Port Map

| Host Identifier | Default IP (Bridged / Hotspot) | Script Executed | Listening Port | Transport |
| :--- | :--- | :--- | :--- | :--- |
| **Host 1: Client** | `192.168.1.10` / `192.168.43.10` | `src/client.py` | Ephemeral OS port | UDP (`SOCK_DGRAM`) |
| **Host 2: Resolver** | `192.168.1.11` / `192.168.43.20` | `src/resolver.py` | `53000` | UDP (`SOCK_DGRAM`) |
| **Host 3: Auth Server** | `192.168.1.12` / `192.168.43.30` | `src/authoritative_server.py` | `53053` | UDP (`SOCK_DGRAM`) |

---

## 2. End-to-End Architectural Flow Diagram

```
+---------------------------------------------------------------------------------------------------------+
|                                         HOST 1: CLIENT ENGINE                                           |
|                                                                                                         |
|   [ CLI / Benchmark ]                                                                                   |
|           │                                                                                             |
|           ▼                                                                                             |
|   client.py::query_domain()                                                                             |
|           │                                                                                             |
|           ├──> protocol.py::MYDNSMessage(msg_type=MSG_QUERY, domain=...)                                |
|           │            │                                                                                |
|           │            └──> MYDNSMessage.pack() ──────────────┐                                         |
|           │                                                   │ (28-byte raw UDP datagram)              |
|   time.perf_counter() [Start Timer]                           │                                         |
|   socket.sendto((resolver_ip, 53000)) ◄───────────────────────┘                                         |
+─────────────────────────────────────────────────────────────────────────────────────────────────────────+
                                                │
                                                ▼  UDP Datagram across Network Link 1
+---------------------------------------------------------------------------------------------------------+
|                                    HOST 2: CACHING RESOLVER ENGINE                                      |
|                                                                                                         |
|   resolver.py::ThreadedUDPRequestHandler.handle()                                                       |
|           │                                                                                             |
|           ├──> protocol.py::MYDNSMessage.unpack(raw_bytes)                                              |
|           │                                                                                             |
|           ├──> resolver.py::DNSCache.get(query.domain)                                                  |
|           │            │                                                                                |
|           │            ├── [CACHE HIT: remaining_ttl > 0]                                               |
|           │            │        │                                                                       |
|           │            │        ├──> MYDNSMessage(msg_type=MSG_RESPONSE, status=SUCCESS, ip=cached_ip)  |
|           │            │        └──> response.pack() (32 bytes) ───► client_sock.sendto(client_addr)    |
|           │            │                                                                                |
|           │            └── [CACHE MISS: expired or absent]                                              |
|           │                     │                                                                       |
|           │                     └──> resolver.py::forward_to_auth(query)                                |
|           │                                  │                                                          |
|           │                                  └──> fwd_sock.sendto((auth_ip, 53053)) ─────┐              |
+──────────────────────────────────────────────────────────────────────────────────────────┼──────────────+
                                                                                           │
                                                                                           ▼  Link 2
+---------------------------------------------------------------------------------------------------------+
|                                   HOST 3: AUTHORITATIVE ZONE SERVER                                     |
|                                                                                                         |
|   authoritative_server.py::main_loop()                                                                  |
|           │                                                                                             |
|           ├──> sock.recvfrom() ───► protocol.py::MYDNSMessage.unpack(data)                              |
|           │                                                                                             |
|           ├──> authoritative_server.py::lookup_zone(domain, zone_db)                                   |
|           │            │                                                                                |
|           │            ├── [DOMAIN FOUND]                                                               |
|           │            │        └──> MYDNSMessage(status=STATUS_SUCCESS, ip=zone_ip, ttl=zone_ttl)     |
|           │            │                                                                                |
|           │            └── [DOMAIN NOT FOUND]                                                           |
|           │                     └──> MYDNSMessage(status=STATUS_NXDOMAIN, ip="0.0.0.0", ttl=0)         |
|           │                                                                                             |
|           └──> response.pack() (32 bytes) ───► sock.sendto(resolver_addr) ──────────────┐              |
+──────────────────────────────────────────────────────────────────────────────────────────┼──────────────+
                                                                                           │
                                                                                           ▼  Link 2 Return
+---------------------------------------------------------------------------------------------------------+
|                               HOST 2: CACHING RESOLVER (RESPONSE HANDLING)                              |
|                                                                                                         |
|   resolver.py::forward_to_auth()                                                                        |
|           │                                                                                             |
|           ├──> fwd_sock.recvfrom() ───► protocol.py::MYDNSMessage.unpack(auth_data)                     |
|           │                                                                                             |
|           ├──> [If status == STATUS_SUCCESS]: resolver.py::DNSCache.put(domain, ip, ttl)                |
|           │                                                                                             |
|           └──> client_sock.sendto(auth_data, client_addr) ──────────────────────────────┐              |
+──────────────────────────────────────────────────────────────────────────────────────────┼──────────────+
                                                                                           │
                                                                                           ▼  Link 1 Return
+---------------------------------------------------------------------------------------------------------+
|                                       HOST 1: CLIENT COMPLETION                                         |
|                                                                                                         |
|   client.py::query_domain()                                                                             |
|           │                                                                                             |
|           ├──> sock.recvfrom()                                                                          |
|           ├──> time.perf_counter() [Stop Timer] ───► Calculate RTT (ms)                                 |
|           ├──> protocol.py::MYDNSMessage.unpack(response_bytes)                                         |
|           ├──> Validate response.tx_id == tx_id                                                         |
|           └──> Return (response, rtt_ms) to caller (CLI display or benchmark aggregator)                |
+---------------------------------------------------------------------------------------------------------+
```

---

## 3. Detailed Step-by-Step Flow Scenarios

### Scenario A: Cache Hit (Immediate Resolver Response)
1. **User / Benchmark Runner** invokes `src/client.py`:
   - `client.py:main()` parses command-line arguments (`--resolver-ip`, `--resolver-port`, `--domain`).
   - Calls `client.py:query_domain(resolver_ip, resolver_port, "portal.neduet.local")`.
2. **Client Serialization:**
   - Instantiates `protocol.py:MYDNSMessage(tx_id=0x1234, msg_type=MSG_QUERY, query_type=TYPE_A, domain="portal.neduet.local")`.
   - Calls `MYDNSMessage.pack()`. Since `msg_type == MSG_QUERY`, only the 8-byte header and domain length/name are packed ($8 + 1 + 19 = 28\text{ bytes}$).
   - Records `t_start = time.perf_counter()`.
   - Sends the 28-byte datagram to `192.168.1.11:53000` via `socket.sendto()`.
3. **Resolver Processing:**
   - `resolver.py:ThreadedUDPRequestHandler.handle()` receives datagram.
   - Calls `protocol.py:MYDNSMessage.unpack(data)`. Unpacks header fields (`!HBBBxH`), extracts domain `portal.neduet.local`.
   - Calls `resolver.py:DNSCache.get("portal.neduet.local")`.
   - `DNSCache` acquires `self.lock`. Compares `time.time()` against `expires_at`.
   - `remaining_ttl = int(expires_at - now) > 0` $\rightarrow$ **Cache Hit**.
   - Releases lock and returns `("10.0.1.5", remaining_ttl)`.
4. **Resolver Response Generation:**
   - Constructs `protocol.py:MYDNSMessage(tx_id=0x1234, msg_type=MSG_RESPONSE, query_type=TYPE_A, status=STATUS_SUCCESS, ttl=remaining_ttl, domain="portal.neduet.local", ip_address="10.0.1.5")`.
   - Calls `MYDNSMessage.pack()`. Appends 4-byte packed IPv4 address ($8 + 1 + 19 + 4 = 32\text{ bytes}$).
   - Calls `client_sock.sendto(wire_bytes, client_addr)`.
   - **Zero network traffic** is sent to Host 3.
5. **Client Response Ingestion:**
   - `client.py:sock.recvfrom(512)` unblocks.
   - Records `t_end = time.perf_counter()`.
   - Calls `protocol.py:MYDNSMessage.unpack()`. Slices trailing 4 bytes, converts via `socket.inet_ntoa()`.
   - Verifies `response.tx_id == 0x1234`.
   - Outputs: `Resolved: 10.0.1.5, TTL: remaining_ttl, RTT: ~0.8ms (CACHE HIT)`.

---

### Scenario B: Cache Miss (3-Host Recursive Forwarding)
1. **Steps 1 & 2** are identical to Scenario A.
2. **Resolver Cache Check:**
   - `resolver.py:DNSCache.get("portal.neduet.local")` finds domain absent or `remaining_ttl <= 0`.
   - Returns `(None, 0)` $\rightarrow$ **Cache Miss**.
3. **Resolver Recursive Forwarding:**
   - Calls `resolver.py:forward_to_auth(query, client_sock, client_addr)`.
   - Creates/reuses UDP forwarding client socket `fwd_sock`.
   - Sets upstream timeout: `fwd_sock.settimeout(0.5)`.
   - Sends query wire bytes directly to Authoritative Server at `192.168.1.12:53053`.
4. **Authoritative Server Lookup:**
   - `authoritative_server.py:main()` listens in a socket loop on `0.0.0.0:53053`.
   - `data, resolver_addr = sock.recvfrom(512)`.
   - Calls `protocol.py:MYDNSMessage.unpack(data)`.
   - Checks `zone_data = zone_dict.get(query.domain)`.
   - Domain found in `zone.json`: `{"ip": "10.0.1.5", "ttl": 120}`.
   - Constructs `MYDNSMessage(tx_id=query.tx_id, msg_type=MSG_RESPONSE, status=STATUS_SUCCESS, ttl=120, domain=query.domain, ip_address="10.0.1.5")`.
   - Calls `response.pack()` (32 bytes).
   - Sends datagram back to `resolver_addr`.
5. **Resolver Cache Population & Relay:**
   - `resolver.py:fwd_sock.recvfrom()` unblocks with Authoritative server's 32-byte response.
   - Calls `protocol.py:MYDNSMessage.unpack(auth_data)`.
   - Calls `resolver.py:DNSCache.put("portal.neduet.local", "10.0.1.5", 120)`:
     - Calculates `expires_at = time.time() + 120`. Stores record under lock.
   - Forwards the 32-byte response datagram directly to `client_addr`.
6. **Client Completion:**
   - Client records $RTT \approx 4.5\text{ms}$ (accounting for 2 physical round trips across Link 1 and Link 2).

---

### Scenario C: Upstream Server Failure & Recovery (Requirement R7)
1. **Host 3 is offline or stopped.**
2. Client sends query for `portal.neduet.local` to Host 2. Client retransmission timer is active with `timeout = 1.5s`.
3. Host 2 checks cache $\rightarrow$ Miss.
4. Host 2 executes `forward_to_auth()`:
   - **Attempt 1:** `fwd_sock.sendto(..., (auth_ip, 53053))`. Waits up to `0.5s`. Times out (`socket.timeout`).
   - **Attempt 2:** Retries `fwd_sock.sendto(...)`. Waits up to `0.5s`. Times out (`socket.timeout`).
   - Total elapsed time at Resolver $= 1.0\text{s}$.
5. Host 2 constructs error response:
   - `MYDNSMessage(tx_id=query.tx_id, msg_type=MSG_RESPONSE, status=STATUS_SERVER_FAILURE, ttl=0, domain=query.domain, ip_address="0.0.0.0")`.
   - Calls `response.pack()` (32 bytes).
   - Sends datagram to `client_addr`.
6. At $T = 1.0\text{s}$ (safely before the client's $1.5\text{s}$ timeout triggers):
   - Client receives response with `status == STATUS_SERVER_FAILURE`.
   - Displays error: `[SERVER FAILURE] Authoritative server unreachable`.
   - Zero uncoordinated client retransmissions occur.

---

### Scenario D: Automated Benchmark Execution Flow (Requirement R6)
1. Member 1 runs:
   ```bash
   python tests/benchmark_runner.py --resolver-ip 192.168.1.11 --domain portal.neduet.local --trials 10
   ```
2. `benchmark_runner.py::run_benchmarks()`:
   - **Phase 1 (Cache Miss Evaluation):**
     - Queries 10 unique pseudo-domains or waits for TTL expiration.
     - For each trial, calls `client.py:query_domain()`.
     - Collects array of RTTs: $[RTT_1, RTT_2, \dots, RTT_{10}]$.
   - **Phase 2 (Cache Hit Evaluation):**
     - Sends 10 immediate back-to-back queries for the cached domain.
     - Collects array of RTTs: $[RTT_1, RTT_2, \dots, RTT_{10}]$.
3. **Statistical Computation:**
   - Computes Mean: $\mu = \frac{1}{N}\sum RTT_i$
   - Computes Sample Standard Deviation (Spread): $\sigma = \sqrt{\frac{1}{N-1}\sum (RTT_i - \mu)^2}$
   - Computes Min and Max.
4. **Artifact Generation:**
   - Prints formatted Markdown comparison table to stdout.
   - Invokes `matplotlib.pyplot` to plot bar charts with error bars ($\pm \sigma$) comparing Miss vs. Hit.
   - Saves plot to `gemini-docs/rtt_benchmark_plot.png`.

---

## 4. Cross-Module Function Call Reference

| Caller Function | Target Function | Defined In | Arguments Passed | Return Value | Purpose |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `client.py:query_domain()` | `MYDNSMessage.__init__()` | `src/protocol.py` | `tx_id, msg_type, query_type, domain` | `MYDNSMessage` instance | Constructs query packet object |
| `client.py:query_domain()` | `MYDNSMessage.pack()` | `src/protocol.py` | `None` (uses `self`) | `bytes` (28B) | Serializes query to raw UDP wire bytes |
| `client.py:query_domain()` | `socket.sendto()` | Python standard `socket` | `(wire_bytes, (ip, port))` | `int` (bytes sent) | Transmits datagram over the network |
| `client.py:query_domain()` | `socket.recvfrom()` | Python standard `socket` | `512` | `(data, addr)` | Blocks waiting for response datagram |
| `client.py:query_domain()` | `MYDNSMessage.unpack()` | `src/protocol.py` | `data: bytes` | `MYDNSMessage` instance | Deserializes wire bytes into message object |
| `resolver.py:handle()` | `MYDNSMessage.unpack()` | `src/protocol.py` | `data: bytes` | `MYDNSMessage` instance | Parses incoming client query |
| `resolver.py:handle()` | `DNSCache.get()` | `src/resolver.py` | `domain: str` | `(ip, remaining_ttl)` or `(None, 0)` | Thread-safe cache lookup & TTL decrement |
| `resolver.py:handle()` | `forward_to_auth()` | `src/resolver.py` | `query, client_sock, client_addr` | `None` | Recursively resolves cache miss from Host 3 |
| `resolver.py:handle()` | `MYDNSMessage.pack()` | `src/protocol.py` | `None` (uses `self`) | `bytes` (32B) | Serializes cache hit response |
| `resolver.py:forward_to_auth()` | `DNSCache.put()` | `src/resolver.py` | `domain, ip, ttl` | `None` | Stores authoritative response in cache |
| `auth_server.py:main()` | `MYDNSMessage.unpack()` | `src/protocol.py` | `data: bytes` | `MYDNSMessage` instance | Parses resolver query |
| `auth_server.py:main()` | `lookup_zone()` | `src/authoritative_server.py`| `domain, zone_data` | `dict` or `None` | Queries zone database for domain record |
| `auth_server.py:main()` | `MYDNSMessage.pack()` | `src/protocol.py` | `None` (uses `self`) | `bytes` (32B) | Serializes authoritative response |
| `benchmark_runner.py` | `client.py:query_domain()` | `src/client.py` | `res_ip, res_port, domain` | `(response, rtt_ms)` | Executes automated benchmark trials |

---

## 5. Packet Transformation Lifecycle (Object to Wire Bytes)

### A. Serialization (`MYDNSMessage.pack()`)
```
[ MYDNSMessage In-Memory Object ]
  ├── tx_id      = 0xA1B2
  ├── msg_type   = MSG_QUERY (0x01)
  ├── query_type = TYPE_A (0x01)
  ├── status     = STATUS_SUCCESS (0x00)
  ├── ttl        = 0
  └── domain     = "portal.neduet.local" (L = 19)

1. Header Packing:
   struct.pack('!HBBBxH', 0xA1B2, 0x01, 0x01, 0x00, 0x0000)
   Output: b'\xA1\xB2\x01\x01\x00\x00\x00\x00' (8 Bytes)

2. Domain Packing:
   struct.pack('!B', 19) + b"portal.neduet.local"
   Output: b'\x13portal.neduet.local' (20 Bytes)

3. IPv4 Trailer Decision:
   Since msg_type == MSG_QUERY, IPv4 trailer is OMITTED.

Total Wire Payload: 8 + 20 = 28 Bytes
```

### B. Deserialization (`MYDNSMessage.unpack()`)
```
[ Incoming Raw Bytes (32 Bytes from Server) ]
b'\xA1\xB2\x02\x01\x00\x00\x00\x78\x13portal.neduet.local\x0A\x00\x01\x05'

1. Minimum Length Guard:
   len(data) >= 10 Bytes (32 >= 10) -> Pass

2. Header Unpack:
   tx_id, msg_type, qtype, status, ttl = struct.unpack('!HBBBxH', data[:8])
   Values: tx_id=0xA1B2, msg_type=2, qtype=1, status=0, ttl=120

3. Domain Extraction:
   domain_len = data[8] = 19
   Bounds check: 1 <= 19 <= 255 -> Pass
   Slice: data[9 : 9 + 19] = b"portal.neduet.local" -> "portal.neduet.local"

4. IPv4 Extraction:
   msg_type == 2 (MSG_RESPONSE) -> Check len(data) >= 9 + 19 + 4 = 32 -> Pass
   Slice: data[28 : 32] = b'\x0A\x00\x01\x05'
   socket.inet_ntoa(b'\x0A\x00\x01\x05') -> "10.0.1.5"

Output: Fully populated MYDNSMessage object ready for application use.
```

---

## Maintenance Invariant

> [!IMPORTANT]
> **Continuous Flow Audit Requirement:** Whenever a new module, function, CLI parameter, or socket interaction is introduced or modified in `src/` or `tests/`, this document **MUST** be updated to maintain an accurate, unbroken map of control flow and function call graphs.

