# Comprehensive Test Suite Architecture & Technical Specifications (`test_details.md`)

**Project:** `MYDNS/1.0` — Mini DNS Service (Option B)  
**Course:** CS-327 Computer Communication Networks (Fall 2026)  
**Institution:** Department of Computer & Information Systems Engineering, NED University of Engineering & Technology  
**Lead Client & Benchmarking Engineer:** Asadullah Zafar (`CS-24082`)  
**Collaborators:** Atta-Ur-Rehman (`CS-24092`), Abdur Rahman (`CS-24098`)  
**Target Directory:** `c:\projects\Sentra_DNS\tests\`  
**Document Purpose:** This document provides a complete technical specification of all test suites and benchmarking scripts inside the `tests/` directory. It explains exactly how every file is constructed, the programming languages and libraries used, the function-by-function architecture, and the underlying algorithms.

---

## 1. Test Architecture Overview

The `tests/` directory contains **4 primary Python files**: three automated unit test suites (`test_protocol.py`, `test_client.py`, `test_benchmark.py`) and one live evaluation CLI benchmarking tool (`benchmark_runner.py`).

Together, they execute **29 automated tests** in approximately **1.0 second** with a 100% pass rate.

```
c:\projects\Sentra_DNS\tests\
├── test_protocol.py       # 17 Tests: Binary Wire Format, Bit-Level Layout & Boundary Guards
├── test_client.py         #  8 Tests: Real Socket Client Engine, Stop-and-Wait ARQ & Error Discard
├── test_benchmark.py      #  4 Tests: Statistical Formulas, Throughput Engine & Plot Rendering
├── benchmark_runner.py    # Live CLI: Multi-Trial Benchmarking, Delay Modeling & Matplotlib Plotter
└── __init__.py            # Module namespace anchor
```

### Architectural Summary Table

| Test Script | Language | Total Tests | Target Tested | Core Strategy |
| :--- | :--- | :---: | :--- | :--- |
| **`test_protocol.py`** | Python 3 | 17 | `src/protocol.py` | In-memory binary slicing, boundary fuzzing, roundtrip byte-fidelity. |
| **`test_client.py`** | Python 3 | 8 | `src/client.py` | **Zero-Mock Real Sockets**: Spins up real OS UDP server thread on `127.0.0.1:0`. |
| **`test_benchmark.py`** | Python 3 | 4 | `tests/benchmark_runner.py` | Ground-truth mathematical assertions, headless Matplotlib rendering. |
| **`benchmark_runner.py`**| Python 3 | Live CLI | Multi-Host / Local Resolver | Phase-based trial burst, Bessel variance, QPS throughput, 3-panel plotting. |

---

## 2. File 1: `tests/test_protocol.py` — Protocol Serialization & Deserialization Engine

### 2.1 Language, Imports & Dependencies
* **Language:** Python 3.10+
* **Framework:** Standard Library `unittest` (`unittest.TestCase`)
* **Core Modules Used:**
  * `struct`: Packing and unpacking binary data into network byte buffers.
  * `os`, `sys`: Dynamic path resolution (`sys.path.insert(0, ...)`).
  * `src.protocol`: Imports `MYDNSMessage` class and all wire constants (`MSG_QUERY`, `MSG_RESPONSE`, `MSG_ERROR`, `TYPE_A`, `STATUS_*`, `HEADER_FORMAT`).

### 2.2 Core Algorithm & Engineering Philosophy
`test_protocol.py` verifies the wire contract specified in the project RFC without opening network sockets. It treats `MYDNSMessage` as a serialization engine (SerDes):
$$\text{Python Object} \xrightarrow[\text{struct.pack}]{\text{pack()}} \text{Raw Wire Bytes} \xrightarrow[\text{struct.unpack}]{\text{unpack()}} \text{Identical Python Object}$$
It asserts three core invariants:
1. **Byte-Level Layout:** Validates that headers strictly follow `!HBBBxH` (Big-Endian Network Byte Order).
2. **Boundary Invariants:** Proves that domain lengths $1 \le L \le 255$ serialize correctly, while $L=0$, $L \ge 256$, and Unicode characters are strictly rejected.
3. **Payload Asymmetry:** Validates that queries and errors omit the 4-byte IPv4 trailer ($9+L$ bytes), while responses strictly include it ($13+L$ bytes).

---

### 2.3 Detailed Method-by-Method Breakdown (17 Tests)

#### 1. `test_query_pack_unpack(self)`
* **Purpose:** Tests standard query serialization.
* **Algorithm:** Constructs a query for `portal.neduet.local` ($L=19$). Calls `pack()`. Asserts wire size is exactly $8 + 1 + 19 = 28\text{ bytes}$. Calls `unpack()` and verifies all unpacked fields (`tx_id`, `msg_type=MSG_QUERY`, `query_type=TYPE_A`, `domain`, `ip_address=None`) match the original.

#### 2. `test_response_success_pack_unpack(self)`
* **Purpose:** Tests standard response serialization.
* **Algorithm:** Constructs a response with `ip_address="10.0.1.5"` and `ttl=120`. Calls `pack()`. Asserts wire size is exactly $8 + 1 + 19 + 4 = 32\text{ bytes}$. Unpacks and verifies the IPv4 trailer is accurately converted from raw binary (`socket.inet_ntoa`) back to `"10.0.1.5"`.

#### 3. `test_response_nxdomain(self)`
* **Purpose:** Tests non-existent domain error response.
* **Algorithm:** Constructs an `MSG_RESPONSE` with `status=STATUS_NXDOMAIN` (`0x01`), `ttl=0`, and `ip_address="0.0.0.0"`. Asserts packing produces 32 bytes and unpacks with status `0x01`.

#### 4. `test_response_server_failure(self)`
* **Purpose:** Tests upstream timeout error response.
* **Algorithm:** Constructs an `MSG_RESPONSE` with `status=STATUS_SERVER_FAILURE` (`0x02`), `ttl=0`, and `ip_address="0.0.0.0"`. Asserts correct byte preservation and status extraction.

#### 5. `test_minimum_domain_length(self)`
* **Purpose:** Lower boundary testing ($L = 1$).
* **Algorithm:** Uses single-character domain `"a"`.
  * Query: Asserts wire size is $8 + 1 + 1 = 10\text{ bytes}$ (the absolute minimum legal `MYDNS/1.0` datagram).
  * Response: Asserts wire size is $8 + 1 + 1 + 4 = 14\text{ bytes}$.

#### 6. `test_maximum_domain_length(self)`
* **Purpose:** Upper boundary testing ($L = 255$).
* **Algorithm:** Generates a 255-character domain (`"a" * 255`).
  * Query: Asserts wire size is $8 + 1 + 255 = 264\text{ bytes}$.
  * Response: Asserts wire size is $8 + 1 + 255 + 4 = 268\text{ bytes}$.
  * Unpacks both and asserts the string is preserved without truncation.

#### 7. `test_zero_length_domain_rejected(self)`
* **Purpose:** Invalid boundary rejection ($L = 0$).
* **Algorithm:**
  * Tests that `MYDNSMessage(..., domain="").pack()` raises `ValueError`.
  * Synthesizes a raw 10-byte binary packet with `domain_len = 0x00` and verifies `unpack()` raises `ValueError("Invalid domain length: 0")`.

#### 8. `test_domain_overflow_rejected(self)`
* **Purpose:** Overflow boundary rejection ($L = 256$).
* **Algorithm:** Constructs `domain = "a" * 256`. Verifies `pack()` raises `ValueError` because a 1-byte length prefix (`!B`) cannot hold integers $>255$.

#### 9. `test_non_ascii_domain_rejected(self)`
* **Purpose:** Rejection of non-ASCII characters.
* **Algorithm:** Tests domains containing Unicode/international characters (`"portal.nëduet.local"`, `"test\u2603.local"`). Asserts `pack()` raises `ValueError` before transmitting invalid bytes.

#### 10. `test_truncated_header(self)`
* **Purpose:** Protection against truncated datagrams.
* **Algorithm:** Injects byte slices of length $0, 1, 2, \dots, 9$ into `unpack()`. Asserts `ValueError("Packet truncated below minimum 10-byte threshold")` is raised for all lengths $<10$.

#### 11. `test_truncated_response_missing_ip(self)`
* **Purpose:** Detection of missing IPv4 trailer on responses.
* **Algorithm:** Packs a 28-byte query, then mutates byte index 2 to `MSG_RESPONSE` (`0x02`). When unpacked, the parser notices the message type is `RESPONSE` but length is $28 < 32$. Asserts `ValueError("missing required 4-byte IPv4 trailer")` is raised.

#### 12. `test_big_endian_wire_layout(self)`
* **Purpose:** Bit-for-bit and byte-for-byte verification of wire layout.
* **Algorithm:** Packs a query with `tx_id=0xA1B2`, `ttl=120` (`0x0078`), and `domain="portal.neduet.local"`. Direct array slicing verifies:
  * `wire[0:2] == b'\xA1\xB2'` (TxID)
  * `wire[2] == 0x01` (`MSG_QUERY`)
  * `wire[3] == 0x01` (`TYPE_A`)
  * `wire[4] == 0x00` (`STATUS_SUCCESS`)
  * `wire[5] == 0x00` (Reserved pad)
  * `wire[6:8] == b'\x00\x78'` (TTL)
  * `wire[8] == 19` (Domain length)
  * `wire[9:28] == b"portal.neduet.local"` (ASCII domain)

#### 13. `test_msg_error_pack_unpack(self)`
* **Purpose:** Verification of `MSG_ERROR` packets.
* **Algorithm:** Packs `tx_id=0x9999`, `msg_type=MSG_ERROR`, `status=STATUS_FORMAT_ERROR`, `domain="bad.request"`. Verifies size is $8 + 1 + 11 = 20\text{ bytes}$ (no IP trailer) and unpacks accurately.

#### 14. `test_constructor_validation(self)`
* **Purpose:** Defensive input validation during object instantiation.
* **Algorithm:** Verifies `ValueError` or `TypeError` is raised when passing negative TxIDs (`-1`), TxID $>65535$, boolean TxIDs, invalid message types (`0x00`, `0x04`), invalid query types, or negative TTLs.

#### 15. `test_invalid_ip_in_response(self)`
* **Purpose:** Verification of IPv4 address string validation.
* **Algorithm:** Feeds illegal IP strings (`"256.0.0.1"`, `"not-an-ip"`, `"1.2.3.4.5"`) to an `MSG_RESPONSE` object. Asserts `pack()` raises `ValueError` via `socket.inet_aton()`.

#### 16. `test_diagnostics_and_representations(self)`
* **Purpose:** Diagnostic formatting validation.
* **Algorithm:** Validates `to_dict()`, `__repr__()`, and Wireshark-compatible 16-byte hex dumps (`hex_dump(formatted=True)`).

#### 17. `test_unpack_type_and_value_guards(self)`
* **Purpose:** Type safety guards on deserialization.
* **Algorithm:** Asserts passing a string instead of bytes to `unpack()` raises `TypeError`. Asserts mutating message type to unrecognized `0x99` raises `ValueError`.

---

## 3. File 2: `tests/test_client.py` — Real UDP Socket Client Engine

### 3.1 Language, Imports & Dependencies
* **Language:** Python 3.10+
* **Framework:** Standard Library `unittest` (`unittest.TestCase`)
* **Core Modules Used:**
  * `socket`: Direct low-level Berkeley socket API (`socket.AF_INET`, `socket.SOCK_DGRAM`).
  * `threading`: Background thread concurrency (`threading.Thread`, `threading.Event`).
  * `time`: Microsecond timer validation (`time.perf_counter()`, `time.sleep()`).
  * `src.client`: Imports `query_domain()` function.
  * `src.protocol`: Imports `MYDNSMessage` and wire constants.

### 3.2 Core Algorithm: Zero-Mock Real UDP Server Thread
Rather than using mocked objects or monkey-patching, `test_client.py` uses a **100% real network testing harness**:

```python
class RealUDPServerThread(threading.Thread):
    def __init__(self, handler=None):
        super().__init__(daemon=True)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(('127.0.0.1', 0))  # Kernel allocates ephemeral port
        self.host, self.port = self.sock.getsockname()
        self.handler = handler
        self.running = True
        self.ready_event = threading.Event()
```

#### How this harness works:
1. **Dynamic Ephemeral Port Allocation:** Passing port `0` instructs the operating system kernel to allocate any currently free port (e.g. `58312`). This completely eliminates port collisions or "Address already in use" errors during test runs.
2. **Deterministic Thread Synchronization:** Uses `threading.Event()` (`ready_event.set()`) so the test client never transmits before the server socket is bound and listening.
3. **Pluggable Callback Handlers:** Each test passes a custom `handler(data, addr, sock)` function into the server thread. This allows each individual test to simulate packet drops, packet delays, corrupt bytes, or mismatched transaction IDs.

---

### 3.3 Detailed Method-by-Method Breakdown (8 Real-Socket Tests)

#### 1. `test_real_socket_query_success(self)`
* **Purpose:** Verifies standard end-to-end DNS lookup over a real UDP socket.
* **Algorithm:** Server thread runs an echo handler that unpacks the query, creates a matching response (`status=STATUS_SUCCESS`, `ip="10.0.1.5"`, `ttl=120`), and sends it back. Client executes `query_domain()`. Asserts `response.status == SUCCESS`, `ip_address == "10.0.1.5"`, and measured RTT $> 0\text{ ms}$ and $< 1000\text{ ms}$.

#### 2. `test_real_socket_stop_and_wait_retry(self)`
* **Purpose:** Proves Stop-and-Wait ARQ retransmission under physical packet loss.
* **Algorithm:** 
  * Handler records all received attempts in a list: `attempts_seen.append(data)`.
  * **On Attempt 1:** The handler does nothing (`return`), simulating a lost UDP packet in the network.
  * Client's stop-and-wait timeout ($0.2\text{s}$) fires and retransmits Attempt 2.
  * **On Attempt 2:** The handler replies with a valid response.
  * **Assertion:** `self.assertEqual(len(attempts_seen), 2)` — proves the client retransmitted over the wire and recovered successfully.

#### 3. `test_real_socket_timeout_exhaustion(self)`
* **Purpose:** Verifies client behavior when the server is dead or permanently offline.
* **Algorithm:** Server handler silently drops all packets. Client configured with `timeout=0.1s` and `max_retries=3`. Asserts `TimeoutError` is raised, error message states `"failed after 3 attempts"`, and exactly 3 datagrams were sent over the socket.

#### 4. `test_real_socket_tx_id_filtering(self)`
* **Purpose:** Verifies asynchronous Transaction ID correlation.
* **Algorithm:** 
  * When the query arrives, the server deliberately transmits a **stale response first** with a mismatched `tx_id` (`(query.tx_id + 1) % 0xFFFF`), then sends the correct matching response.
  * The client's receive loop inspects the first packet, sees `response.tx_id != tx_id`, discards it, and continues listening.
  * The client accepts the second matching packet.
  * **Assertion:** Verifies client receives the correct IP address (`"10.0.1.5"`), proving stale datagrams are safely ignored.

#### 5. `test_real_socket_nxdomain(self)`
* **Purpose:** Verifies reception of `STATUS_NXDOMAIN` over native UDP.
* **Algorithm:** Server replies with `STATUS_NXDOMAIN` (`0x01`). Asserts client parses `response.status == STATUS_NXDOMAIN`, `ip_address == "0.0.0.0"`, and `ttl == 0`.

#### 6. `test_real_socket_server_failure(self)`
* **Purpose:** Verifies reception of `STATUS_SERVER_FAILURE` over native UDP.
* **Algorithm:** Server replies with `STATUS_SERVER_FAILURE` (`0x02`). Asserts client parses the failure status cleanly without raising exceptions.

#### 7. `test_real_socket_corrupt_datagram_ignored(self)`
* **Purpose:** Tests defensive immunity against Wi-Fi background noise and corrupt packets.
* **Algorithm:** 
  * Server sends a raw 16-byte garbage datagram (`b"\x00\x01\xFFGARBAGE_PAYLOAD\x99"`), followed immediately by the legitimate response.
  * In `src/client.py`, the `try...except (ValueError, TypeError, struct.error): continue` block catches the corrupted packet and silently continues listening.
  * **Assertion:** Client cleanly receives the valid response without crashing.

#### 8. `test_real_socket_format_error_fast_fail(self)`
* **Purpose:** Verifies fail-fast behavior on `MSG_ERROR` / `STATUS_FORMAT_ERROR`.
* **Algorithm:** 
  * Server handler replies to Attempt 1 with an `MSG_ERROR` datagram carrying `STATUS_FORMAT_ERROR` (`0x03`).
  * In `src/client.py`, the client recognizes matching `tx_id` on an error packet, halts the Stop-and-Wait timer, and returns immediately without retrying.
  * **Assertion:** `self.assertEqual(len(attempts_seen), 1)` — proves zero unnecessary retries were sent.

---

## 4. File 3: `tests/test_benchmark.py` — Mathematical Rigor & Statistical Engine

### 4.1 Language, Imports & Dependencies
* **Language:** Python 3.10+
* **Framework:** Standard Library `unittest` (`unittest.TestCase`)
* **Core Modules Used:**
  * `math`: Square root and statistical summation.
  * `os`, `sys`: Image file size inspection.
  * `tests.test_client`: Imports `RealUDPServerThread`.
  * `tests.benchmark_runner`: Imports `calculate_statistics`, `generate_benchmark_plot`, and `run_benchmark_trials`.

### 4.2 Core Algorithm: Statistical Verification & Headless Graphics Pipeline
This suite guarantees that performance benchmarking numbers reported to course instructors are mathematically sound.
It tests:
1. **Unbiased Sample Variance (Bessel's Correction):**
   $$\mu = \frac{1}{n} \sum_{i=1}^n x_i \qquad \sigma = \sqrt{\frac{1}{n-1} \sum_{i=1}^n (x_i - \mu)^2}$$
2. **Application Throughput Modeling (Requirement R6):**
   $$\text{QPS} = \frac{n}{\sum t_i} = \frac{1000}{\mu_{\text{ms}}} \qquad \text{Throughput}_{\text{KB/s}} = \frac{\text{QPS} \times \text{Bytes per Query}}{1024}$$
3. **Headless Canvas Rendering:** Uses Matplotlib's `'Agg'` backend to generate figures purely in memory without requiring a GUI display.

---

### 4.3 Detailed Method-by-Method Breakdown (4 Tests)

#### 1. `test_statistics_calculation(self)`
* **Purpose:** Validates statistical accuracy against hand-computed ground truth.
* **Input Dataset:** $N = 8$ sample RTTs: `[2.0, 4.0, 4.0, 4.0, 5.0, 5.0, 7.0, 9.0]`.
  * Sum $= 40.0$, Mean $\mu = 5.0\text{ ms}$.
  * Sum of squared deviations: $(2-5)^2 + 3(4-5)^2 + 2(5-5)^2 + (7-5)^2 + (9-5)^2 = 9 + 3 + 0 + 4 + 16 = 32$.
  * Sample Variance $s^2 = \frac{32}{8 - 1} = \frac{32}{7} \approx 4.571428$.
  * Standard Deviation $\sigma = \sqrt{4.571428} \approx 2.1380899\text{ ms}$.
  * Total duration $= 40\text{ ms} = 0.040\text{ s}$.
  * Throughput $\text{QPS} = \frac{8}{0.040} = 200.0\text{ queries/sec}$.
  * Payload Throughput $= \frac{200 \times 60\text{ bytes}}{1024} = 11.71875\text{ KB/s}$.
* **Assertions:** Asserts calculated `mean`, `std_dev`, `min`, `max`, `qps`, and `throughput_kbps` match ground truth to 4 decimal places.

#### 2. `test_statistics_edge_cases(self)`
* **Purpose:** Verifies edge-case safety.
* **Algorithm:** Feeds an empty list `[]` ($N=0$) and single-element list `[5.5]` ($N=1$). Asserts that `mean`, `std_dev`, and `qps` return `0.0` rather than crashing with `ZeroDivisionError`.

#### 3. `test_plot_generation(self)`
* **Purpose:** Verifies automatic plot generation and export.
* **Algorithm:** Calls `generate_benchmark_plot()` with synthetic miss and hit data. Checks that the target file is created and file size $> 50,000\text{ bytes}$ (confirming a high-resolution 300 DPI image). Cleans up test artifact on completion.

#### 4. `test_real_udp_benchmark_execution(self)`
* **Purpose:** Verifies multi-trial benchmark execution over native loopback sockets.
* **Algorithm:** Starts `RealUDPServerThread`. Calls `run_benchmark_trials(..., trials=3)`. Verifies that exactly 3 miss RTTs and 3 hit RTTs are collected and all values are positive floating-point numbers.

---

## 5. File 4: `tests/benchmark_runner.py` — Multi-Trial Benchmarking & Evaluation CLI

### 5.1 Language, Imports & Dependencies
* **Language:** Python 3.10+
* **Core Modules Used:**
  * `argparse`: Command-line interface parsing (`--resolver-ip`, `--domain`, `--trials`, `--output-plot`).
  * `math`: Square root calculations.
  * `matplotlib.pyplot`: Publication-grade graphing with `'Agg'` headless backend.
  * `src.client`: `query_domain()` query engine.
  * `src.protocol`: Status codes and message constants.

---

### 5.2 Core Functions & Execution Flow

```
[ CLI Entrypoint: main() ]
          │
          ├── 1. run_benchmark_trials(resolver_ip, domain, trials=10)
          │        ├── Phase 1: Queries bench01..bench10 (Cache Miss, 4 Hops)
          │        ├── Phase 2: Primes Resolver RAM with portal.neduet.local
          │        └── Phase 3: Queries portal.neduet.local x 10 (Cache Hit, 2 Hops)
          │
          ├── 2. calculate_statistics(miss_rtts) & calculate_statistics(hit_rtts)
          │        └── Computes Mean, Std Dev, Min, Max, QPS, and KB/s Throughput
          │
          ├── 3. print_comparison_table() -> Outputs formatted Markdown table to terminal
          │
          └── 4. generate_benchmark_plot() -> Renders 3-panel figure to docs/rtt_benchmark_plot.png
```

#### Function 1: `calculate_statistics(rtts, domain, is_miss)`
Computes statistical spread and application throughput. Dynamically calculates wire payload sizes using $9+L$ for queries and $13+L$ for responses.

#### Function 2: `run_benchmark_trials(resolver_ip, resolver_port, domain, trials, timeout)`
Executes the empirical benchmark across 3 sequential phases:
* **Phase 1 (Cache Miss):** Iterates $i$ from 1 to $N$, querying `bench{i:02d}.neduet.local`. Because each domain is unique and uncached, every query traverses all 4 hops (Client $\rightarrow$ Resolver $\rightarrow$ Auth $\rightarrow$ Resolver $\rightarrow$ Client).
* **Phase 2 (Cache Priming):** Issues a single query for the base domain to ensure it is stored in the resolver's RAM cache.
* **Phase 3 (Cache Hit):** Fires $N$ consecutive queries for the base domain. Because the record is cached, the resolver replies immediately from memory, bypassing Link 2.

#### Function 3: `print_comparison_table(miss_stats, hit_stats, trials)`
Outputs a clean Markdown table comparing Cache Miss vs. Cache Hit across all 11 required metrics:
```text
================================================================================
STATISTICAL BENCHMARK COMPARISON TABLE (CS-327 Rubric Criterion 3 & R6)
================================================================================
| Metric                       |    Cache Miss (4 Hops) |     Cache Hit (2 Hops) |
|:-----------------------------|-----------------------:|-----------------------:|
| Sample Trials (N)            |                     10 |                     10 |
| Mean RTT (mu)                |                4.92 ms |                0.88 ms |
| Std Deviation (sigma)        |             +/-0.28 ms |             +/-0.07 ms |
| Minimum Latency              |                4.61 ms |                0.81 ms |
| Maximum Latency              |                5.39 ms |                1.04 ms |
| Throughput (Queries/sec)     |              203.3 QPS |             1136.4 QPS |
| Throughput (Payload KB/s)    |             12.31 KB/s |             66.58 KB/s |
| Client Payload / Query       |               62 bytes |               60 bytes |
| Total Wire Traffic / Query   |              124 bytes |               60 bytes |
| Upstream Link 2 Traversal    | Host 2 <-> Host 3 (Yes)|   Bypassed (Zero Load) |
--------------------------------------------------------------------------------
Empirical Latency Speedup:     5.59x faster on Cache Hit
Throughput Improvement:        5.59x higher queries/sec on Cache Hit
Network Traffic Savings:       50.0% byte & energy reduction (CLO-3 Sustainability)
================================================================================
```

#### Function 4: `generate_benchmark_plot(miss_rtts, hit_rtts, miss_stats, hit_stats, output_path)`
Renders a 3-panel figure exported at 300 DPI:
1. **Subplot 1 (Latency Comparison):** Bar chart comparing Mean Miss vs. Mean Hit latency with error bars ($\mu \pm \sigma$) and speedup badge.
2. **Subplot 2 (Throughput Comparison):** Bar chart comparing sustained Queries Per Second (QPS) and payload throughput (KB/s).
3. **Subplot 3 (Trial Progression & Jitter):** Line plot tracking individual trial RTTs, illustrating the **Layer 2 ARP Cold-Start Anomaly** on Trial 1 and network jitter across trials.

---

## 6. How to Execute the Test Suites

### Run All 29 Automated Tests
From the project root:
```powershell
python -m unittest discover tests
```
*Expected terminal output:*
```text
Ran 29 tests in 1.038s

OK
```

### Run Individual Test Suites
```powershell
# Run protocol wire format tests (17 tests)
python -m unittest tests.test_protocol

# Run real socket client engine tests (8 tests)
python -m unittest tests.test_client

# Run statistical and plotting tests (4 tests)
python -m unittest tests.test_benchmark
```

### Run Live Benchmarking CLI Tool
```powershell
# Against local loopback resolver:
python tests/benchmark_runner.py --resolver-ip 127.0.0.1 --domain portal.neduet.local --trials 10

# Against remote teammate's resolver during evaluation:
python tests/benchmark_runner.py --resolver-ip 192.168.43.20 --domain portal.neduet.local --trials 10
```

