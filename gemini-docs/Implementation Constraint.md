# Implementation Constraints & Modular Dependency Architecture
**Project:** CS-327 Computer Communication Networks — Complex Engineering Problem (CEP)  
**Track:** Option B — Mini DNS Service (`MYDNS/1.0`)  
**Document Purpose:** Define modularity boundaries and the single shared protocol dependency.

---

## 1. Modularity Overview

The system is designed as a **distributed, modular application**. Because it operates across three independent physical or virtual network endpoints, the components **do not share runtime memory, global state, databases, or threads**. Each component runs as a standalone OS process communicating strictly over low-level UDP sockets.

However, there is **exactly one critical shared dependency** that acts as the backbone contract across all three nodes:

---

## 2. The Single Shared Dependency: `src/protocol.py`

In any custom networked application, every host must speak the **exact same binary language**:

```
                                  +-------------------------------------+
                                  |           src/protocol.py           |
                                  |   (Shared Binary Wire Contract)     |
                                  | - 8-Byte Binary Header (!HBBBxH)    |
                                  | - pack() / unpack() SerDes          |
                                  | - Message Types & Status Constants  |
                                  +-------------------------------------+
                                       /              |              \
                       +--------------+               |               +---------------+
                       |                              |                               |
                       v                              v                               v
+-------------------------------+ +-------------------------------+ +-------------------------------+
|       HOST 1: CLIENT          | |      HOST 2: RESOLVER         | |    HOST 3: AUTH SERVER        |
|       (src/client.py)         | |      (src/resolver.py)        | | (src/authoritative_server.py) |
|   Lead: Asadullah Zafar       | |    Lead: Atta-Ur-Rehman       | |     Lead: Abdur Rahman        |
+-------------------------------+ +-------------------------------+ +-------------------------------+
```

### Why `protocol.py` Must Be Shared:
1. **Binary Encoding Symmetry:** When Host 1 serializes a query using `struct.pack('!HBBBxH', ...)`, Host 2 must parse it with the exact same byte offsets, field widths, endianness, and padding.
2. **Shared Numerical Constants:** Constants such as:
   * **Message Types:** `MSG_QUERY (0x01)`, `MSG_RESPONSE (0x02)`, `MSG_ERROR (0x03)`
   * **Status Codes:** `STATUS_SUCCESS (0x00)`, `STATUS_NXDOMAIN (0x01)`, `STATUS_SERVER_FAILURE (0x02)`, `STATUS_FORMAT_ERROR (0x03)`
   * **Query Types:** `TYPE_A (0x01)`
   must have identical numerical representations across all three programs.

> [!CAUTION]
> **Constraint Violation Warning:** If `protocol.py` is modified or inconsistent between devices (e.g., if one member changes a field from 8-bit to 16-bit without syncing), the other nodes will fail to decode the packet, resulting in `STATUS_FORMAT_ERROR` or corrupted data.

---

## 3. How the Remaining Modules Are Decoupled

Aside from importing `protocol.py`, each member's module has **zero dependency on the other members' internal code**:

| Module | What It Owns & Encapsulates | Zero Dependency On |
| :--- | :--- | :--- |
| **`src/authoritative_server.py`** *(Member 3)* | Reads `zone.json`, manages authoritative domain mappings, listens on port `53053`. | Doesn't care about caches, TTL timers, or client RTT benchmarks. |
| **`src/resolver.py`** *(Member 2)* | In-memory cache dictionary, dynamic TTL countdown, multi-threaded request pool, timeout retry logic. | Doesn't care how the client renders graphs or how the authoritative server loads its zone file. |
| **`src/client.py`** *(Member 1)* | Microsecond `time.perf_counter()` RTT timers, CLI parsing, automated 10-trial benchmark loop, Matplotlib graph generation. | Doesn't care how the resolver implements its cache or how the authoritative server is configured. |

---

## 4. Team Workflow Strategy: Protocol-First Development

To ensure all three team members can develop in parallel without blocking one another:

1. **Step 1 (First Priority): Implement & Freeze `src/protocol.py`**
   * Member 3 writes `src/protocol.py`.
   * The team runs unit tests to confirm that queries and responses serialize and deserialize with 100% byte fidelity.
   * All team members pull or copy this file into their local working directories.
2. **Step 2 (Parallel Development):**
   * **Abdur Rahman:** Builds `authoritative_server.py` and `zone.json`.
   * **Atta-Ur-Rehman:** Builds `resolver.py` (caching and concurrency).
   * **Asadullah Zafar:** Builds `client.py` and `benchmark_runner.py`.
3. **Step 3 (Integration & Deployment):**
   * Bring all three scripts together on your laptops (or bridged VMs) and run the full 3-host test across independent IP addresses.

