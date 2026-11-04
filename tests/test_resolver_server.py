import os
import socket
import sys
import threading
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from protocol import (
    MSG_ERROR, MSG_QUERY, MSG_RESPONSE, STATUS_FORMAT_ERROR, STATUS_NXDOMAIN,
    STATUS_SERVER_FAILURE, STATUS_SUCCESS, TYPE_A, MYDNSMessage,
)
from resolver import DNSCache, handle_datagram, serve


def query(domain="portal.neduet.local", tx_id=101):
    return MYDNSMessage(tx_id, MSG_QUERY, TYPE_A, STATUS_SUCCESS, 0, domain).pack()


def auth_reply(q_bytes, ip="10.0.1.5", ttl=120, status=STATUS_SUCCESS):
    q = MYDNSMessage.unpack(q_bytes)
    return MYDNSMessage(q.tx_id, MSG_RESPONSE, TYPE_A, status, ttl, q.domain, ip).pack()


class FakeClock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


class FakeUpstream:
    def __init__(self, fn):
        self.fn = fn
        self.calls = []

    def __call__(self, data):
        self.calls.append(data)
        return self.fn(data)


class TestHandleDatagram(unittest.TestCase):
    def setUp(self):
        self.clock = FakeClock()
        self.cache = DNSCache(clock=self.clock)

    def run_q(self, data, upstream):
        reply, outcome = handle_datagram(data, self.cache, upstream)
        return MYDNSMessage.unpack(reply), outcome

    def test_miss_forwards_original_bytes_and_relays(self):
        up = FakeUpstream(auth_reply)
        data = query()
        msg, outcome = self.run_q(data, up)
        self.assertEqual(outcome, "MISS")
        self.assertEqual(up.calls, [data])
        self.assertEqual((msg.ip_address, msg.ttl, msg.status), ("10.0.1.5", 120, STATUS_SUCCESS))

    def test_second_query_is_cache_hit(self):
        up = FakeUpstream(auth_reply)
        self.run_q(query(), up)
        msg, outcome = self.run_q(query(), up)
        self.assertEqual(outcome, "HIT")
        self.assertEqual(len(up.calls), 1)
        self.assertEqual(msg.ip_address, "10.0.1.5")

    def test_hit_uses_new_txid_and_client_domain_case(self):
        up = FakeUpstream(auth_reply)
        self.run_q(query("portal.neduet.local", 101), up)
        msg, outcome = self.run_q(query("Portal.NEDUET.local", 202), up)
        self.assertEqual(outcome, "HIT")
        self.assertEqual(msg.tx_id, 202)
        self.assertEqual(msg.domain, "Portal.NEDUET.local")

    def test_hit_ttl_counts_down(self):
        up = FakeUpstream(auth_reply)
        self.run_q(query(), up)
        self.clock.advance(30)
        msg, outcome = self.run_q(query(), up)
        self.assertEqual((outcome, msg.ttl), ("HIT", 90))

    def test_nxdomain_relayed_not_cached(self):
        up = FakeUpstream(lambda d: auth_reply(d, "0.0.0.0", 0, STATUS_NXDOMAIN))
        msg, outcome = self.run_q(query("nope.neduet.local"), up)
        self.assertEqual(msg.status, STATUS_NXDOMAIN)
        self.assertEqual(len(self.cache), 0)
        self.run_q(query("nope.neduet.local"), up)
        self.assertEqual(len(up.calls), 2)

    def test_upstream_timeout_gives_server_failure(self):
        up = FakeUpstream(lambda d: None)
        msg, outcome = self.run_q(query(), up)
        self.assertEqual(outcome, "SERVER_FAILURE")
        self.assertEqual(msg.msg_type, MSG_RESPONSE)
        self.assertEqual(msg.status, STATUS_SERVER_FAILURE)
        self.assertEqual(msg.tx_id, 101)
        self.assertEqual(len(self.cache), 0)

    def test_upstream_wrong_txid_gives_server_failure(self):
        up = FakeUpstream(lambda d: auth_reply(query(tx_id=999)))
        msg, outcome = self.run_q(query(), up)
        self.assertEqual(outcome, "SERVER_FAILURE")
        self.assertEqual(len(self.cache), 0)

    def test_upstream_garbage_gives_server_failure(self):
        up = FakeUpstream(lambda d: b"\x00\x01garbage")
        msg, outcome = self.run_q(query(), up)
        self.assertEqual(outcome, "SERVER_FAILURE")
        self.assertEqual(len(self.cache), 0)

    def test_upstream_error_relayed_not_cached(self):
        err = lambda d: MYDNSMessage(
            101, MSG_ERROR, TYPE_A, STATUS_FORMAT_ERROR, 0, "bad.request").pack()
        up = FakeUpstream(err)
        msg, outcome = self.run_q(query(), up)
        self.assertEqual(msg.msg_type, MSG_ERROR)
        self.assertEqual(len(self.cache), 0)

    def test_malformed_client_never_forwarded(self):
        up = FakeUpstream(auth_reply)
        msg, outcome = self.run_q(b"\x00\x65garbage", up)
        self.assertEqual(outcome, "FORMAT_ERROR")
        self.assertEqual(msg.msg_type, MSG_ERROR)
        self.assertEqual(up.calls, [])

    def test_failure_then_recovery(self):
        state = {"up": False}
        up = FakeUpstream(lambda d: auth_reply(d) if state["up"] else None)
        self.run_q(query(), up)
        state["up"] = True
        msg, outcome = self.run_q(query(), up)
        self.assertEqual(outcome, "MISS")


class FakeAuth(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(("127.0.0.1", 0))
        self.sock.settimeout(0.2)
        self.port = self.sock.getsockname()[1]
        self.stop = threading.Event()
        self.count = 0

    def run(self):
        while not self.stop.is_set():
            try:
                data, addr = self.sock.recvfrom(512)
            except OSError:
                continue
            self.count += 1
            if MYDNSMessage.unpack(data).domain.lower() == "portal.neduet.local":
                resp = auth_reply(data)
            else:
                resp = auth_reply(data, "0.0.0.0", 0, STATUS_NXDOMAIN)
            self.sock.sendto(resp, addr)


class TestEndToEnd(unittest.TestCase):
    def setUp(self):
        self.auth = FakeAuth()
        self.auth.start()
        self.stop = threading.Event()
        started = threading.Event()
        self.addr = {}

        def on_ready(addr):
            self.addr["a"] = addr
            started.set()

        self.thread = threading.Thread(
            target=serve,
            kwargs=dict(listen_host="127.0.0.1", listen_port=0,
                        upstream_host="127.0.0.1", upstream_port=self.auth.port,
                        timeout=1.0, stop_event=self.stop, on_ready=on_ready),
            daemon=True)
        self.thread.start()
        self.assertTrue(started.wait(3))
        self.client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.client.settimeout(2.0)
        self.addCleanup(self.cleanup)

    def cleanup(self):
        self.stop.set()
        self.auth.stop.set()
        self.thread.join(3)
        self.auth.join(3)
        self.auth.sock.close()
        self.client.close()

    def ask(self, data):
        self.client.sendto(data, self.addr["a"])
        return MYDNSMessage.unpack(self.client.recvfrom(512)[0])

    def test_end_to_end_miss_then_hit(self):
        first = self.ask(query(tx_id=101))
        self.assertEqual((first.ip_address, first.ttl), ("10.0.1.5", 120))
        second = self.ask(query(tx_id=102))
        self.assertEqual(second.tx_id, 102)
        self.assertEqual(second.ip_address, "10.0.1.5")
        self.assertTrue(118 <= second.ttl <= 120)
        self.assertEqual(self.auth.count, 1)

    def test_end_to_end_nxdomain(self):
        msg = self.ask(query("nope.neduet.local"))
        self.assertEqual(msg.status, STATUS_NXDOMAIN)
        self.assertEqual(msg.ttl, 0)

    def test_end_to_end_malformed_gets_error(self):
        msg = self.ask(b"\x12\x34\xff\xff\xff\xff\xff\xff\xff\xff")
        self.assertEqual(msg.msg_type, MSG_ERROR)
        self.assertEqual(msg.tx_id, 0x1234)
        self.assertEqual(self.auth.count, 0)


if __name__ == "__main__":
    unittest.main()