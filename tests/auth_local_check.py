import os
import socket
import sys
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from protocol import (MYDNSMessage, MSG_QUERY, MSG_RESPONSE, MSG_ERROR,
                      STATUS_SUCCESS, STATUS_NXDOMAIN, STATUS_FORMAT_ERROR)

HOST, PORT = "127.0.0.1", 53053
results = []


def exchange(payload, timeout=2.0):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(timeout)
    try:
        s.sendto(payload, (HOST, PORT))
        data, _ = s.recvfrom(512)
        return data
    except (socket.timeout, ConnectionResetError):
        return None
    finally:
        s.close()


def query(domain, tx_id):
    return exchange(MYDNSMessage(tx_id, MSG_QUERY, domain=domain).pack())


def check(name, cond):
    results.append(cond)
    print(f"[{'PASS' if cond else 'FAIL'}] {name}")


# 1. known domain
d = query("portal.neduet.local", 0xA1B2)
r = MYDNSMessage.unpack(d) if d else None
check("known domain -> 32 B, SUCCESS, 10.0.1.5, ttl 120, TxID echoed",
      r is not None and len(d) == 32 and r.msg_type == MSG_RESPONSE
      and r.status == STATUS_SUCCESS and r.ip_address == "10.0.1.5"
      and r.ttl == 120 and r.tx_id == 0xA1B2)

# 2. unknown domain
dom = "nosuch.neduet.local"
d = query(dom, 0x0002)
r = MYDNSMessage.unpack(d) if d else None
check("unknown domain -> NXDOMAIN, 0.0.0.0, ttl 0",
      r is not None and len(d) == 13 + len(dom) and r.status == STATUS_NXDOMAIN
      and r.ip_address == "0.0.0.0" and r.ttl == 0 and r.tx_id == 0x0002)

# 3. mixed case: lookup works, original case is echoed
dom = "PORTAL.NEDUET.Local"
d = query(dom, 0x0003)
r = MYDNSMessage.unpack(d) if d else None
check("mixed-case domain -> SUCCESS and case echoed",
      r is not None and r.status == STATUS_SUCCESS and r.ip_address == "10.0.1.5"
      and r.domain == dom)

# 4. garbage bytes
d = exchange(b"\xde\xad\xbe")
r = MYDNSMessage.unpack(d) if d else None
check("garbage bytes -> ERROR, FORMAT_ERROR, TxID 0xDEAD",
      r is not None and r.msg_type == MSG_ERROR
      and r.status == STATUS_FORMAT_ERROR and r.tx_id == 0xDEAD)

# 5. non-QUERY message must be ignored (expect a timeout)
bad = MYDNSMessage(0x0005, MSG_RESPONSE, ttl=120, domain="portal.neduet.local",
                   ip_address="10.0.1.5").pack()
check("RESPONSE sent to server -> ignored (no reply)", exchange(bad, timeout=1.0) is None)

# 6. server still alive after garbage and the ignored packet
d = query("portal.neduet.local", 0x0006)
check("server still answers after bad input", d is not None and len(d) == 32)

# 7. stress: 50 parallel queries across the 10 benchmark names
domains = [f"bench{n:02d}.neduet.local" for n in range(1, 11)]


def one(i):
    dom = domains[i % 10]
    data = query(dom, 1000 + i)
    if data is None:
        return False
    m = MYDNSMessage.unpack(data)
    return (m.tx_id == 1000 + i and m.status == STATUS_SUCCESS and m.domain == dom
            and m.ip_address == f"10.0.2.{i % 10 + 1}")


with ThreadPoolExecutor(max_workers=50) as ex:
    stress = list(ex.map(one, range(50)))
print(f"stress: {sum(stress)}/50 correct")
check("50 parallel queries, none dropped or mismatched", all(stress))

print(f"\n{sum(results)}/{len(results)} checks passed")
sys.exit(0 if all(results) else 1)