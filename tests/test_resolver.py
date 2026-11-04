import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from resolver import DNSCache


class FakeClock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


class TestDNSCache(unittest.TestCase):
    def setUp(self):
        self.clock = FakeClock()
        self.cache = DNSCache(clock=self.clock)

    def test_miss_on_empty_cache(self):
        self.assertIsNone(self.cache.get("portal.neduet.local"))

    def test_hit_returns_value_and_remaining_ttl(self):
        self.cache.put("portal.neduet.local", "10.0.0.5", 120)
        self.assertEqual(self.cache.get("portal.neduet.local"), ("10.0.0.5", 120))

    def test_remaining_ttl_counts_down(self):
        self.cache.put("portal.neduet.local", "10.0.0.5", 120)
        self.clock.advance(30)
        self.assertEqual(self.cache.get("portal.neduet.local"), ("10.0.0.5", 90))

    def test_entry_expires_at_ttl(self):
        self.cache.put("portal.neduet.local", "10.0.0.5", 60)
        self.clock.advance(60)
        self.assertIsNone(self.cache.get("portal.neduet.local"))

    def test_expired_entry_is_removed(self):
        self.cache.put("a.neduet.local", "1.1.1.1", 10)
        self.clock.advance(11)
        self.cache.get("a.neduet.local")
        self.assertEqual(len(self.cache), 0)

    def test_keys_are_case_insensitive(self):
        self.cache.put("Portal.NEDUET.local", "10.0.0.5", 120)
        self.assertIsNotNone(self.cache.get("portal.neduet.local"))
        self.assertIsNotNone(self.cache.get("PORTAL.neduet.LOCAL"))

    def test_zero_or_negative_ttl_not_cached(self):
        self.cache.put("a.neduet.local", "1.1.1.1", 0)
        self.cache.put("b.neduet.local", "2.2.2.2", -5)
        self.assertEqual(len(self.cache), 0)

    def test_put_overwrites_and_resets_ttl(self):
        self.cache.put("a.neduet.local", "1.1.1.1", 10)
        self.clock.advance(8)
        self.cache.put("a.neduet.local", "2.2.2.2", 10)
        self.assertEqual(self.cache.get("a.neduet.local"), ("2.2.2.2", 10))

    def test_purge_expired_counts_removed(self):
        self.cache.put("a.neduet.local", "1.1.1.1", 5)
        self.cache.put("b.neduet.local", "2.2.2.2", 100)
        self.clock.advance(10)
        self.assertEqual(self.cache.purge_expired(), 1)
        self.assertEqual(len(self.cache), 1)

    def test_clear(self):
        self.cache.put("a.neduet.local", "1.1.1.1", 50)
        self.cache.clear()
        self.assertEqual(len(self.cache), 0)


if __name__ == "__main__":
    unittest.main()