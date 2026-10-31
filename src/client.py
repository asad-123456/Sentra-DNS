"""
MYDNS/1.0 Client Engine & Query CLI
Course: CS-327 Computer Communication Networks (Fall 2026)
Track: Option B — Mini DNS Service (MYDNS/1.0)
Lead Client Engineer: Asadullah Zafar (CS-24082)
Collaborators: Atta-Ur-Rehman (CS-24092), Abdur Rahman (CS-24098)
Institution: Department of Computer & Information Systems Engineering,
             NED University of Engineering & Technology

This module implements Host 1 (Client) for the MYDNS/1.0 architecture.
It manages native UDP socket communication, microsecond RTT measurement,
and Stop-and-Wait timeout and retransmissions.
"""

from typing import Tuple, Optional
import argparse
import random
import socket
import struct
import sys
import time
import os

# Add src/ to sys.path if running as standalone script
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

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
    STATUS_NAMES,
)


def query_domain(
    resolver_ip: str,
    resolver_port: int,
    domain: str,
    timeout: float = 1.5,
    max_retries: int = 3,
    sock: Optional[socket.socket] = None
) -> Tuple[MYDNSMessage, float]:
    """
    Sends a MYDNS/1.0 query datagram to the resolver and awaits a matching response.
    Implements application-layer Stop-and-Wait ARQ with timeout retransmissions.

    Args:
        resolver_ip: Target resolver IPv4 address (e.g. '192.168.1.11' or '127.0.0.1').
        resolver_port: Target resolver UDP port (typically 53000).
        domain: Fully Qualified Domain Name to resolve (e.g. 'portal.neduet.local').
        timeout: Stop-and-wait timeout in seconds per attempt (default 1.5s).
        max_retries: Maximum number of transmission attempts (default 3).
        sock: Optional pre-existing socket (used primarily for unit testing).

    Returns:
        Tuple[MYDNSMessage, float]: The unpacked response message and measured RTT in ms.

    Raises:
        TimeoutError: If all retry attempts expire without a valid matching response.
        ValueError: If domain format is invalid or message packing fails.
    """
    owns_socket = sock is None
    if sock is None:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    sock.settimeout(timeout)

    # Generate a random 16-bit Transaction ID
    tx_id = random.randint(1, 0xFFFF)
    query = MYDNSMessage(
        tx_id=tx_id,
        msg_type=MSG_QUERY,
        query_type=TYPE_A,
        domain=domain
    )
    wire_bytes = query.pack()

    try:
        for attempt in range(1, max_retries + 1):
            try:
                # Start microsecond-precision hardware stopwatch
                t_start = time.perf_counter()
                attempt_deadline = t_start + timeout
                sock.sendto(wire_bytes, (resolver_ip, resolver_port))

                # Loop to handle possible asynchronous/stale or malformed background packets
                while True:
                    time_left = attempt_deadline - time.perf_counter()
                    if time_left <= 0:
                        raise socket.timeout()

                    sock.settimeout(time_left)
                    data, _ = sock.recvfrom(512)
                    t_end = time.perf_counter()
                    rtt_ms = (t_end - t_start) * 1000.0

                    try:
                        response = MYDNSMessage.unpack(data)
                    except (ValueError, TypeError, struct.error):
                        # Silently discard non-MYDNS or corrupt background datagrams
                        continue

                    # Verify Transaction ID matching
                    if response.tx_id == tx_id:
                        # Fail-fast on matching TxID (including MSG_ERROR / STATUS_FORMAT_ERROR without retrying)
                        return response, rtt_ms
                    # If mismatched, ignore stale datagram and continue waiting within attempt window

            except (socket.timeout, TimeoutError):
                if attempt < max_retries:
                    print(
                        f"[CLIENT WARN] Attempt {attempt}/{max_retries} timed out after {timeout:.1f}s. "
                        f"Retrying Stop-and-Wait...",
                        file=sys.stderr
                    )
                else:
                    print(
                        f"[CLIENT ERROR] Attempt {attempt}/{max_retries} timed out after {timeout:.1f}s. "
                        f"Retries exhausted.",
                        file=sys.stderr
                    )

        raise TimeoutError(
            f"Query for '{domain}' failed after {max_retries} attempts ({max_retries * timeout:.1f}s total)."
        )

    finally:
        if owns_socket:
            sock.close()


def print_formatted_result(domain: str, response: MYDNSMessage, rtt_ms: float, resolver_addr: Tuple[str, int]) -> None:
    """Formats and prints the query resolution details to stdout."""
    status_str = response.get_status_name()
    print("=" * 70)
    print("MYDNS/1.0 Resolution Result")
    print("=" * 70)
    print(f"Queried Domain:   {domain}")
    print(f"Resolver Host:    {resolver_addr[0]}:{resolver_addr[1]}")
    print(f"Transaction ID:   {response.tx_id:#06x} ({response.tx_id})")
    print(f"Response Status:  {status_str} (0x{response.status:02X})")
    print(f"Round-Trip Time:  {rtt_ms:.2f} ms")

    if response.status == STATUS_SUCCESS:
        # Heuristic classification for educational demo: < 2.5ms typically indicates local cache hit
        cache_hint = "CACHE HIT (Fast Path)" if rtt_ms < 2.5 else "CACHE MISS (Full Upstream Traversal)"
        print(f"Resolved IPv4:    {response.ip_address}")
        print(f"Time-To-Live:     {response.ttl} seconds")
        print(f"Path Performance: {cache_hint}")
        print("-" * 70)
        print(f"[SUCCESS] {domain} -> {response.ip_address} (TTL: {response.ttl}s, RTT: {rtt_ms:.2f}ms)")
    elif response.status == STATUS_NXDOMAIN:
        print(f"Resolved IPv4:    None (0.0.0.0)")
        print(f"Time-To-Live:     0 seconds")
        print("-" * 70)
        print(f"[NXDOMAIN] Domain '{domain}' does not exist in authoritative zone database.")
    elif response.status == STATUS_SERVER_FAILURE:
        print(f"Resolved IPv4:    None (0.0.0.0)")
        print(f"Time-To-Live:     0 seconds")
        print("-" * 70)
        print(f"[SERVER FAILURE] Resolver was unable to reach authoritative upstream server.")
    elif response.msg_type == MSG_ERROR or response.status == STATUS_FORMAT_ERROR:
        print(f"Resolved IPv4:    None (0.0.0.0)")
        print(f"Time-To-Live:     0 seconds")
        print("-" * 70)
        print(f"[FORMAT ERROR] Query format rejected by resolver or server (Fail-Fast, no retries).")
    else:
        print("-" * 70)
        print(f"[UNKNOWN STATUS 0x{response.status:02X}] Response returned unrecognized status code.")
    print("=" * 70)


def main() -> int:
    """CLI entrypoint for interactive DNS queries."""
    parser = argparse.ArgumentParser(
        description="MYDNS/1.0 Client CLI - Host 1 Query Engine & Latency Profiler"
    )
    parser.add_argument(
        "--resolver-ip",
        type=str,
        default="127.0.0.1",
        help="IPv4 address of the Caching Resolver (Host 2, default: 127.0.0.1)"
    )
    parser.add_argument(
        "--resolver-port",
        type=int,
        default=53000,
        help="UDP port of the Caching Resolver (default: 53000)"
    )
    parser.add_argument(
        "--domain",
        type=str,
        default="portal.neduet.local",
        help="Domain name to resolve (default: portal.neduet.local)"
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=1.5,
        help="Stop-and-wait timeout in seconds per attempt (default: 1.5)"
    )
    parser.add_argument(
        "--retries",
        type=int,
        default=3,
        help="Maximum retry attempts before failing (default: 3)"
    )

    args = parser.parse_args()

    print(f"[CLIENT] Sending MYDNS/1.0 query for '{args.domain}' to {args.resolver_ip}:{args.resolver_port}...")
    try:
        response, rtt_ms = query_domain(
            resolver_ip=args.resolver_ip,
            resolver_port=args.resolver_port,
            domain=args.domain,
            timeout=args.timeout,
            max_retries=args.retries
        )
        print_formatted_result(args.domain, response, rtt_ms, (args.resolver_ip, args.resolver_port))
        return 0
    except TimeoutError as e:
        print(f"\n[CLIENT TIMEOUT ERROR] {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"\n[CLIENT FATAL ERROR] {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
