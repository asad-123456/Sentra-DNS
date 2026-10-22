"""
Unit Test Suite for MYDNS/1.0 Protocol SerDes Engine
Course: CS-327 Computer Communication Networks (Fall 2026)
Track: Option B — Mini DNS Service (MYDNS/1.0)
Lead Protocol Engineer: Abdur Rahman (CS-24098)
Collaborators: Atta-Ur-Rehman (CS-24092), Asadullah Zafar (CS-24082)
Target File: src/protocol.py

Verifies 100% roundtrip byte fidelity, big-endian alignment, boundary invariants,
and resilient exception handling for all packet types.
"""

import os
import sys
import struct
import unittest

# Ensure src/ is on sys.path for direct script execution
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from protocol import (
    MYDNSMessage,
    MSG_QUERY,
    MSG_RESPONSE,
    MSG_ERROR,
    TYPE_A,
    STATUS_SUCCESS,
    STATUS_NXDOMAIN,
    STATUS_SERVER_FAILURE,
    STATUS_FORMAT_ERROR,
    HEADER_FORMAT,
    HEADER_SIZE,
    MIN_PACKET_SIZE,
)


class TestMYDNSProtocol(unittest.TestCase):
    """Automated test cases for MYDNS/1.0 binary wire protocol serialization & parsing."""

    def test_query_pack_unpack(self):
        """
        Standard Query serialization:
        Header (8B) + Domain Len (1B) + Domain (19B) = 28 Bytes.
        IPv4 trailer must be omitted on wire and None when unpacked.
        """
        domain = "portal.neduet.local"  # 19 characters
        tx_id = 0xA1B2
        msg = MYDNSMessage(
            tx_id=tx_id,
            msg_type=MSG_QUERY,
            query_type=TYPE_A,
            status=STATUS_SUCCESS,
            ttl=0,
            domain=domain
        )

        wire_bytes = msg.pack()
        expected_len = 8 + 1 + len(domain)  # 28 bytes
        self.assertEqual(len(wire_bytes), expected_len)
        self.assertEqual(len(wire_bytes), 28)

        # Unpack and verify byte-for-byte fidelity
        unpacked = MYDNSMessage.unpack(wire_bytes)
        self.assertEqual(unpacked.tx_id, tx_id)
        self.assertEqual(unpacked.msg_type, MSG_QUERY)
        self.assertEqual(unpacked.query_type, TYPE_A)
        self.assertEqual(unpacked.status, STATUS_SUCCESS)
        self.assertEqual(unpacked.ttl, 0)
        self.assertEqual(unpacked.domain, domain)
        self.assertIsNone(unpacked.ip_address)
        self.assertEqual(msg, unpacked)

    def test_response_success_pack_unpack(self):
        """
        Success Response serialization:
        Header (8B) + Domain Len (1B) + Domain (19B) + IPv4 (4B) = 32 Bytes.
        """
        domain = "portal.neduet.local"
        tx_id = 0xA1B2
        ip = "10.0.1.5"
        ttl = 120

        msg = MYDNSMessage(
            tx_id=tx_id,
            msg_type=MSG_RESPONSE,
            query_type=TYPE_A,
            status=STATUS_SUCCESS,
            ttl=ttl,
            domain=domain,
            ip_address=ip
        )

        wire_bytes = msg.pack()
        expected_len = 8 + 1 + len(domain) + 4  # 32 bytes
        self.assertEqual(len(wire_bytes), expected_len)
        self.assertEqual(len(wire_bytes), 32)

        unpacked = MYDNSMessage.unpack(wire_bytes)
        self.assertEqual(unpacked.tx_id, tx_id)
        self.assertEqual(unpacked.msg_type, MSG_RESPONSE)
        self.assertEqual(unpacked.query_type, TYPE_A)
        self.assertEqual(unpacked.status, STATUS_SUCCESS)
        self.assertEqual(unpacked.ttl, ttl)
        self.assertEqual(unpacked.domain, domain)
        self.assertEqual(unpacked.ip_address, ip)
        self.assertEqual(msg, unpacked)

    def test_response_nxdomain(self):
        """
        NXDOMAIN response serialization:
        Status code 0x01, TTL=0, IP defaults to 0.0.0.0.
        Packs to 32 bytes for 19-char domain.
        """
        domain = "portal.neduet.local"
        msg = MYDNSMessage(
            tx_id=0x1234,
            msg_type=MSG_RESPONSE,
            query_type=TYPE_A,
            status=STATUS_NXDOMAIN,
            ttl=0,
            domain=domain,
            ip_address="0.0.0.0"
        )

        wire_bytes = msg.pack()
        self.assertEqual(len(wire_bytes), 32)

        unpacked = MYDNSMessage.unpack(wire_bytes)
        self.assertEqual(unpacked.status, STATUS_NXDOMAIN)
        self.assertEqual(unpacked.ip_address, "0.0.0.0")
        self.assertEqual(unpacked.ttl, 0)
        self.assertEqual(unpacked.domain, domain)

    def test_response_server_failure(self):
        """
        SERVER_FAILURE response serialization:
        Status code 0x02, TTL=0, IP defaults to 0.0.0.0.
        Packs to 32 bytes for 19-char domain.
        """
        domain = "portal.neduet.local"
        msg = MYDNSMessage(
            tx_id=0x5678,
            msg_type=MSG_RESPONSE,
            query_type=TYPE_A,
            status=STATUS_SERVER_FAILURE,
            ttl=0,
            domain=domain,
            ip_address="0.0.0.0"
        )

        wire_bytes = msg.pack()
        self.assertEqual(len(wire_bytes), 32)

        unpacked = MYDNSMessage.unpack(wire_bytes)
        self.assertEqual(unpacked.status, STATUS_SERVER_FAILURE)
        self.assertEqual(unpacked.ip_address, "0.0.0.0")
        self.assertEqual(unpacked.ttl, 0)

    def test_minimum_domain_length(self):
        """
        Boundary test for minimum legal domain length: L = 1 ('a').
        Query packet: 8 + 1 + 1 = 10 bytes (absolute protocol minimum).
        Response packet: 8 + 1 + 1 + 4 = 14 bytes.
        """
        min_domain = "a"

        # 1. Query packet
        query = MYDNSMessage(
            tx_id=1,
            msg_type=MSG_QUERY,
            query_type=TYPE_A,
            domain=min_domain
        )
        query_wire = query.pack()
        self.assertEqual(len(query_wire), 10)
        unpacked_query = MYDNSMessage.unpack(query_wire)
        self.assertEqual(unpacked_query.domain, min_domain)
        self.assertIsNone(unpacked_query.ip_address)

        # 2. Response packet
        resp = MYDNSMessage(
            tx_id=1,
            msg_type=MSG_RESPONSE,
            query_type=TYPE_A,
            status=STATUS_SUCCESS,
            ttl=60,
            domain=min_domain,
            ip_address="127.0.0.1"
        )
        resp_wire = resp.pack()
        self.assertEqual(len(resp_wire), 14)
        unpacked_resp = MYDNSMessage.unpack(resp_wire)
        self.assertEqual(unpacked_resp.domain, min_domain)
        self.assertEqual(unpacked_resp.ip_address, "127.0.0.1")

    def test_maximum_domain_length(self):
        """
        Boundary test for maximum legal domain length: L = 255 ('a' * 255).
        Query packet: 8 + 1 + 255 = 264 bytes.
        Response packet: 8 + 1 + 255 + 4 = 268 bytes.
        """
        max_domain = "a" * 255

        # 1. Query packet
        query = MYDNSMessage(
            tx_id=2,
            msg_type=MSG_QUERY,
            domain=max_domain
        )
        query_wire = query.pack()
        self.assertEqual(len(query_wire), 264)
        unpacked_query = MYDNSMessage.unpack(query_wire)
        self.assertEqual(len(unpacked_query.domain), 255)
        self.assertEqual(unpacked_query.domain, max_domain)

        # 2. Response packet
        resp = MYDNSMessage(
            tx_id=2,
            msg_type=MSG_RESPONSE,
            domain=max_domain,
            ip_address="10.0.0.1"
        )
        resp_wire = resp.pack()
        self.assertEqual(len(resp_wire), 268)
        unpacked_resp = MYDNSMessage.unpack(resp_wire)
        self.assertEqual(len(unpacked_resp.domain), 255)
        self.assertEqual(unpacked_resp.domain, max_domain)
        self.assertEqual(unpacked_resp.ip_address, "10.0.0.1")

    def test_zero_length_domain_rejected(self):
        """
        Boundary test: L = 0 domain must be rejected by both pack() and unpack().
        """
        # Pack rejection
        empty_msg = MYDNSMessage(tx_id=1, msg_type=MSG_QUERY, domain="")
        with self.assertRaises(ValueError):
            empty_msg.pack()

        # Unpack rejection: packet containing 0x00 length prefix
        raw_header = struct.pack(HEADER_FORMAT, 1, MSG_QUERY, TYPE_A, STATUS_SUCCESS, 0)
        corrupt_zero_len = raw_header + b'\x00' + b'x'  # 10 bytes, domain_len=0
        with self.assertRaises(ValueError) as ctx:
            MYDNSMessage.unpack(corrupt_zero_len)
        self.assertIn("Invalid domain length: 0", str(ctx.exception))

    def test_domain_overflow_rejected(self):
        """
        Boundary test: L = 256 domain must be rejected by pack().
        """
        overflow_domain = "a" * 256
        msg = MYDNSMessage(tx_id=1, msg_type=MSG_QUERY, domain=overflow_domain)
        with self.assertRaises(ValueError):
            msg.pack()

    def test_non_ascii_domain_rejected(self):
        """
        Non-ASCII Unicode character injection must raise ValueError during pack().
        """
        non_ascii_domains = [
            "portal.nëduet.local",
            "portal.рф",
            "test\u2603.local",
        ]
        for bad_domain in non_ascii_domains:
            msg = MYDNSMessage(tx_id=1, msg_type=MSG_QUERY, domain=bad_domain)
            with self.assertRaises(ValueError):
                msg.pack()

    def test_truncated_header(self):
        """
        Any packet truncated below the minimum 10-byte threshold must raise ValueError in unpack().
        """
        for length in range(10):
            with self.subTest(length=length):
                truncated_data = b'\x00' * length
                with self.assertRaises(ValueError) as ctx:
                    MYDNSMessage.unpack(truncated_data)
                self.assertIn("Packet truncated below minimum 10-byte threshold", str(ctx.exception))

    def test_truncated_response_missing_ip(self):
        """
        A response packet that carries the domain string but is missing the 4-byte IPv4 trailer
        must be caught and raise ValueError in unpack().
        """
        domain = "portal.neduet.local"  # 19 characters
        # Construct query packet (28 bytes) and mutate message type to MSG_RESPONSE (0x02)
        query = MYDNSMessage(tx_id=1, msg_type=MSG_QUERY, domain=domain)
        query_bytes = bytearray(query.pack())
        query_bytes[2] = MSG_RESPONSE  # Now marked as RESPONSE, but only 28 bytes (needs 32)

        with self.assertRaises(ValueError) as ctx:
            MYDNSMessage.unpack(bytes(query_bytes))
        self.assertIn("missing required 4-byte IPv4 trailer", str(ctx.exception))

    def test_big_endian_wire_layout(self):
        """
        Verifies exact Network Byte Order (Big-Endian) alignment of all header and payload fields.
        """
        tx_id = 0xA1B2
        msg_type = MSG_QUERY
        query_type = TYPE_A
        status = STATUS_SUCCESS
        ttl = 120  # 0x0078
        domain = "portal.neduet.local"  # 19 chars = 0x13

        msg = MYDNSMessage(
            tx_id=tx_id,
            msg_type=msg_type,
            query_type=query_type,
            status=status,
            ttl=ttl,
            domain=domain
        )
        wire = msg.pack()

        # Byte 0-1: TxID 0xA1B2 (Big-Endian)
        self.assertEqual(wire[0:2], b'\xA1\xB2')
        # Byte 2: Message Type 0x01
        self.assertEqual(wire[2], 0x01)
        # Byte 3: Query Type 0x01
        self.assertEqual(wire[3], 0x01)
        # Byte 4: Status 0x00
        self.assertEqual(wire[4], 0x00)
        # Byte 5: Reserved Pad 0x00
        self.assertEqual(wire[5], 0x00)
        # Byte 6-7: TTL 120 -> 0x0078 (Big-Endian)
        self.assertEqual(wire[6:8], b'\x00\x78')
        # Byte 8: Domain Length 19 -> 0x13
        self.assertEqual(wire[8], 19)
        # Byte 9-27: ASCII domain
        self.assertEqual(wire[9:28], b"portal.neduet.local")

    def test_msg_error_pack_unpack(self):
        """
        MSG_ERROR packet serialization:
        Header (8B) + Domain Len (1B) + Domain (11B) = 20 Bytes (no IPv4 trailer).
        """
        msg = MYDNSMessage(
            tx_id=0x9999,
            msg_type=MSG_ERROR,
            query_type=TYPE_A,
            status=STATUS_FORMAT_ERROR,
            ttl=0,
            domain="bad.request"
        )
        wire = msg.pack()
        self.assertEqual(len(wire), 8 + 1 + len("bad.request"))
        self.assertEqual(len(wire), 20)

        unpacked = MYDNSMessage.unpack(wire)
        self.assertEqual(unpacked.tx_id, 0x9999)
        self.assertEqual(unpacked.msg_type, MSG_ERROR)
        self.assertEqual(unpacked.status, STATUS_FORMAT_ERROR)
        self.assertIsNone(unpacked.ip_address)

    def test_constructor_validation(self):
        """Verifies strict parameter bounds checking in __init__."""
        # TxID bounds
        with self.assertRaises(ValueError):
            MYDNSMessage(tx_id=-1, msg_type=MSG_QUERY, domain="test.local")
        with self.assertRaises(ValueError):
            MYDNSMessage(tx_id=0x10000, msg_type=MSG_QUERY, domain="test.local")
        with self.assertRaises(ValueError):
            MYDNSMessage(tx_id=True, msg_type=MSG_QUERY, domain="test.local")

        # Invalid msg_type
        with self.assertRaises(ValueError):
            MYDNSMessage(tx_id=1, msg_type=0x00, domain="test.local")
        with self.assertRaises(ValueError):
            MYDNSMessage(tx_id=1, msg_type=0x04, domain="test.local")

        # Invalid query_type
        with self.assertRaises(ValueError):
            MYDNSMessage(tx_id=1, msg_type=MSG_QUERY, query_type=0x02, domain="test.local")

        # Invalid status
        with self.assertRaises(ValueError):
            MYDNSMessage(tx_id=1, msg_type=MSG_QUERY, status=0x04, domain="test.local")

        # TTL bounds
        with self.assertRaises(ValueError):
            MYDNSMessage(tx_id=1, msg_type=MSG_QUERY, ttl=-1, domain="test.local")
        with self.assertRaises(ValueError):
            MYDNSMessage(tx_id=1, msg_type=MSG_QUERY, ttl=0x10000, domain="test.local")

        # Domain type
        with self.assertRaises(TypeError):
            MYDNSMessage(tx_id=1, msg_type=MSG_QUERY, domain=123)  # type: ignore

    def test_invalid_ip_in_response(self):
        """Verifies invalid IPv4 formats are rejected during pack()."""
        invalid_ips = [
            "256.0.0.1",
            "10.0.1",
            "not-an-ip",
            "1.2.3.4.5",
            "-1.0.0.1",
        ]
        for bad_ip in invalid_ips:
            msg = MYDNSMessage(
                tx_id=1,
                msg_type=MSG_RESPONSE,
                domain="portal.neduet.local",
                ip_address=bad_ip
            )
            with self.assertRaises(ValueError):
                msg.pack()

    def test_diagnostics_and_representations(self):
        """Verifies to_dict(), hex_dump(), format_hex(), and __repr__()."""
        msg = MYDNSMessage(
            tx_id=0xA1B2,
            msg_type=MSG_RESPONSE,
            query_type=TYPE_A,
            status=STATUS_SUCCESS,
            ttl=120,
            domain="portal.neduet.local",
            ip_address="10.0.1.5"
        )

        d = msg.to_dict()
        self.assertEqual(d["tx_id"], 0xA1B2)
        self.assertEqual(d["tx_id_hex"], "0xa1b2")
        self.assertEqual(d["msg_type_name"], "RESPONSE")
        self.assertEqual(d["query_type_name"], "TYPE_A")
        self.assertEqual(d["status_name"], "SUCCESS")
        self.assertEqual(d["ttl"], 120)
        self.assertEqual(d["domain"], "portal.neduet.local")
        self.assertEqual(d["ip_address"], "10.0.1.5")

        rep = repr(msg)
        self.assertIn("0xa1b2", rep)
        self.assertIn("RESPONSE", rep)
        self.assertIn("portal.neduet.local", rep)
        self.assertIn("10.0.1.5", rep)

        hex_str = msg.hex_dump()
        self.assertTrue(hex_str.startswith("A1 B2 02 01 00 00 00 78"))

        formatted_hex = msg.hex_dump(formatted=True)
        self.assertIn("portal.", formatted_hex)
        self.assertIn("neduet.local", formatted_hex)
        self.assertIn("0000", formatted_hex)

    def test_unpack_type_and_value_guards(self):
        """Verifies TypeError on non-bytes and ValueError on malformed headers."""
        with self.assertRaises(TypeError):
            MYDNSMessage.unpack("string instead of bytes")  # type: ignore

        # Mutate query with invalid message type 0x99
        query = MYDNSMessage(tx_id=1, msg_type=MSG_QUERY, domain="portal.neduet.local")
        bad_bytes = bytearray(query.pack())
        bad_bytes[2] = 0x99
        with self.assertRaises(ValueError) as ctx:
            MYDNSMessage.unpack(bytes(bad_bytes))
        self.assertIn("Invalid Message Type in packet", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
