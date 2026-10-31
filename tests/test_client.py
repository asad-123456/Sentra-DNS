"""
Real UDP Socket Verification Suite for MYDNS/1.0 Client Engine
Course: CS-327 Computer Communication Networks (Fall 2026)
Track: Option B — Mini DNS Service (MYDNS/1.0)
Lead Client Engineer: Asadullah Zafar (CS-24082)

Verifies client query execution, stop-and-wait timeout retransmission,
asynchronous Transaction ID filtering, and status code handling over
real native operating system UDP sockets with ZERO mock frameworks.
"""

import os
import sys
import time
import socket
import threading
import unittest
from typing import Optional, Callable

# Add src/ and root to sys.path
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
)
from client import query_domain


class RealUDPServerThread(threading.Thread):
    """
    A lightweight, real UDP server running on loopback (127.0.0.1) on an OS-allocated
    ephemeral port. Used to verify client network interactions with actual datagrams.
    """

    def __init__(self, handler: Optional[Callable[[bytes, tuple, socket.socket], None]] = None) -> None:
        super().__init__(daemon=True)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # Binding to port 0 instructs the operating system to allocate an ephemeral free port
        self.sock.bind(('127.0.0.1', 0))
        self.host, self.port = self.sock.getsockname()
        self.handler = handler
        self.running = True
        self.received_packets = []
        self.ready_event = threading.Event()

    def run(self) -> None:
        self.sock.settimeout(0.1)
        self.ready_event.set()
        while self.running:
            try:
                data, addr = self.sock.recvfrom(512)
                self.received_packets.append((data, addr))
                if self.handler:
                    self.handler(data, addr, self.sock)
            except socket.timeout:
                continue
            except OSError:
                break

    def stop(self) -> None:
        self.running = False
        try:
            self.sock.close()
        except OSError:
            pass


class TestMYDNSClientRealSocket(unittest.TestCase):
    """Verifies client engine behavior over real OS UDP sockets."""

    def test_real_socket_query_success(self):
        """Verifies standard query/response resolution over a real UDP socket."""
        domain = "portal.neduet.local"
        expected_ip = "10.0.1.5"
        expected_ttl = 120

        def echo_handler(data: bytes, addr: tuple, server_sock: socket.socket):
            query = MYDNSMessage.unpack(data)
            resp = MYDNSMessage(
                tx_id=query.tx_id,
                msg_type=MSG_RESPONSE,
                query_type=TYPE_A,
                status=STATUS_SUCCESS,
                ttl=expected_ttl,
                domain=query.domain,
                ip_address=expected_ip
            )
            server_sock.sendto(resp.pack(), addr)

        server = RealUDPServerThread(handler=echo_handler)
        server.start()
        server.ready_event.wait(timeout=1.0)

        try:
            response, rtt_ms = query_domain(
                resolver_ip=server.host,
                resolver_port=server.port,
                domain=domain,
                timeout=1.0,
                max_retries=2
            )

            self.assertEqual(len(server.received_packets), 1)
            self.assertEqual(response.status, STATUS_SUCCESS)
            self.assertEqual(response.ip_address, expected_ip)
            self.assertEqual(response.ttl, expected_ttl)
            self.assertEqual(response.domain, domain)
            self.assertGreater(rtt_ms, 0.0)
            self.assertLess(rtt_ms, 1000.0)
        finally:
            server.stop()

    def test_real_socket_stop_and_wait_retry(self):
        """
        Verifies Stop-and-Wait ARQ retransmission when packets are dropped:
        Server deliberately ignores Attempt 1 and replies to Attempt 2.
        """
        domain = "portal.neduet.local"
        attempts_seen = []

        def drop_first_handler(data: bytes, addr: tuple, server_sock: socket.socket):
            attempts_seen.append(data)
            if len(attempts_seen) == 1:
                # Deliberately drop the first packet to simulate link packet loss
                return

            # Respond to the retransmitted datagram
            query = MYDNSMessage.unpack(data)
            resp = MYDNSMessage(
                tx_id=query.tx_id,
                msg_type=MSG_RESPONSE,
                query_type=TYPE_A,
                status=STATUS_SUCCESS,
                ttl=60,
                domain=query.domain,
                ip_address="10.0.1.5"
            )
            server_sock.sendto(resp.pack(), addr)

        server = RealUDPServerThread(handler=drop_first_handler)
        server.start()
        server.ready_event.wait(timeout=1.0)

        try:
            # Use small 0.2s timeout so the test runs quickly
            response, rtt_ms = query_domain(
                resolver_ip=server.host,
                resolver_port=server.port,
                domain=domain,
                timeout=0.2,
                max_retries=3
            )

            # Must have received 2 attempts across the wire
            self.assertEqual(len(attempts_seen), 2)
            self.assertEqual(response.status, STATUS_SUCCESS)
            self.assertEqual(response.ip_address, "10.0.1.5")
            self.assertGreater(rtt_ms, 0.0)
        finally:
            server.stop()

    def test_real_socket_timeout_exhaustion(self):
        """Verifies TimeoutError is raised when all Stop-and-Wait attempts expire."""
        # Handler that drops every packet
        server = RealUDPServerThread(handler=lambda data, addr, sock: None)
        server.start()
        server.ready_event.wait(timeout=1.0)

        try:
            with self.assertRaises(TimeoutError) as ctx:
                query_domain(
                    resolver_ip=server.host,
                    resolver_port=server.port,
                    domain="portal.neduet.local",
                    timeout=0.1,
                    max_retries=3
                )
            self.assertIn("failed after 3 attempts", str(ctx.exception))
            # Must have transmitted exactly 3 datagrams
            self.assertEqual(len(server.received_packets), 3)
        finally:
            server.stop()

    def test_real_socket_tx_id_filtering(self):
        """
        Verifies asynchronous Transaction ID matching:
        Server sends a packet with a mismatched TxID first, followed by the correct packet.
        The client must ignore the wrong TxID and accept the matching one.
        """
        domain = "portal.neduet.local"

        def mismatched_then_correct_handler(data: bytes, addr: tuple, server_sock: socket.socket):
            query = MYDNSMessage.unpack(data)
            # 1. Send stale packet with mismatched TxID
            wrong_tx_id = (query.tx_id + 1) % 0xFFFF
            stale_resp = MYDNSMessage(
                tx_id=wrong_tx_id,
                msg_type=MSG_RESPONSE,
                query_type=TYPE_A,
                status=STATUS_SUCCESS,
                ttl=10,
                domain=query.domain,
                ip_address="192.168.99.99"
            )
            server_sock.sendto(stale_resp.pack(), addr)

            # 2. Send correct matching packet
            correct_resp = MYDNSMessage(
                tx_id=query.tx_id,
                msg_type=MSG_RESPONSE,
                query_type=TYPE_A,
                status=STATUS_SUCCESS,
                ttl=120,
                domain=query.domain,
                ip_address="10.0.1.5"
            )
            server_sock.sendto(correct_resp.pack(), addr)

        server = RealUDPServerThread(handler=mismatched_then_correct_handler)
        server.start()
        server.ready_event.wait(timeout=1.0)

        try:
            response, rtt_ms = query_domain(
                resolver_ip=server.host,
                resolver_port=server.port,
                domain=domain,
                timeout=1.0,
                max_retries=2
            )

            # Client must have accepted the correct IP and TxID, ignoring the stale one
            self.assertEqual(response.ip_address, "10.0.1.5")
            self.assertEqual(response.ttl, 120)
        finally:
            server.stop()

    def test_real_socket_nxdomain(self):
        """Verifies proper parsing of STATUS_NXDOMAIN responses over real UDP."""
        def nxdomain_handler(data: bytes, addr: tuple, server_sock: socket.socket):
            query = MYDNSMessage.unpack(data)
            resp = MYDNSMessage(
                tx_id=query.tx_id,
                msg_type=MSG_RESPONSE,
                query_type=TYPE_A,
                status=STATUS_NXDOMAIN,
                ttl=0,
                domain=query.domain,
                ip_address="0.0.0.0"
            )
            server_sock.sendto(resp.pack(), addr)

        server = RealUDPServerThread(handler=nxdomain_handler)
        server.start()
        server.ready_event.wait(timeout=1.0)

        try:
            response, _ = query_domain(
                resolver_ip=server.host,
                resolver_port=server.port,
                domain="unknown.local",
                timeout=1.0,
                max_retries=1
            )
            self.assertEqual(response.status, STATUS_NXDOMAIN)
            self.assertEqual(response.ip_address, "0.0.0.0")
            self.assertEqual(response.ttl, 0)
        finally:
            server.stop()

    def test_real_socket_server_failure(self):
        """Verifies proper parsing of STATUS_SERVER_FAILURE responses over real UDP."""
        def servfail_handler(data: bytes, addr: tuple, server_sock: socket.socket):
            query = MYDNSMessage.unpack(data)
            resp = MYDNSMessage(
                tx_id=query.tx_id,
                msg_type=MSG_RESPONSE,
                query_type=TYPE_A,
                status=STATUS_SERVER_FAILURE,
                ttl=0,
                domain=query.domain,
                ip_address="0.0.0.0"
            )
            server_sock.sendto(resp.pack(), addr)

        server = RealUDPServerThread(handler=servfail_handler)
        server.start()
        server.ready_event.wait(timeout=1.0)

        try:
            response, _ = query_domain(
                resolver_ip=server.host,
                resolver_port=server.port,
                domain="unreachable.local",
                timeout=1.0,
                max_retries=1
            )
            self.assertEqual(response.status, STATUS_SERVER_FAILURE)
            self.assertEqual(response.ip_address, "0.0.0.0")
            self.assertEqual(response.ttl, 0)
        finally:
            server.stop()

    def test_real_socket_corrupt_datagram_ignored(self):
        """
        Verifies that non-MYDNS / malformed garbage datagrams arriving on the client
        ephemeral port are silently discarded, and the valid response is still received.
        """
        domain = "portal.neduet.local"

        def noise_then_valid_handler(data: bytes, addr: tuple, server_sock: socket.socket):
            # 1. Send garbage raw bytes that will fail unpack()
            server_sock.sendto(b"\x00\x01\xFFGARBAGE_PAYLOAD\x99", addr)

            # 2. Send the legitimate response
            query = MYDNSMessage.unpack(data)
            resp = MYDNSMessage(
                tx_id=query.tx_id,
                msg_type=MSG_RESPONSE,
                query_type=TYPE_A,
                status=STATUS_SUCCESS,
                ttl=120,
                domain=query.domain,
                ip_address="10.0.1.5"
            )
            server_sock.sendto(resp.pack(), addr)

        server = RealUDPServerThread(handler=noise_then_valid_handler)
        server.start()
        server.ready_event.wait(timeout=1.0)

        try:
            response, rtt_ms = query_domain(
                resolver_ip=server.host,
                resolver_port=server.port,
                domain=domain,
                timeout=1.0,
                max_retries=1
            )
            self.assertEqual(response.status, STATUS_SUCCESS)
            self.assertEqual(response.ip_address, "10.0.1.5")
            self.assertGreater(rtt_ms, 0.0)
        finally:
            server.stop()

    def test_real_socket_format_error_fast_fail(self):
        """
        Verifies that MSG_ERROR with matching TxID is returned immediately
        (fail-fast) without triggering unnecessary Stop-and-Wait retries.
        """
        attempts_seen = []

        def error_handler(data: bytes, addr: tuple, server_sock: socket.socket):
            attempts_seen.append(data)
            query = MYDNSMessage.unpack(data)
            # Send MSG_ERROR with STATUS_FORMAT_ERROR and matching TxID
            err_resp = MYDNSMessage(
                tx_id=query.tx_id,
                msg_type=MSG_ERROR,
                query_type=TYPE_A,
                status=STATUS_FORMAT_ERROR,
                ttl=0,
                domain=query.domain
            )
            server_sock.sendto(err_resp.pack(), addr)

        server = RealUDPServerThread(handler=error_handler)
        server.start()
        server.ready_event.wait(timeout=1.0)

        try:
            response, _ = query_domain(
                resolver_ip=server.host,
                resolver_port=server.port,
                domain="bad.request",
                timeout=0.3,
                max_retries=3
            )
            # Client must have received the error immediately on attempt 1 with zero retries
            self.assertEqual(len(attempts_seen), 1)
            self.assertEqual(response.msg_type, MSG_ERROR)
            self.assertEqual(response.status, STATUS_FORMAT_ERROR)
        finally:
            server.stop()


if __name__ == "__main__":
    unittest.main()
