# SentraDNS

A lightweight, custom binary DNS service implemented from scratch over raw UDP sockets in pure Python — zero external dependencies, no third-party libraries, just sockets and byte packing.

It ships with a full three-tier architecture: an authoritative nameserver backed by a simple JSON zone file, a multi-threaded caching resolver with live TTL countdown, and a client CLI featuring Stop-and-Wait ARQ and microsecond-level latency measurement.

---

## Architecture at a Glance

```
 [ Client ]                 [ Caching Resolver ]              [ Authoritative Server ]
 src/client.py               src/resolver.py                   src/authoritative_server.py
 Ephemeral Port                UDP :53000                        UDP :53053
       │                            │                                  │
       │─── Link 1: QUERY ─────────>│                                  │
       │    (9 + L bytes)           │                                  │
       │                            │─── Link 2: Cache Miss ──────────>│
       │                            │    (forwards raw query bytes)    │
       │                            │                                  │
       │                            │<── Link 2: Zone Response ────────│
       │                            │    (caches if TTL > 0)           │
       │<── Link 1: RESPONSE ───────│                                  │
       │    (13 + L bytes)          │ (Cached queries resolve here!   │
       │                            │  Link 2 is completely bypassed)  │
```

- **Client (`src/client.py`):** Sends queries, manages Stop-and-Wait ARQ retransmission (up to 3 attempts with a 1.5s timeout), verifies 16-bit transaction IDs, and profiles RTT.
- **Caching Resolver (`src/resolver.py`):** Listens on port `53000`, worker pool (`ThreadPoolExecutor(32)`), serves cache hits with dynamic TTL decrementing, and forwards misses upstream to port `53053`.
- **Authoritative Server (`src/authoritative_server.py`):** Listens on port `53053`, loads records from `src/zone.json`, and returns answers or `NXDOMAIN`.

---

## Wire Protocol (`MYDNS/1.0`)

SentraDNS uses a custom binary packet format packed via Python's standard `struct` module. Every packet has an 8-byte fixed header:

```
 0                   1                   2                   3
 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|       Transaction ID          |   Msg Type    |  Query Type   |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|  Status Code  |   (Reserved)  |              TTL              |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|   Domain Len  | Domain Name (L bytes, ASCII)...               |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
| IPv4 Address (4 bytes, Network Order) [RESPONSE only]         |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
```

- **Header Struct Format:** `!HBBBxH` (8 bytes, Network Byte Order / Big-Endian).
- **Query / Error Length:** $9 + L$ bytes (omits IPv4 trailer).
- **Response Length:** $13 + L$ bytes (includes 4-byte IPv4 address).
- **Opcodes:** `0x01` = Query, `0x02` = Response, `0x03` = Error.
- **Status Codes:** `0x00` = Success, `0x01` = NXDOMAIN, `0x02` = Server Failure, `0x03` = Format Error.

---

## Quickstart (Localhost)

To see it working on a single machine, open three terminal windows:

### 1. Start the Authoritative Server
```bash
python src/authoritative_server.py --port 53053
```

### 2. Start the Caching Resolver
```bash
python src/resolver.py --port 53000 --upstream-host 127.0.0.1 --upstream-port 53053
```

### 3. Query with the Client
```bash
# First query -> Cache Miss (4-hop resolution to Auth Server)
python src/client.py portal.neduet.local

# Second query -> Cache Hit (2-hop resolution straight from Resolver memory)
python src/client.py portal.neduet.local
```

You'll immediately see the latency drop on the second query, and the remaining TTL will tick down accurately in real-time.

---

## Running Across Multiple Machines

To run SentraDNS across actual computers or over a local network / VPN:

1. **Host 3 (Authoritative Server):**
   ```bash
   python src/authoritative_server.py --host 0.0.0.0 --port 53053
   ```
2. **Host 2 (Resolver):**
   ```bash
   python src/resolver.py --host 0.0.0.0 --port 53000 --upstream-host <HOST_3_IP> --upstream-port 53053
   ```
3. **Host 1 (Client):**
   ```bash
   python src/client.py --resolver-ip <HOST_2_IP> --resolver-port 53000 portal.neduet.local
   ```

---

## Adding Custom Domains

All authoritative records live in `src/zone.json`. You can add new A-records easily:

```json
{
  "records": {
    "mycoolsite.local": {
      "ip": "192.168.1.50",
      "ttl": 300
    }
  }
}
```

The authoritative server handles case-insensitive lookups automatically while preserving whatever casing the client sent in the response.

---

## Performance Benchmarking

SentraDNS comes with an automated benchmark tool that runs multi-trial comparisons of uncached queries vs. cached queries and computes mean RTT ($\mu$), sample standard deviation ($\sigma$), queries per second (QPS), and throughput:

```bash
python tests/benchmark_runner.py --resolver-ip 127.0.0.1 --resolver-port 53000 --trials 10
```

Over a local network or VPN, cache hits typically deliver a **10x to 15x speedup** compared to uncached queries by cutting out intermediate network hops and resolving directly from RAM.

---

## Running Tests

No external test runners needed — the test suite uses Python's built-in `unittest` module:

```bash
python -m unittest discover -s tests -p "test_*.py" -v
```

All 72 tests (covering binary packing/unpacking, client ARQ edge cases, thread-safe cache eviction, and end-to-end socket handling) run and pass in ~2.5 seconds.
