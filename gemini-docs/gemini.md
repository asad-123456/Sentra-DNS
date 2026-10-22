# Context Memory: CS-327 CCN Complex Engineering Problem (CEP)
**Project Title:** Design, Implementation, and Evaluation of a Multi-Host Networked Application  
**Selected Track:** Option B — Mini DNS Service (`MYDNS/1.0`)  
**Working Directory:** `c:\projects\Sentra_DNS` (aliased to `c:\projects\mydns`)  
**Documentation Directory:** `c:\projects\Sentra_DNS\gemini-docs`  
**Architecture Decision Log:** `c:\projects\Sentra_DNS\Decisions.md`  
**Control & Data Flow Audit:** `c:\projects\Sentra_DNS\flow.md`  
**Protocol Implementation Plan:** `c:\projects\Sentra_DNS\gemini-docs\protocol_implementation_plan.md`

---

## 1. Team & Role Distribution
* **Group Size:** 3 Members (Max allowed: 4)
* **Member 1:** Asadullah Zafar (`CS-24082`) — *Lead: Client Engine, Microsecond RTT Benchmarking Suite & Delay Modeling*
* **Member 2:** Atta-Ur-Rehman (`CS-24092`) — *Lead: Resolver Caching Logic, Thread-Safe TTL Engine & Failure Recovery*
* **Member 3:** Abdur Rahman (`CS-24098`) — *Lead: Authoritative Zone Server, Packet Encoding Specification & Wireshark Encapsulation Analysis*

---

## 2. Core Educational Framework
* **CLO-1 (PLO-1):** Discuss basic computer network topologies and reference models. Addressed by protocol design and layering analysis (encapsulation).
* **CLO-2 (PLO-2):** Explore operation and design issues of OSI layers. Addressed by socket implementation, 3-host deployment, delay measurements ($T_{nodal}$), and trade-off defense.
* **CLO-3 (PLO-7):** Explore tools for environment friendly and/or sustainable communication. Addressed by quantifying byte/energy savings through caching and compact serialization.
* **Complex Problem Attributes Covered:**
  * **CPA-1 (Depth of Analysis):** Original protocol invention without supplied templates; empirical validation vs. theoretical models.
  * **CPA-2 (Level of Interaction):** Resolving $\ge 3$ conflicting technical tensions (latency vs reliability, freshness vs traffic reduction, compactness vs readability).
  * **CPA-3 (Familiarity):** Moving from consumer to protocol architect; distributed implementation across independent IP hosts directly on raw sockets.

---

## 3. Mandatory Engineering Requirements (R1 – R7)
1. **R1: Custom Application Layer Protocol:**
   - Must be original (`MYDNS/1.0`).
   - Comprehensive formal specification: message types, exact bit-level binary header fields, state transitions, legal message ordering, error/status codes.
   - Specification must be strict enough for a third-party group to implement inter-operably without reading source code.
2. **R2: Direct Socket Implementation:**
   - Native sockets (`socket.AF_INET`, `socket.SOCK_DGRAM`) in Python.
   - Zero high-level application protocol libraries (no `dnspython`, `urllib`, etc.).
   - Standard low-level encoding (`struct.pack` / `struct.unpack`).
3. **R3: 3-Host Independent Deployment:**
   - At least 3 distinct network endpoints with separate IPs (e.g., Department LAN, Wi-Fi hotspot, or Bridged VMs).
   - Zero reliance on `127.0.0.1` loopback for final submission/demonstration.
   - Required artifacts: `ipconfig` / `ip addr` outputs for all 3 nodes + network topology diagram.
4. **R4: Transport Layer Justification:**
   - UDP selection justified against the 4 Lecture 04 service requirements: Reliable Data Transfer, Throughput, Timing, Security.
   - Must articulate the exact consequences and performance penalties of choosing TCP (connection handshake latency, byte overhead, state memory).
5. **R5: Traffic Capture & Encapsulation Analysis:**
   - Wireshark `.pcap` capture of live traffic between nodes.
   - Annotated inspection: Link-layer Ethernet Frame -> Network-layer IPv4 Packet -> Transport-layer UDP Datagram -> Application-layer `MYDNS/1.0` payload.
6. **R6: Quantitative Performance Benchmarking:**
   - Metric 1: Round-Trip Time (RTT in ms/$\mu$s).
   - Metric 2: Application-level throughput (queries/sec, KB/s).
   - Metric 3: Response/transfer time of representative operations.
   - Comparison: Cache Hit vs. Cache Miss over $\ge 5$ runs with mean, spread (standard deviation), min, max.
   - Analytical mapping to the Lecture 02 Nodal Delay Model:
     $$T_{nodal} = d_{proc} + d_{queue} + d_{trans} + d_{prop}$$
7. **R7: Behavior Under Failure:**
   - Deterministic handling of abnormal conditions (e.g., authoritative server unreachable/offline, dropped UDP datagrams, malformed packets).
   - Client stop-and-wait retransmission with exponential backoff / timeout limit.
   - Resolver failover / timeout signaling with `SERVER_FAILURE` error code.
   - Empirical proof required: logs and Wireshark captures demonstrating graceful recovery.

---

## 4. System Architecture (Option B: Mini DNS Service)
```
+--------------------+                 +--------------------------+                 +-----------------------------+
|   HOST 1: CLIENT   |   Query (UDP)   |     HOST 2: RESOLVER     |   Query (UDP)   | HOST 3: AUTHORITATIVE SERVER|
|   192.168.1.10     | --------------> |      192.168.1.11        | --------------> |       192.168.1.12          |
|                    |                 |                          |                 |                             |
|  - RTT Profiler    |                 | - In-Memory Cache + TTL  |                 | - Master Zone File          |
|  - Retransmit timer| <-------------- | - HIT: Returns local IP  | <-------------- |   (hosts / domain mappings) |
|  - CLI Interface   |  Response (UDP) | - MISS: Forwards to Auth |  Response (UDP) | - Authoritative TTL config  |
+--------------------+                 +--------------------------+                 +-----------------------------+
```

---

## 5. Protocol Specification Outline (`MYDNS/1.0`)
Communication uses a fixed 64-bit (8-byte) binary header:
```
 0                   1                   2                   3
 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|        Transaction ID         |  Msg Type (8) |  Query Type(8)|
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|   Status (8)  |   Reserved(8) |              TTL (16)         |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
| Domain Length |               Domain Name (Variable)          |
+-+-+-+-+-+-+-+-+                                               +
|               | Resolved IPv4 Address (4 Bytes, if Response)  |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
```
- **Header Format (`struct`):** `!HBBBxH` (Big-Endian Network Byte Order)
  - `Transaction ID` (16 bits): Request/Response correlation.
  - `Msg Type` (8 bits): `0x01` (Query), `0x02` (Response), `0x03` (Error).
  - `Query Type` (8 bits): `0x01` (TYPE_A).
  - `Status Code` (8 bits): `0x00` (SUCCESS), `0x01` (NXDOMAIN), `0x02` (SERVER_FAILURE), `0x03` (FORMAT_ERROR).
  - `Reserved` (8 bits): Padding (`0x00`).
  - `TTL` (16 bits): Remaining cache lifetime in seconds.
- **Payload:**
  - `Domain Length` (1 byte, unsigned char `!B`).
  - `Domain Name` (Variable ASCII string).
  - `Resolved IPv4 Address` (4 bytes raw binary, `socket.inet_aton`, response only).

---

## 6. Design Tensions & Positions
1. **Caching Freshness vs. Traffic Reduction:**
   - Position: Balanced TTL (e.g., 60s - 300s) with active expiration and negative caching prevention.
   - Justification: Maximizes hit ratio while minimizing risk of serving stale IP mappings.
2. **Reliability vs. Latency:**
   - Position: Native UDP + Application-layer stop-and-wait timeout (1.5s max 3 retries).
   - Justification: Avoids TCP 3-way handshake (1 RTT penalty), eliminates connection state overhead, delivers sub-millisecond local responses.
3. **Compactness vs. Readability:**
   - Position: Custom binary packed header (`struct`) over JSON/ASCII.
   - Justification: 8-byte header vs. ~120-byte JSON reduces MTU fragmentation risk, serialization CPU time, and total network byte overhead.

---

## 7. Sustainability & Quantitative Efficiency Model
- Cache Hit eliminates the 2-hop traversal to the Authoritative Server:
  - Cache Miss: Client -> Resolver (Query) + Resolver -> Auth (Query) + Auth -> Resolver (Resp) + Resolver -> Client (Resp) $\approx 4\text{ packets} \approx 200\text{ bytes}$.
  - Cache Hit: Client -> Resolver (Query) + Resolver -> Client (Resp) $\approx 2\text{ packets} \approx 100\text{ bytes}$.
- Byte reduction: $\approx 50\%$ traffic savings on cache hit.
- Scaled Projection: Modeling query load for 10,000 to 1,000,000 campus users demonstrates significant reduction in NIC packet processing energy, router queue contention, and switch power draw.

---

## 8. Grading Rubric Target (50 / 50 Marks)
* **Criterion 1 (10 Marks):** Complete formal protocol specification + rigorous packet encapsulation analysis connecting every header field to OSI layer functions.
* **Criterion 2 (10 Marks):** Multi-host deployment on 3 separate physical/VM endpoints, zero loopback, clean concurrent query handling.
* **Criterion 3 (10 Marks):** $\ge 5$ benchmark runs per condition, mean & spread reporting, delay model ($d_{proc}, d_{queue}, d_{trans}, d_{prop}$), critical trade-off analysis, deliberate failure demonstrations with Wireshark logs.
* **Criterion 4 (10 Marks):** Rigorous byte-savings math based on empirical data, projected to a realistic user population with honest assumptions.
* **Criterion 5 (10 Marks):** High-quality $\le 10$-page report (Times New Roman 12/14, rubric title page), fully signed individual contributions table, fluent demonstration.

---

## 9. Mandatory Agent Invariants: Self-Auditing & Living Documentation

Whenever the AI agent makes modifications to the codebase, scripts, protocol, or architecture, the agent **MUST ALWAYS proactively update the following two living audit files** before completing the turn:

1. **`c:\projects\Sentra_DNS\Decisions.md` (Architecture Decision Log):**
   * **When to update:** Any architectural shift, design tradeoff, packet layout update, timing/timeout adjustment, concurrency change, or new dependency.
   * **What to record:** Entry with ADR ID, Date, Status, Context, Alternatives Considered, Decision, and Rationale/Consequences.

2. **`c:\projects\Sentra_DNS\flow.md` (Program Control & Data Flow Audit):**
   * **When to update:** Any addition, modification, or refactoring of files, functions, call graphs, command-line arguments, network sequences, or packet serialization lifecycles.
   * **What to record:** Updated directory map, ASCII sequence diagrams, and cross-module function call reference entries detailing caller, callee, parameters, and return types.

> [!IMPORTANT]
> **Documentation Synchronization Invariant:** All documentation across `docs/`, `gemini-docs/`, `Decisions.md`, and `flow.md` must remain 100% mutually consistent and synchronized with the latest codebase state at all times.


