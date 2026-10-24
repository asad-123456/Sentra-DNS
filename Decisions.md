# Architecture & Codebase Decisions Audit Log (`Decisions.md`)

**Project:** `MYDNS/1.0` — Mini DNS Service (Option B)  
**Course:** CS-327 Computer Communication Networks (Fall 2026)  
**Repository:** `c:\projects\Sentra_DNS`  
**Purpose:** This document serves as the formal Architectural Decision Record (ADR) and audit log for all major technical, architectural, and protocol design choices made throughout the codebase, complete with context, alternatives considered, rationale, and impact.

---

## Decision Index

* [ADR-001: Track & Application Selection (Option B: Mini DNS)](#adr-001-track--application-selection-option-b-mini-dns)
* [ADR-002: Transport Layer Choice (Native UDP Sockets)](#adr-002-transport-layer-choice-native-udp-sockets)
* [ADR-003: Fixed 64-Bit Binary Header Packed with Struct](#adr-003-fixed-64-bit-binary-header-packed-with-struct)
* [ADR-004: Conditional IPv4 Payload Trailer (Response Only)](#adr-004-conditional-ipv4-payload-trailer-response-only)
* [ADR-005: Upstream Resolver Timeout Tuning vs. Client Retransmission Timer](#adr-005-upstream-resolver-timeout-tuning-vs-client-retransmission-timer)
* [ADR-006: Thread-Safe In-Memory Cache with Dynamic TTL Decrementing](#adr-006-thread-safe-in-memory-cache-with-dynamic-ttl-decrementing)
* [ADR-007: Multi-Threaded Resolver Concurrency Model](#adr-007-multi-threaded-resolver-concurrency-model)
* [ADR-008: Error Handling Separation (`MSG_RESPONSE` Status vs. `MSG_ERROR`)](#adr-008-error-handling-separation-msg_response-status-vs-msg_error)
* [ADR-009: Decoupled Protocol-First Architecture (`src/protocol.py`)](#adr-009-decoupled-protocol-first-architecture-srcprotocolpy)
* [ADR-010: Standardized Fully Qualified Domain Names (`portal.neduet.local`)](#adr-010-standardized-fully-qualified-domain-names-portalneduetlocal)
* [ADR-011: Protocol Implementation Strategy & Unit Test Verification Protocol](#adr-011-protocol-implementation-strategy--unit-test-verification-protocol)
* [ADR-012: Implementation & Verification of Protocol Engine (`src/protocol.py`)](#adr-012-implementation--verification-of-protocol-engine-srcprotocolpy)

---

### ADR-001: Track & Application Selection (Option B: Mini DNS)
* **Date:** 2026-10-14
* **Status:** Accepted
* **Context:** The CS-327 Complex Engineering Problem (CEP) required selecting one application among five tracks (A: Mail System, B: Mini DNS, C: Web Caching Proxy, D: Multi-client Chat, E: File Distribution).
* **Alternatives Considered:**
  1. *Option C (Web proxy):* Involves complex HTTP parsing or non-persistent/persistent state tracking.
  2. *Option D (Chat):* Difficult to measure quantifiable delay models ($T_{nodal}$) or clear sustainability byte savings.
* **Decision:** Selected Option B: Mini DNS Service (`MYDNS/1.0`).
* **Rationale:** Option B maps cleanly across exactly three distributed hosts (Client, Resolver, Authoritative Server). It offers a clear, measurable performance contrast (Cache Hit vs. Cache Miss) that directly demonstrates the Lecture 02 Nodal Delay Model ($T_{nodal} = d_{proc} + d_{queue} + d_{trans} + d_{prop}$) and allows exact quantification of traffic/energy reductions (50% byte savings) for Section 7 sustainability requirements.

---

### ADR-002: Transport Layer Choice (Native UDP Sockets)
* **Date:** 2026-10-14
* **Status:** Accepted
* **Context:** Mandatory Requirement R4 requires selecting and defending either TCP or UDP against the four application service requirements: Reliable Data Transfer, Throughput, Timing, and Security.
* **Alternatives Considered:**
  1. *TCP (`SOCK_STREAM`):* Provides guaranteed ordered delivery, but imposes a mandatory 3-way handshake (1 RTT delay penalty), 20-byte segment headers, connection state memory on servers, and connection teardown overhead.
* **Decision:** Use native UDP sockets (`socket.SOCK_DGRAM`) with client-side application-layer stop-and-wait retransmissions (`socket.settimeout(1.5)`).
* **Rationale:** DNS lookups are short, request-response atomic exchanges requiring 0-RTT connectionless setup. Query loss is handled gracefully at the application layer using a 1.5s timeout and 3 max retries. Using UDP eliminates TCP connection setup latency and keeps wire overhead minimal.

---

### ADR-003: Fixed 64-Bit Binary Header Packed with Struct
* **Date:** 2026-10-14
* **Status:** Accepted
* **Context:** Requirement R1 requires designing an original custom protocol header that is compact, deterministic, and inspectable in Wireshark.
* **Alternatives Considered:**
  1. *Text / JSON / ASCII:* Highly human-readable, but carries ~120 bytes of overhead per message, variable parsing times, and risk of fragmentation.
  2. *Variable-length bitfields:* Complex bitwise shifts and endianness bugs.
* **Decision:** Implement a fixed 8-byte (64-bit) binary header packed using Python's native `struct` module with format string **`!HBBBxH`** in Network Byte Order (Big-Endian).
* **Rationale:**
  * Byte 0–1: `Transaction ID` (16-bit unsigned short `!H`)
  * Byte 2: `Message Type` (8-bit unsigned char `!B`)
  * Byte 3: `Query Type` (8-bit unsigned char `!B`)
  * Byte 4: `Status Code` (8-bit unsigned char `!B`)
  * Byte 5: `Reserved/Pad` (1-byte pad `x`, auto-written as `0x00`)
  * Byte 6–7: `TTL` (16-bit unsigned short `!H`)
  Total size is strictly 8 bytes. `struct.pack` takes exactly 5 arguments because `x` inserts the pad byte automatically.

---

### ADR-004: Conditional IPv4 Payload Trailer (Response Only)
* **Date:** 2026-10-19
* **Status:** Accepted (Updated & Re-aligned with Submitted Proposal)
* **Context:** The initial draft of `protocol_specification.md` included a fixed 4-byte IPv4 trailer defaulting to `0.0.0.0` in all packets ($13+L$ bytes). However, `project-proposal-v4.md` had already been submitted stating IPv4 is `"4 Bytes, if Response"`.
* **Alternatives Considered:**
  1. *Keep 4-byte trailer in Queries:* Simplifies length checks, but wastes 4 bytes on every query datagram and contradicts the submitted proposal.
  2. *Omit IPv4 trailer in Queries:* Query packets become $9 + L$ bytes; Response packets become $13 + L$ bytes.
* **Decision:** Aligned the protocol specification with the submitted proposal. The 4-byte raw binary IPv4 trailer (`socket.inet_aton`) is present **only in `MSG_RESPONSE` packets**.
* **Rationale:**
  * Conforms faithfully to standard DNS (RFC 1035), where queries do not carry answer records.
  * Preserves 100% fidelity with the submitted proposal document.
  * Saves 4 bytes on the wire per query, perfectly matching the proposal's 50-byte saving arithmetic (21B query + 25B response $\approx 50\text{B}$).

---

### ADR-005: Upstream Resolver Timeout Tuning vs. Client Retransmission Timer
* **Date:** 2026-10-19
* **Status:** Accepted
* **Context:** The client stop-and-wait retransmission timer is set to $1.5\text{s}$. If the resolver took $1.5\text{s} \times 2 = 3.0\text{s}$ to detect that the Authoritative Server was offline, the client's timer would expire first, triggering a duplicate client retransmission while the resolver was still waiting.
* **Alternatives Considered:**
  1. *Increase Client Timeout to 4.0s:* Delays client responsiveness to network failures.
  2. *Single Upstream Attempt of 1.4s:* Leaves no room for packet loss recovery between Resolver and Auth server.
* **Decision:** Set the Resolver's upstream forwarding timeout to **$0.5\text{s}$ per attempt**, allowing 2 attempts ($1.0\text{s}$ total).
* **Rationale:** $1.0\text{s} < 1.5\text{s}$. When Host 3 is offline, Host 2 detects failure and sends a `SERVER_FAILURE` response to Host 1 at $T = 1.0\text{s}$, arriving safely before Host 1's $1.5\text{s}$ client retransmission timer fires.

---

### ADR-006: Thread-Safe In-Memory Cache with Dynamic TTL Decrementing
* **Date:** 2026-10-14
* **Status:** Accepted
* **Context:** Requirement Option B requires caching answers subject to a Time-To-Live (TTL).
* **Alternatives Considered:**
  1. *Return static TTL received from Auth Server:* Violates RFC DNS caching behavior; clients would be told the record is fresh for the full duration even when fetched near expiry.
* **Decision:** Store records with `expires_at = time.time() + ttl`. On cache hit, compute `remaining_ttl = int(expires_at - time.time())`. If `remaining_ttl <= 0`, evict entry and trigger a cache miss. Protect the cache dictionary with `threading.Lock()`.
* **Rationale:** Guarantees strict DNS caching semantics, prevents cache corruption under concurrency, and ensures real-time TTL decrementing visible during live evaluation.

---

### ADR-007: Multi-Threaded Resolver Concurrency Model
* **Date:** 2026-10-14
* **Status:** Accepted
* **Context:** Rubric Criterion 2 (Level 4: 8–10 Marks) requires that *"the system handles concurrent clients or multiple servers cleanly."*
* **Alternatives Considered:**
  1. *Single-threaded `while True: sock.recvfrom()` loop:* A slow authoritative lookup or timeout would block all other pending client queries in the OS receive buffer.
* **Decision:** Implement Host 2 (Resolver) using `socketserver.ThreadingUDPServer` or a dedicated thread worker pool for incoming datagrams.
* **Rationale:** Decouples incoming client request reception from blocking upstream network I/O, ensuring multiple concurrent clients are served simultaneously.

---

### ADR-008: Error Handling Separation (`MSG_RESPONSE` Status vs. `MSG_ERROR`)
* **Date:** 2026-10-19
* **Status:** Accepted
* **Context:** Disambiguate when `msg_type == MSG_ERROR` (`0x03`) is used vs. when `msg_type == MSG_RESPONSE` (`0x02`) with a non-zero status code (`0x01 NXDOMAIN`, `0x02 SERVER_FAILURE`, `0x03 FORMAT_ERROR`).
* **Alternatives Considered:**
  1. *Use `MSG_ERROR` for all non-success outcomes:* Breaks DNS symmetry where NXDOMAIN is a normal response containing authoritative status.
* **Decision:**
  * **`MSG_RESPONSE` (`0x02`):** Used for all DNS answers, including `STATUS_SUCCESS` (`0x00`), `STATUS_NXDOMAIN` (`0x01`), and `STATUS_SERVER_FAILURE` (`0x02`).
  * **`MSG_ERROR` (`0x03`):** Reserved strictly for unrecoverable wire-level syntax violations (`STATUS_FORMAT_ERROR`), such as truncated headers or illegal length prefixes, where a valid response payload cannot be generated.
* **Rationale:** Mirrors RFC DNS RCODE architecture while preserving explicit signaling for transport-level malformed packets.

---

### ADR-009: Decoupled Protocol-First Architecture (`src/protocol.py`)
* **Date:** 2026-10-14
* **Status:** Accepted
* **Context:** Prevent merge conflicts and cross-member blocking during parallel development across the 3 independent modules.
* **Alternatives Considered:**
  1. *Duplicate packing code in each member's script:* Invites endianness, offset, or padding desynchronization.
* **Decision:** Establish `src/protocol.py` as the **sole shared dependency**. Client, Resolver, and Authoritative server modules import `MYDNSMessage` and numerical constants from `protocol.py` and remain completely decoupled otherwise.
* **Rationale:** Allows Member 1 (Client), Member 2 (Resolver), and Member 3 (Auth Server) to build and unit test their respective components in total isolation against a frozen wire contract.

---

### ADR-010: Standardized Fully Qualified Domain Names (`portal.neduet.local`)
* **Date:** 2026-10-19
* **Status:** Accepted
* **Context:** Address minor inconsistencies where sequence diagrams used `portal.local` while wire formulas used `portal.neduet.local`.
* **Alternatives Considered:**
  1. *Use short names (`portal.local`):* Shorter domain length ($L=12$).
* **Decision:** Standardize on `portal.neduet.local` ($L=19$) across all documentation, test scripts, and zone files.
* **Rationale:** Campus-authentic domain naming (`neduet.local`) reflects the actual university deployment environment and provides consistent 28-byte Query / 32-byte Response packet sizes for Wireshark inspection.

### ADR-011: Protocol Implementation Strategy & Unit Test Verification Protocol
* **Date:** 2026-10-21
* **Status:** Accepted
* **Context:** A formal plan is required to guide the safe, verifiable implementation of `src/protocol.py` before distributing the module to team members.
* **Alternatives Considered:**
  1. *Ad-hoc coding without a written plan:* Risks subtle boundary errors (e.g. truncated packets or off-by-one errors on domain bounds) and uneven test coverage.
* **Decision:** Adopt a strict 5-phase implementation plan outlined in `gemini-docs/protocol_implementation_plan.md`, covering class scaffolding, 5-argument `struct.pack('!HBBBxH')` packing, multi-tier `unpack()` bounds validation, and a 12-case automated unit test suite (`tests/test_protocol.py`).
* **Rationale:** Enforces complete boundary test coverage ($L=1$ to $L=255$), verifies Network Byte Order (`!`), guarantees 100% roundtrip byte preservation, and ensures zero desynchronization before Member 1, 2, and 3 build their dependent modules.

### ADR-012: Implementation & Verification of Protocol Engine (`src/protocol.py`)
* **Date:** 2026-10-21 (Updated: 2026-10-24)
* **Status:** Implemented & Verified
* **Context:** Following ADR-009 and ADR-011, the core wire contract module `src/protocol.py` and unit test suite `tests/test_protocol.py` needed to be built and verified against all specified boundaries and byte alignments.
* **Decision:** Implemented `MYDNSMessage` with 64-bit Big-Endian header (`!HBBBxH`), domain bounds enforcement ($1 \le L \le 255$), ASCII character validation, conditional 4-byte IPv4 trailer formatting, multi-tier deserialization guards, diagnostic hex dumps, and standalone interactive CLI self-check (`__main__`). Verified with a 17-case automated test suite (100% pass rate in 0.001s).
* **SHA-256 Checksums:**
  * **Canonical Repo / LF:** `351BAF0F33C662E9A50E64AC64F7B02EA7151F36D55F2A129256CF5DABA0521B`
  * **Windows Checkout (CRLF):** `22EA136B541C022E6A0C62296B19371BEFF34705173D2AF7A4B2487690016797`
  * *(Historical note: Initial commit `fe23e16` before the `__main__` block had hash `C9E1188FA63F5261665EDE7CBA23FF8B17BA7F25E1CBF3D5398D34E6D52968B9` (LF) / `BD676BC2C31AF15147FF34B6110A252464DCE83CBF11749CF40AD1A972E20FD1` (CRLF); `81AA0F...` was the pre-commit buffer without an EOF newline).*
* **Impact:** Unblocks Member 1 (Client), Member 2 (Resolver), and Member 3 (Authoritative Server) for parallel independent development.

---

## Maintenance Invariant

> [!IMPORTANT]
> **Continuous Audit Requirement:** Any future architectural modifications, packet format changes, timing parameter updates, or structural refactorings **MUST** be recorded as a new ADR entry in this file, citing the date, status, context, alternatives, rationale, and impact.

