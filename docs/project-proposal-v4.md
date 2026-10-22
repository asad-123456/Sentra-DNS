# PROJECT PROPOSAL

**Course:** CS-327 Computer Communication Networks (Fall Semester 2026)  
**Project Title:** Design, Implementation, and Evaluation of a Multi-Host Networked Application  
**Selected Track:** **Option B — Mini DNS Service** (`MYDNS/1.0`)  
**Group Size:** 3 Members  

---

### **Group Members & Lead Responsibilities**
* **Member 1:** Asadullah Zafar (`CS-24082`) — *Lead: Client Engine, Microsecond RTT Benchmarking Suite & Delay Modeling*
* **Member 2:** Atta-Ur-Rehman (`CS-24092`) — *Lead: Resolver Caching Logic, Thread-Safe TTL Engine & Failure Recovery*
* **Member 3:** Abdur Rahman (`CS-24098`) — *Lead: Authoritative Zone Server, Packet Encoding Specification & Wireshark Encapsulation Analysis*

---

### **1. Project Overview & 3-Host Architecture**
Our team will design and implement an original application-layer DNS protocol (`MYDNS/1.0`) directly over native UDP sockets without third-party networking libraries. The system is deployed across **three independent network endpoints**:

```
+--------------------+            +-----------------------+            +-----------------------------+
|   HOST 1: CLIENT   |   Query    |   HOST 2: RESOLVER    |   Query    | HOST 3: AUTHORITATIVE SERVER|
|   (192.168.1.10)   | ---------> |    (192.168.1.11)     | ---------> |       (192.168.1.12)        |
|                    | <--------- | (Checks In-Memory TTL)| <--------- |                             |
|  - Measures RTT    |  Response  |  - Cache HIT: Local   |  Response  | - Holds Master Records      |
|  - Retransmission  |            |  - Cache MISS: Fwd    |            |   (domain.local -> IPv4)    |
+--------------------+            +-----------------------+            +-----------------------------+
```

* **Host 1 (Client):** Generates domain lookups, measures high-resolution Round-Trip Time (RTT in ms), and manages stop-and-wait timeout retransmissions.
* **Host 2 (Caching Resolver):** Intercepts client queries, manages an in-memory dictionary cache with dynamic TTL tracking, handles cache hits/misses, and forwards uncached requests.
* **Host 3 (Authoritative Server):** Maintains master zone records (`domain.local -> IPv4`) and authoritative TTL parameters.

---

### **2. Intended Protocol Specification (`MYDNS/1.0`)**
Communication uses a fixed **64-bit (8-byte) binary header** packed using Python's native `struct` library (`!HBBBxH`):

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

* **Transaction ID (16 bits):** Unsigned short (`!H`). Matches asynchronous request-reply pairs.
* **Message Type (8 bits):** `0x01` = QUERY, `0x02` = RESPONSE, `0x03` = ERROR.
* **Query Type (8 bits):** `0x01` = TYPE_A (IPv4 record lookup).
* **Status Code (8 bits):** `0` = SUCCESS, `1` = NXDOMAIN, `2` = SERVER_FAILURE, `3` = FORMAT_ERROR.
* **Reserved (8 bits):** Byte alignment padding (`0x00`).
* **TTL (16 bits):** Time-To-Live validity in seconds.
* **Payload:** 1-byte domain length prefix + ASCII domain string + 4-byte raw IPv4 address (`socket.inet_aton`, response only).

---

### **3. Transport Justification & Deployment Plan**
* **Transport Layer Choice:** **UDP (`SOCK_DGRAM`)**. DNS requires minimal latency (0-RTT setup) and low byte overhead. Query loss is handled at the application layer via client-side stop-and-wait retransmission timers (`socket.settimeout(1.5)`), avoiding heavyweight TCP handshake overhead.
* **Deployment Hardware (3 Independent Endpoints):**
  * **Host 1 (Client):** `192.168.1.10` (Bridged Network Endpoint)
  * **Host 2 (Resolver):** `192.168.1.11` (Bridged Network Endpoint)
  * **Host 3 (Authoritative Server):** `192.168.1.12` (Bridged Network Endpoint)

---

### **4. Experimental Benchmarks, Design Tensions & Sustainability**
* **Performance Benchmarks (R6):** Measure RTT across $\ge 5$ trials comparing **Cache Hit vs. Cache Miss**, mapped to the nodal delay model ($T_{nodal} = d_{proc} + d_{queue} + d_{trans} + d_{prop}$).
* **Failure Analysis (R7):** Simulate an unreachable authoritative host and verify resolver timeout handling and client-side error signaling.
* **Design Tensions Defended:** 
  1. *Caching freshness vs. traffic reduction* (TTL tuning and stale data risks).
  2. *Reliability vs. latency* (UDP application-layer retransmission vs. TCP connection establishment).
  3. *Compactness vs. readability* (binary packed structs vs. verbose text/JSON payloads).
* **Sustainability Analysis (Section 7):** Cache hits save 50 bytes per query ($100\text{ bytes cache miss}$ vs $50\text{ bytes cache hit}$), delivering an exact **50% bandwidth and NIC energy reduction** per query.

---

**Signatures:**

`_________________________` (Asadullah Zafar) &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; `_________________________` (Atta-Ur-Rehman) &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; `_________________________` (Abdur Rahman)
