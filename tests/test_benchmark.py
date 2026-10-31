"""
Unit Tests for Benchmark Suite & Statistical Engine
Course: CS-327 Computer Communication Networks (Fall 2026)
Track: Option B — Mini DNS Service (MYDNS/1.0)
Lead Client Engineer: Asadullah Zafar (CS-24082)

Verifies statistical calculations (mean, std_dev, min, max),
plot generation, and benchmark trial execution over real UDP sockets.
"""

import os
import sys
import unittest
import socket

# Add src/ and root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from tests.test_client import RealUDPServerThread
from tests.benchmark_runner import (
    calculate_statistics,
    generate_benchmark_plot,
    run_benchmark_trials,
)
from protocol import MYDNSMessage, MSG_RESPONSE, TYPE_A, STATUS_SUCCESS


class TestBenchmarkEngine(unittest.TestCase):
    """Verifies statistical profiling, plotting, and trial execution."""

    def test_statistics_calculation(self):
        """Verifies accurate sample mean and sample standard deviation computation."""
        # Test values: [2.0, 4.0, 4.0, 4.0, 5.0, 5.0, 7.0, 9.0]
        # Sum = 40, N = 8, Mean = 5.0
        # Variance = ((9 + 1 + 1 + 1 + 0 + 0 + 4 + 16) / 7) = 32 / 7 = 4.5714
        # Std Dev = sqrt(4.5714) = 2.138
        rtts = [2.0, 4.0, 4.0, 4.0, 5.0, 5.0, 7.0, 9.0]
        stats = calculate_statistics(rtts)

        self.assertEqual(stats["n"], 8)
        self.assertAlmostEqual(stats["mean"], 5.0, places=4)
        self.assertAlmostEqual(stats["std_dev"], 2.138089935299395, places=4)
        self.assertEqual(stats["min"], 2.0)
        self.assertEqual(stats["max"], 9.0)
        self.assertAlmostEqual(stats["qps"], 200.0, places=2)
        self.assertAlmostEqual(stats["throughput_kbps"], 11.71875, places=2)
        self.assertEqual(stats["bytes_per_query"], 60.0)

    def test_statistics_edge_cases(self):
        """Verifies single-element and empty lists handled safely."""
        empty_stats = calculate_statistics([])
        self.assertEqual(empty_stats["n"], 0)
        self.assertEqual(empty_stats["mean"], 0.0)
        self.assertEqual(empty_stats["std_dev"], 0.0)

        single_stats = calculate_statistics([5.5])
        self.assertEqual(single_stats["n"], 1)
        self.assertEqual(single_stats["mean"], 5.5)
        self.assertEqual(single_stats["std_dev"], 0.0)

    def test_plot_generation(self):
        """Verifies Matplotlib generates and saves a valid PNG file."""
        miss_rtts = [5.1, 4.8, 5.2, 4.9, 5.0]
        hit_rtts = [0.9, 0.8, 1.0, 0.9, 0.8]
        miss_stats = calculate_statistics(miss_rtts)
        hit_stats = calculate_statistics(hit_rtts)

        test_plot_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "test_plot_output.png"))

        try:
            generate_benchmark_plot(miss_rtts, hit_rtts, miss_stats, hit_stats, test_plot_path)
            self.assertTrue(os.path.exists(test_plot_path))
            self.assertGreater(os.path.getsize(test_plot_path), 50000)  # > 50KB image
        finally:
            if os.path.exists(test_plot_path):
                os.remove(test_plot_path)

    def test_real_udp_benchmark_execution(self):
        """Verifies multi-trial benchmark execution over real native UDP sockets."""
        def benchmark_responder(data: bytes, addr: tuple, server_sock: socket.socket):
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

        server = RealUDPServerThread(handler=benchmark_responder)
        server.start()
        server.ready_event.wait(timeout=1.0)

        try:
            miss_rtts, hit_rtts = run_benchmark_trials(
                resolver_ip=server.host,
                resolver_port=server.port,
                domain="portal.neduet.local",
                trials=3,
                timeout=1.0
            )

            self.assertEqual(len(miss_rtts), 3)
            self.assertEqual(len(hit_rtts), 3)
            for rtt in miss_rtts + hit_rtts:
                self.assertGreater(rtt, 0.0)
        finally:
            server.stop()


if __name__ == "__main__":
    unittest.main()

