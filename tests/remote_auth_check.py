import os
import socket
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from protocol import MYDNSMessage, MSG_QUERY, STATUS_SUCCESS, STATUS_NXDOMAIN

if len(sys.argv) < 2:
    print("usage: python tests\\remote_auth_check.py <host3-ip> [port]")
    sys.exit(2)

HOST = sys.argv[1]
PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 53053


def ask(domain, tx_id, timeout=2.0):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(timeout)
    try:
        t0 = time.perf_counter()
        s.sendto(MYDNSMessage(tx_id, MSG_QUERY, domain=domain).pack(), (HOST, PORT))
        data, src = s.recvfrom(512)
        rtt_ms = (time.perf_counter() - t0) * 1000
        return MYDNSMessage.unpack(data), rtt_ms, src
    except (socket.timeout, ConnectionResetError) as e:
        return None, None, repr(e)
    finally:
        s.close()


ok = True
for dom, tx in [("portal.neduet.local", 0xA1B2), ("nosuch.neduet.local", 0x0002)]:
    r, rtt, src = ask(dom, tx)
    if r is None:
        print(f"[FAIL] {dom}: no reply ({src})")
        ok = False
    else:
        print(f"[OK] {dom} -> {r.get_status_name()} {r.ip_address} ttl={r.ttl} "
              f"txid=0x{r.tx_id:04x} rtt={rtt:.1f} ms from {src}")

print("\nHost 3 reachable" if ok else "\nHost 3 NOT reachable, see checklist below")
sys.exit(0 if ok else 1)