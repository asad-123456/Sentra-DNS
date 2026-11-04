import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from protocol import (
    MSG_ERROR, MSG_QUERY, MSG_RESPONSE, STATUS_FORMAT_ERROR, STATUS_SUCCESS,
    TYPE_A, MYDNSMessage,
)
from resolver import BAD_DOMAIN, DNSCache, build_error_reply, validate_client_datagram


def good_query(domain="portal.neduet.local", tx_id=0x0065):
    return MYDNSMessage(tx_id, MSG_QUERY, TYPE_A, STATUS_SUCCESS, 0, domain).pack()


class FakeClock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


class TestValidation(unittest.TestCase):
    def assert_error_reply(self, data, expected_tx):
        query, reply = validate_client_datagram(data)
        self.assertIsNone(query)
        err = MYDNSMessage.unpack(reply)
        self.assertEqual(err.msg_type, MSG_ERROR)
        self.assertEqual(err.status, STATUS_FORMAT_ERROR)
        self.assertEqual(err.domain, BAD_DOMAIN)
        self.assertEqual(err.ttl, 0)
        self.assertEqual(err.tx_id, expected_tx)

    def test_valid_query_accepted(self):
        query, reply = validate_client_datagram(good_query())
        self.assertIsNone(reply)
        self.assertEqual(query.tx_id, 101)
        self.assertEqual(query.domain, "portal.neduet.local")

    def test_valid_query_keeps_domain_case(self):
        query, reply = validate_client_datagram(good_query("Portal.NEDUET.local"))
        self.assertIsNone(reply)
        self.assertEqual(query.domain, "Portal.NEDUET.local")

    def test_empty_datagram(self):
        self.assert_error_reply(b"", 0)

    def test_one_byte_datagram(self):
        self.assert_error_reply(b"\x12", 0)

    def test_short_datagrams_copy_txid(self):
        self.assert_error_reply(b"\x00\x65", 101)
        self.assert_error_reply(b"\x12\x34\xff\xff\xff", 0x1234)

    def test_truncated_after_header(self):
        self.assert_error_reply(good_query()[:9], 101)

    def test_truncated_domain(self):
        self.assert_error_reply(good_query()[:20], 101)

    def test_bad_msg_type(self):
        data = bytearray(good_query())
        data[2] = 0x09
        self.assert_error_reply(bytes(data), 101)

    def test_non_type_a_query(self):
        data = bytearray(good_query())
        data[3] = 0x02
        self.assert_error_reply(bytes(data), 101)

    def test_bad_status(self):
        data = bytearray(good_query())
        data[4] = 0x7F
        self.assert_error_reply(bytes(data), 101)

    def test_response_from_client_rejected(self):
        resp = MYDNSMessage(
            101, MSG_RESPONSE, TYPE_A, STATUS_SUCCESS, 120,
            "portal.neduet.local", "10.0.1.5",
        ).pack()
        self.assert_error_reply(resp, 101)

    def test_error_from_client_rejected(self):
        err = MYDNSMessage(
            101, MSG_ERROR, TYPE_A, STATUS_FORMAT_ERROR, 0, "portal.neduet.local"
        ).pack()
        self.assert_error_reply(err, 101)

    def test_trailing_bytes_rejected(self):
        self.assert_error_reply(good_query() + b"\x00", 101)

    def test_zero_domain_length(self):
        data = bytearray(good_query())
        data[8] = 0
        self.assert_error_reply(bytes(data), 101)

    def test_non_ascii_domain(self):
        data = bytearray(good_query())
        data[9] = 0xFF
        self.assert_error_reply(bytes(data), 101)

    def test_non_bytes_input(self):
        for bad in (None, "not bytes", 12345):
            self.assert_error_reply(bad, 0)

    def test_error_reply_shape(self):
        reply = build_error_reply(good_query())
        self.assertEqual(len(reply), 20)  # 8 header + 1 len + 11 "bad.request"
        self.assertEqual(MYDNSMessage.unpack(reply).tx_id, 101)


class TestCacheWithZoneNames(unittest.TestCase):
    """Uses the names and TTLs Abdur's authoritative server serves."""

    def setUp(self):
        self.clock = FakeClock()
        self.cache = DNSCache(clock=self.clock)

    def test_zone_ttls(self):
        self.cache.put("portal.neduet.local", "10.0.1.5", 120)
        self.cache.put("short.neduet.local", "10.0.1.6", 10)
        self.cache.put("long.neduet.local", "10.0.1.7", 3600)

        self.clock.advance(10)
        self.assertIsNone(self.cache.get("short.neduet.local"))
        self.assertEqual(self.cache.get("portal.neduet.local"), ("10.0.1.5", 110))
        self.assertEqual(self.cache.get("long.neduet.local"), ("10.0.1.7", 3590))

        self.clock.advance(3000)
        self.assertIsNone(self.cache.get("portal.neduet.local"))
        self.assertEqual(self.cache.get("long.neduet.local"), ("10.0.1.7", 590))

    def test_nxdomain_ttl_zero_not_cached(self):
        self.cache.put("nope.neduet.local", "0.0.0.0", 0)
        self.assertIsNone(self.cache.get("nope.neduet.local"))
        self.assertEqual(len(self.cache), 0)


if __name__ == "__main__":
    unittest.main()