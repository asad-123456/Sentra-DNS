"""
MYDNS/1.0 Protocol Implementation Module
Course: CS-327 Computer Communication Networks (Fall 2026)
Track: Option B — Mini DNS Service (MYDNS/1.0)
Lead Protocol Engineer: Abdur Rahman (CS-24098)
Collaborators: Atta-Ur-Rehman (CS-24092), Asadullah Zafar (CS-24082)
Institution: Department of Computer & Information Systems Engineering,
             NED University of Engineering & Technology

This module defines the single shared wire contract for the MYDNS/1.0 protocol.
It implements the 64-bit (8-byte) binary header format (!HBBBxH) and provides
deterministic serialization (pack) and deserialization (unpack) routines over
native UDP datagrams without third-party dependencies.
"""

from typing import Optional, Dict, Any
import socket
import struct

# ============================================================================
# Protocol Numerical Constants
# ============================================================================

# Message Types (8 bits / 1 byte)
MSG_QUERY: int = 0x01             # Client lookup request (IPv4 trailer omitted)
MSG_RESPONSE: int = 0x02          # Resolver / Authoritative server answer (includes 4-byte IPv4)
MSG_ERROR: int = 0x03             # Wire-level format violation notification

# Query Types (8 bits / 1 byte)
TYPE_A: int = 0x01                # Standard IPv4 Host Address query

# Status Codes (8 bits / 1 byte)
STATUS_SUCCESS: int = 0x00        # Resolution succeeded; valid IPv4 returned
STATUS_NXDOMAIN: int = 0x01       # Non-Existent Domain; record absent from zone
STATUS_SERVER_FAILURE: int = 0x02 # Resolver timed out querying authoritative server
STATUS_FORMAT_ERROR: int = 0x03   # Malformed header, invalid length, or bad syntax

# Wire Framing Constants
HEADER_FORMAT: str = '!HBBBxH'
HEADER_SIZE: int = struct.calcsize(HEADER_FORMAT)  # Exactly 8 bytes
MIN_PACKET_SIZE: int = HEADER_SIZE + 1 + 1          # 10 bytes: 8B header + 1B len + 1B min domain

# Human-Readable Mappings for Logging & Diagnostics
MSG_TYPE_NAMES: Dict[int, str] = {
    MSG_QUERY: "QUERY",
    MSG_RESPONSE: "RESPONSE",
    MSG_ERROR: "ERROR",
}

QUERY_TYPE_NAMES: Dict[int, str] = {
    TYPE_A: "TYPE_A",
}

STATUS_NAMES: Dict[int, str] = {
    STATUS_SUCCESS: "SUCCESS",
    STATUS_NXDOMAIN: "NXDOMAIN",
    STATUS_SERVER_FAILURE: "SERVER_FAILURE",
    STATUS_FORMAT_ERROR: "FORMAT_ERROR",
}

VALID_MSG_TYPES = (MSG_QUERY, MSG_RESPONSE, MSG_ERROR)
VALID_QUERY_TYPES = (TYPE_A,)
VALID_STATUS_CODES = (STATUS_SUCCESS, STATUS_NXDOMAIN, STATUS_SERVER_FAILURE, STATUS_FORMAT_ERROR)


class MYDNSMessage:
    """
    Representation of a MYDNS/1.0 protocol message.

    Encapsulates the 8-byte fixed binary header and variable-length payload.
    Supports network-order serialization (pack) and parsing (unpack).

    Attributes:
        tx_id (int): 16-bit Transaction ID matching request and response pairs.
        msg_type (int): 8-bit message role (MSG_QUERY, MSG_RESPONSE, MSG_ERROR).
        query_type (int): 8-bit query type (TYPE_A = 0x01).
        status (int): 8-bit status code (STATUS_SUCCESS, STATUS_NXDOMAIN, etc.).
        ttl (int): 16-bit Time-To-Live in seconds (0 to 65535).
        domain (str): ASCII domain name string (1 to 255 characters).
        ip_address (Optional[str]): Dotted-decimal IPv4 address (response only).
    """

    def __init__(
        self,
        tx_id: int,
        msg_type: int,
        query_type: int = TYPE_A,
        status: int = STATUS_SUCCESS,
        ttl: int = 0,
        domain: str = "",
        ip_address: Optional[str] = None
    ) -> None:
        if not isinstance(tx_id, int) or isinstance(tx_id, bool) or not (0 <= tx_id <= 0xFFFF):
            raise ValueError(f"Transaction ID must be a 16-bit unsigned integer (0-65535), got {tx_id}")
        if msg_type not in VALID_MSG_TYPES:
            raise ValueError(f"Invalid Message Type: {msg_type:#04x} (expected 0x01, 0x02, or 0x03)")
        if query_type not in VALID_QUERY_TYPES:
            raise ValueError(f"Invalid Query Type: {query_type:#04x} (only TYPE_A=0x01 supported)")
        if status not in VALID_STATUS_CODES:
            raise ValueError(f"Invalid Status Code: {status:#04x}")
        if not isinstance(ttl, int) or isinstance(ttl, bool) or not (0 <= ttl <= 0xFFFF):
            raise ValueError(f"TTL must be a 16-bit unsigned integer (0-65535), got {ttl}")
        if not isinstance(domain, str):
            raise TypeError(f"Domain must be a string, got {type(domain).__name__}")

        self.tx_id: int = tx_id
        self.msg_type: int = msg_type
        self.query_type: int = query_type
        self.status: int = status
        self.ttl: int = ttl
        self.domain: str = domain
        self.ip_address: Optional[str] = ip_address

    def pack(self) -> bytes:
        """
        Serializes the MYDNSMessage into raw wire bytes in Network Byte Order (Big-Endian).

        Packet Size:
          - MSG_QUERY:    8 (header) + 1 (len) + L (domain) = 9 + L bytes
          - MSG_ERROR:    8 (header) + 1 (len) + L (domain) = 9 + L bytes
          - MSG_RESPONSE: 8 (header) + 1 (len) + L (domain) + 4 (IPv4) = 13 + L bytes

        Returns:
            bytes: The packed binary datagram ready for UDP transmission.

        Raises:
            ValueError: If domain length is not 1-255 bytes, domain contains non-ASCII
                        characters, or IPv4 format is invalid for response messages.
        """
        # 1. Header Packing (8 bytes)
        header_bytes = struct.pack(
            HEADER_FORMAT,
            self.tx_id,
            self.msg_type,
            self.query_type,
            self.status,
            self.ttl
        )

        # 2. Domain Encoding & Bounds Validation
        try:
            domain_bytes = self.domain.encode('ascii')
        except UnicodeEncodeError as e:
            raise ValueError(f"Domain must contain only ASCII characters: {e}")

        domain_len = len(domain_bytes)
        if not (1 <= domain_len <= 255):
            raise ValueError(f"Domain length must be between 1 and 255 bytes (got {domain_len})")

        domain_payload = struct.pack('!B', domain_len) + domain_bytes

        # 3. Conditional IPv4 Trailer
        if self.msg_type == MSG_RESPONSE:
            ip_str = self.ip_address if self.ip_address is not None else "0.0.0.0"
            parts = ip_str.split('.')
            if len(parts) != 4 or not all(p.isdigit() and 0 <= int(p) <= 255 for p in parts):
                raise ValueError(f"Invalid IPv4 address format '{ip_str}'")
            try:
                ip_bytes = socket.inet_aton(ip_str)
            except OSError as e:
                raise ValueError(f"Invalid IPv4 address format '{ip_str}': {e}")
            return header_bytes + domain_payload + ip_bytes
        else:
            # For MSG_QUERY and MSG_ERROR, omit the 4-byte IP trailer
            return header_bytes + domain_payload

    @classmethod
    def unpack(cls, data: bytes) -> 'MYDNSMessage':
        """
        Deserializes raw wire bytes in Network Byte Order (Big-Endian) into a MYDNSMessage.

        Args:
            data: Raw datagram received from UDP socket.

        Returns:
            MYDNSMessage: Fully populated message instance.

        Raises:
            TypeError: If data is not bytes or bytearray.
            ValueError: If packet is truncated below 10 bytes, has invalid header fields,
                        invalid domain length, or missing IPv4 trailer on response.
        """
        if not isinstance(data, (bytes, bytearray)):
            raise TypeError("Packet data must be bytes or bytearray")

        # 1. Minimum Length Guard (Header 8B + Domain Len 1B + Min 1-Char Domain 1B = 10B)
        if len(data) < MIN_PACKET_SIZE:
            raise ValueError(
                f"Packet truncated below minimum {MIN_PACKET_SIZE}-byte threshold (got {len(data)} bytes)"
            )

        # 2. Header Unpacking (First 8 bytes)
        try:
            tx_id, msg_type, query_type, status, ttl = struct.unpack(HEADER_FORMAT, data[:HEADER_SIZE])
        except struct.error as e:
            raise ValueError(f"Failed to unpack header: {e}")

        # Validate header fields
        if msg_type not in VALID_MSG_TYPES:
            raise ValueError(f"Invalid Message Type in packet: {msg_type:#04x}")
        if query_type not in VALID_QUERY_TYPES:
            raise ValueError(f"Invalid Query Type in packet: {query_type:#04x}")
        if status not in VALID_STATUS_CODES:
            raise ValueError(f"Invalid Status Code in packet: {status:#04x}")

        # 3. Domain Length Extraction & Boundary Validation
        domain_len = data[HEADER_SIZE]  # byte at index 8
        if domain_len < 1 or domain_len > 255:
            raise ValueError(f"Invalid domain length: {domain_len}")

        # 4. Payload Boundary Checks & Extraction
        domain_start = HEADER_SIZE + 1  # index 9
        domain_end = domain_start + domain_len

        if msg_type == MSG_RESPONSE:
            expected_min_len = domain_end + 4  # 13 + domain_len
            if len(data) < expected_min_len:
                raise ValueError("Response packet missing required 4-byte IPv4 trailer")
            try:
                domain = data[domain_start:domain_end].decode('ascii')
            except UnicodeDecodeError as e:
                raise ValueError(f"Invalid ASCII in domain: {e}")

            ip_bytes = data[domain_end:domain_end + 4]
            ip_address = socket.inet_ntoa(ip_bytes)
        else:
            # MSG_QUERY or MSG_ERROR
            expected_min_len = domain_end  # 9 + domain_len
            if len(data) < expected_min_len:
                raise ValueError("Query packet payload truncated")
            try:
                domain = data[domain_start:domain_end].decode('ascii')
            except UnicodeDecodeError as e:
                raise ValueError(f"Invalid ASCII in domain: {e}")

            ip_address = None

        return cls(
            tx_id=tx_id,
            msg_type=msg_type,
            query_type=query_type,
            status=status,
            ttl=ttl,
            domain=domain,
            ip_address=ip_address
        )

    def get_msg_type_name(self) -> str:
        """Returns the human-readable string representation of the message type."""
        return MSG_TYPE_NAMES.get(self.msg_type, f"UNKNOWN({self.msg_type:#04x})")

    def get_query_type_name(self) -> str:
        """Returns the human-readable string representation of the query type."""
        return QUERY_TYPE_NAMES.get(self.query_type, f"UNKNOWN({self.query_type:#04x})")

    def get_status_name(self) -> str:
        """Returns the human-readable string representation of the status code."""
        return STATUS_NAMES.get(self.status, f"UNKNOWN({self.status:#04x})")

    def to_dict(self) -> Dict[str, Any]:
        """Returns a dictionary representation suitable for logging or JSON serialization."""
        return {
            "tx_id": self.tx_id,
            "tx_id_hex": f"{self.tx_id:#06x}",
            "msg_type": self.msg_type,
            "msg_type_name": self.get_msg_type_name(),
            "query_type": self.query_type,
            "query_type_name": self.get_query_type_name(),
            "status": self.status,
            "status_name": self.get_status_name(),
            "ttl": self.ttl,
            "domain": self.domain,
            "ip_address": self.ip_address,
        }

    @staticmethod
    def format_hex(data: bytes, bytes_per_line: int = 16) -> str:
        """
        Generates a Wireshark-style formatted hex dump with byte offsets and ASCII view.

        Args:
            data: Binary payload to format.
            bytes_per_line: Number of bytes per display line (default 16).

        Returns:
            str: Multi-line formatted hex dump.
        """
        lines = []
        for offset in range(0, len(data), bytes_per_line):
            chunk = data[offset:offset + bytes_per_line]
            hex_part = " ".join(f"{b:02X}" for b in chunk)
            ascii_part = "".join(chr(b) if 32 <= b <= 126 else "." for b in chunk)
            lines.append(f"{offset:04x}   {hex_part:<{bytes_per_line * 3}}  {ascii_part}")
        return "\n".join(lines)

    def hex_dump(self, data: Optional[bytes] = None, formatted: bool = False) -> str:
        """
        Returns a hex dump of the packed packet (or provided bytes).

        Args:
            data: Optional explicit bytes; if None, packs this message.
            formatted: If True, returns multi-line offset+hex+ascii dump.
                       If False, returns space-separated hex bytes.
        """
        raw = data if data is not None else self.pack()
        if formatted:
            return self.format_hex(raw)
        return " ".join(f"{b:02X}" for b in raw)

    def __repr__(self) -> str:
        return (
            f"<MYDNSMessage tx_id={self.tx_id:#06x} "
            f"type={self.get_msg_type_name()} "
            f"qtype={self.get_query_type_name()} "
            f"status={self.get_status_name()} "
            f"ttl={self.ttl}s "
            f"domain='{self.domain}' "
            f"ip='{self.ip_address}'>"
        )

    def __str__(self) -> str:
        return self.__repr__()

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, MYDNSMessage):
            return False
        return (
            self.tx_id == other.tx_id
            and self.msg_type == other.msg_type
            and self.query_type == other.query_type
            and self.status == other.status
            and self.ttl == other.ttl
            and self.domain == other.domain
            and self.ip_address == other.ip_address
        )


if __name__ == "__main__":
    print("=" * 70)
    print("MYDNS/1.0 Protocol Demonstration & Self-Check")
    print("Course: CS-327 Computer Communication Networks (Fall 2026)")
    print("=" * 70)

    # 1. Build & Pack a Query
    print("\n1. Constructing Sample Query for 'portal.neduet.local':")
    sample_query = MYDNSMessage(
        tx_id=0xA1B2,
        msg_type=MSG_QUERY,
        query_type=TYPE_A,
        domain="portal.neduet.local"
    )
    query_raw = sample_query.pack()
    print(f"   Object:       {sample_query}")
    print(f"   Wire Length:  {len(query_raw)} bytes (Formula: 8 header + 1 len + 19 domain = 28B)")
    print(f"   Hex Dump:     {sample_query.hex_dump()}")
    print("   Wireshark Inspection Format:")
    for line in MYDNSMessage.format_hex(query_raw).splitlines():
        print(f"     {line}")

    # 2. Unpack Query
    unpacked_q = MYDNSMessage.unpack(query_raw)
    assert unpacked_q == sample_query, "Query round-trip assertion failed!"
    print("   [+] Query unpacked successfully with 100% round-trip fidelity.")

    # 3. Build & Pack a Response
    print("\n2. Constructing Sample Response (ip='10.0.1.5', ttl=120s):")
    sample_response = MYDNSMessage(
        tx_id=sample_query.tx_id,
        msg_type=MSG_RESPONSE,
        query_type=TYPE_A,
        status=STATUS_SUCCESS,
        ttl=120,
        domain=sample_query.domain,
        ip_address="10.0.1.5"
    )
    resp_raw = sample_response.pack()
    print(f"   Object:       {sample_response}")
    print(f"   Wire Length:  {len(resp_raw)} bytes (Formula: 8 header + 1 len + 19 domain + 4 IPv4 = 32B)")
    print(f"   Hex Dump:     {sample_response.hex_dump()}")
    print("   Wireshark Inspection Format:")
    for line in MYDNSMessage.format_hex(resp_raw).splitlines():
        print(f"     {line}")

    # 4. Unpack Response
    unpacked_r = MYDNSMessage.unpack(resp_raw)
    assert unpacked_r == sample_response, "Response round-trip assertion failed!"
    print("   [+] Response unpacked successfully with 100% round-trip fidelity.")

    print("\n" + "=" * 70)
    print("[SUCCESS] MYDNS/1.0 protocol engine is 100% ready and verified!")
    print("Run automated test suite: python -m unittest discover -s tests -p 'test_*.py' -v")
    print("=" * 70)


