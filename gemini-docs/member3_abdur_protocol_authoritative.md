# Member 3 Module Guide: Protocol Engineering & Authoritative Server
**Lead:** Abdur Rahman (`CS-24098`)  
**Core Responsibilities:**
1. Custom Binary Protocol Specification & Serialization (`src/protocol.py`)
2. Authoritative Zone Server (`src/authoritative_server.py`) & Zone Database (`src/zone.json`)
3. Wireshark Encapsulation Analysis & Dissection (Mandatory Requirement R5)

---

## 1. Technical Overview & Role in the System
As Member 3, your work is the **foundation of the entire project**. Both Member 2 (Resolver) and Member 1 (Client) depend directly on your `protocol.py` module to pack and unpack `MYDNS/1.0` binary packets over native UDP sockets. Additionally, you are responsible for Host 3 (Authoritative Server), which is the source of truth for all domain mappings.

```
+---------------------------------+
|  Host 3: Authoritative Server   | <--- Listens on UDP 53053
|  (Abdur Rahman's Core Module)   | <--- Reads src/zone.json
+---------------------------------+
                 ^
                 | (Cache Miss: MYDNS/1.0 Query)
                 v
+---------------------------------+
|   Host 2: Caching Resolver      |
+---------------------------------+
```

---

## 2. Protocol Specification (`src/protocol.py`)

### 64-bit Binary Header Structure
The binary header is packed using Python's `struct` library with network byte order (`!` big-endian):
Format String: `!HBBBxH` (Total 8 bytes)

```
 0                   1                   2                   3
 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|        Transaction ID         |  Msg Type (8) |  Query Type(8)|
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|   Status (8)  |   Reserved(8) |              TTL (16)         |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
| Domain Length |               Domain Name (Variable ASCII)    |
+-+-+-+-+-+-+-+-+                                               +
|               | Resolved IPv4 Address (4 Bytes, if Response)  |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
```

### Protocol Constants
```python
# Message Types (8 bits)
MSG_QUERY    = 0x01
MSG_RESPONSE = 0x02
MSG_ERROR    = 0x03

# Query Types (8 bits)
TYPE_A       = 0x01  # IPv4 Address Lookup

# Status Codes (8 bits)
STATUS_SUCCESS        = 0x00
STATUS_NXDOMAIN       = 0x01  # Domain does not exist
STATUS_SERVER_FAILURE = 0x02  # Upstream server timeout/unreachable
STATUS_FORMAT_ERROR   = 0x03  # Malformed packet header or payload
```

### Packet Class Implementation Guide
In `src/protocol.py`, define `MYDNSMessage`:
* `pack(self) -> bytes`:
  1. Encode domain to ASCII bytes: `domain_bytes = self.domain.encode('ascii')`.
  2. Domain length prefix: `len(domain_bytes)` (1 byte `!B`).
  3. Header: `struct.pack('!HBBBxH', self.tx_id, self.msg_type, self.query_type, self.status, self.ttl)`. Note: Exactly 5 arguments (pad byte `x` is automatic).
  4. Assemble:
     * If `self.msg_type == MSG_RESPONSE`:
       `ip_bytes = socket.inet_aton(self.ip_address if self.ip_address else '0.0.0.0')`
       `return header + struct.pack('!B', len(domain_bytes)) + domain_bytes + ip_bytes`
     * Else (QUERY / ERROR):
       `return header + struct.pack('!B', len(domain_bytes)) + domain_bytes`
* `unpack(data: bytes) -> 'MYDNSMessage'`:
  1. Validate `len(data) >= 10`.
  2. Unpack header fields: `tx_id, msg_type, query_type, status, ttl = struct.unpack('!HBBBxH', data[:8])`.
  3. Extract domain length: `domain_len = data[8]`.
  4. Extract domain string: `data[9 : 9 + domain_len].decode('ascii')`.
  5. If `msg_type == MSG_RESPONSE`:
     `ip_address = socket.inet_ntoa(data[9 + domain_len : 13 + domain_len])`
     Else:
     `ip_address = None`

---

## 3. Authoritative Name Server (`src/authoritative_server.py`)

### Master Zone File (`src/zone.json`)
```json
{
  "portal.neduet.local": {"ip": "10.0.1.5", "ttl": 120},
  "lms.neduet.local": {"ip": "10.0.1.10", "ttl": 180},
  "mail.neduet.local": {"ip": "10.0.1.15", "ttl": 300},
  "cs.neduet.local": {"ip": "10.0.2.1", "ttl": 60},
  "library.neduet.local": {"ip": "10.0.3.20", "ttl": 240}
}
```

### Server Logic
1. Load `zone.json` into a Python dictionary.
2. Create UDP socket: `sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)`.
3. Bind to port `53053`: `sock.bind(('0.0.0.0', 53053))`.
4. Loop forever:
   * `data, client_addr = sock.recvfrom(512)`
   * Unpack query using `MYDNSMessage.unpack(data)`.
   * Check if `query.domain` in zone:
     * **Match:** Build `MYDNSMessage` with `msg_type=MSG_RESPONSE`, `status=STATUS_SUCCESS`, `ip_address=record['ip']`, `ttl=record['ttl']`.
     * **No Match:** Build `MYDNSMessage` with `msg_type=MSG_RESPONSE`, `status=STATUS_NXDOMAIN`, `ip_address='0.0.0.0'`, `ttl=0`.
   * Send response back: `sock.sendto(response.pack(), client_addr)`.

---

## 4. Wireshark Encapsulation Analysis (Requirement R5)

For the final report, you must capture a live packet in Wireshark and annotate each layer's contribution:
1. **Link Layer (Ethernet II):**
   * Preamble, Destination MAC, Source MAC, Type (`0x0800` = IPv4).
   * Contribution: Delivers frame across the physical local link between network interface cards (NICs).
2. **Network Layer (IPv4):**
   * Source IP, Destination IP, Protocol (`17` = UDP), Time To Live (IP TTL, e.g., 64 or 128), Total Length.
   * Contribution: Global/subnet routing and host-to-host datagram delivery across intermediate routers.
3. **Transport Layer (UDP):**
   * Source Port, Destination Port (`53053`), Length, Checksum.
   * Contribution: Process-to-process multiplexing and demultiplexing without connection setup overhead.
4. **Application Layer (`MYDNS/1.0`):**
   * Show hex bytes corresponding to your 8-byte header and payload:
     - Byte 0-1: Transaction ID
     - Byte 2: Message Type (`0x01` / `0x02`)
     - Byte 3: Query Type (`0x01`)
     - Byte 4: Status Code (`0x00` / `0x01`)
     - Byte 5: Padding (`0x00`)
     - Byte 6-7: TTL (e.g., `0x0078` = 120s)
     - Followed by Domain Length prefix and ASCII domain.

---

## 5. Getting Started Checklist
- [x] Create `src/protocol.py` and implement `MYDNSMessage` with `pack()` and `unpack()`. (Completed & SHA256 Verified)
- [x] Create `tests/test_protocol.py` to test round-trip packing and unpacking. (17/17 Tests Passing)
- [ ] Create `src/zone.json` with sample local domain records.
- [ ] Implement `src/authoritative_server.py`.
- [ ] Verify standalone using a basic netcat/Python test query.

