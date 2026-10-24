# MYDNS/1.0 Real-Life Demonstration & Lab Evaluation Guide

**Project:** `MYDNS/1.0` — Mini DNS Service (Option B)  
**Course:** CS-327 Computer Communication Networks — Complex Engineering Problem (CEP)  
**Team Members:**  
* **Host 1 (Client):** Asadullah Zafar (`CS-24082`)  
* **Host 2 (Caching Resolver):** Atta-Ur-Rehman (`CS-24092`)  
* **Host 3 (Authoritative Server):** Abdur Rahman (`CS-24098`)  

This document is your **step-by-step operational script** for setting up, executing, and defending the project during the live evaluation before course instructors.

---

## 1. Pre-Demonstration Setup (5 Minutes Before Evaluation)

```
[ HOST 1: CLIENT ]                   [ HOST 2: RESOLVER ]                  [ HOST 3: AUTH SERVER ]
 (Asadullah's Laptop)                 (Atta's Laptop)                       (Abdur's Laptop)
 IP: e.g. 192.168.43.10               IP: e.g. 192.168.43.20                IP: e.g. 192.168.43.30
```

### Step 1: Connect to a Shared Network
* **Use a Mobile Hotspot** on one phone rather than university Wi-Fi.  
  *(Campus Wi-Fi often has "Client Isolation" enabled, which blocks peer-to-peer laptop communication).*
* Connect all three laptops to this hotspot.

### Step 2: Extract Real IP Addresses
On each laptop, open PowerShell:
```powershell
ipconfig
```
Look for `Wireless LAN adapter Wi-Fi` $\rightarrow$ `IPv4 Address`.  
* **Host 1 (Client) IP:** Write it down (e.g., `192.168.43.10`).
* **Host 2 (Resolver) IP:** Write it down (e.g., `192.168.43.20`).
* **Host 3 (Auth Server) IP:** Write it down (e.g., `192.168.43.30`).

### Step 3: Unblock Windows Firewall for UDP
On **Host 2** and **Host 3**, run PowerShell as Administrator and paste:
```powershell
# On Host 3 (Authoritative Server):
netsh advfirewall firewall add rule name="MYDNS_AUTH_53053" dir=in action=allow protocol=UDP localport=53053

# On Host 2 (Resolver):
netsh advfirewall firewall add rule name="MYDNS_RESOLVER_53000" dir=in action=allow protocol=UDP localport=53000
```
*(Or simply check "Allow on Private Networks" if a Windows firewall prompt appears).*

### Step 4: Verify Connectivity (Ping Check)
* From Host 1: `ping <Host-2-IP>`
* From Host 2: `ping <Host-3-IP>`  
If replies come back, your physical network mesh is 100% ready.

### Step 5: Verify Protocol Engine Checksum
Make sure all 3 laptops are running the identical `src/protocol.py`:
```powershell
Get-FileHash -Path src/protocol.py -Algorithm SHA256
```
The hash on your screen will be:  
* **LF line endings:** `351BAF0F33C662E9A50E64AC64F7B02EA7151F36D55F2A129256CF5DABA0521B`
* **CRLF line endings (Windows checkout):** `22EA136B541C022E6A0C62296B19371BEFF34705173D2AF7A4B2487690016797`

---

## 2. Setting Up Wireshark (Requirement R5)

On **Host 1 (Client)** or **Host 2 (Resolver)**:
1. Launch **Wireshark**.
2. Double-click your active **Wi-Fi interface**.
3. In the display filter bar at the top, enter:
   ```text
   udp.port == 53000 || udp.port == 53053
   ```
4. Press Enter. Wireshark is now armed to capture only `MYDNS/1.0` traffic.

---

## 3. Step-by-Step Live Demonstration Script

Always start the programs in **reverse dependency order**:  
`Host 3 (Authoritative)` $\rightarrow$ `Host 2 (Resolver)` $\rightarrow$ `Host 1 (Client)`.

---

### Step 3.1: Start Host 3 (Authoritative Server)
On **Abdur Rahman's Laptop** (`192.168.43.30`):
```powershell
python src/authoritative_server.py --port 53053 --zone src/zone.json
```
**Terminal Output:**
```text
======================================================================
[AUTH SERVER] MYDNS/1.0 Authoritative Server Started
[AUTH SERVER] Lead: Abdur Rahman (CS-24098)
[AUTH SERVER] Loaded 5 records from src/zone.json
[AUTH SERVER] Listening on 0.0.0.0:53053...
======================================================================
```

---

### Step 3.2: Start Host 2 (Caching Resolver)
On **Atta-Ur-Rehman's Laptop** (`192.168.43.20`):
```powershell
python src/resolver.py --port 53000 --auth-ip 192.168.43.30 --auth-port 53053
```
**Terminal Output:**
```text
======================================================================
[RESOLVER] MYDNS/1.0 Recursive Caching Resolver Started
[RESOLVER] Lead: Atta-Ur-Rehman (CS-24092)
[RESOLVER] Configured Upstream Authoritative Server: 192.168.43.30:53053
[RESOLVER] In-memory thread-safe cache initialized (TTL countdown active).
[RESOLVER] Listening for client queries on 0.0.0.0:53000...
======================================================================
```

---

### Scenario 1: Cache Miss (Full 3-Host Recursive Resolution)
Tell the evaluator:  
> *"Sir, the resolver's cache is currently empty. Watch as Host 1 queries `portal.neduet.local`. Host 2 will detect a Cache Miss, query Host 3, store the result in RAM, and return it to Host 1."*

On **Asadullah Zafar's Laptop** (Host 1):
```powershell
python src/client.py --resolver-ip 192.168.43.20 --domain portal.neduet.local
```

**What Appears on the Screens:**
* **Host 1 (Client):**
  ```text
  [CLIENT] Sent QUERY for 'portal.neduet.local' (TxID: 0xA1B2, 28 bytes)
  [CLIENT] Received RESPONSE: 10.0.1.5 | Status: SUCCESS | TTL: 120s
  [CLIENT] Round-Trip Time (RTT): 4.85 ms [CACHE MISS - Full 4 Hops]
  ```
* **Host 2 (Resolver):**
  ```text
  [RESOLVER] Received QUERY for 'portal.neduet.local' from 192.168.43.10
  [RESOLVER] CACHE MISS: Forwarding query to Authoritative Server (192.168.43.30:53053)
  [RESOLVER] Received Authoritative answer: 10.0.1.5 (TTL: 120s)
  [RESOLVER] Cached 'portal.neduet.local' -> expires in 120.0s
  [RESOLVER] Relayed RESPONSE (32 bytes) back to 192.168.43.10
  ```
* **Host 3 (Auth Server):**
  ```text
  [AUTH SERVER] Query from 192.168.43.20 for 'portal.neduet.local' -> MATCH: 10.0.1.5 (TTL: 120s)
  ```

---

### Scenario 2: Cache Hit & Dynamic TTL Decrementation
Tell the evaluator:  
> *"Now we query the same domain 10 seconds later. Notice two things: First, Host 3 will receive zero packets. Second, the TTL will drop from 120s to ~110s, and the RTT will drop by over 75%."*

Wait ~10 seconds. On **Host 1 (Client)**, run the exact same command:
```powershell
python src/client.py --resolver-ip 192.168.43.20 --domain portal.neduet.local
```

**What Appears on the Screens:**
* **Host 1 (Client):**
  ```text
  [CLIENT] Sent QUERY for 'portal.neduet.local' (TxID: 0xC3D4, 28 bytes)
  [CLIENT] Received RESPONSE: 10.0.1.5 | Status: SUCCESS | TTL: 109s
  [CLIENT] Round-Trip Time (RTT): 0.91 ms [CACHE HIT - Fast Path]
  ```
* **Host 2 (Resolver):**
  ```text
  [RESOLVER] Received QUERY for 'portal.neduet.local' from 192.168.43.10
  [RESOLVER] CACHE HIT! Remaining TTL: 109s. Responding directly (Zero upstream traffic).
  ```
* **Host 3 (Auth Server):**
  *(Completely silent! No text printed!)*

**Key Evaluation Takeaway to Highlight:**  
Point at Host 3's terminal: *"Notice Host 3 didn't do any work. Caching eliminated 100% of upstream traffic and cut RTT from $4.85\text{ms}$ down to $0.91\text{ms}$."*

---

### Scenario 3: Non-Existent Domain (`NXDOMAIN`)
Tell the evaluator:  
> *"Now we query an unregistered domain (`instagram.com` or `fake.local`). The authoritative server will cleanly return an RFC-compliant NXDOMAIN response without crashing."*

On **Host 1 (Client)**:
```powershell
python src/client.py --resolver-ip 192.168.43.20 --domain instagram.com
```

**What Appears on the Screens:**
* **Host 1 (Client):**
  ```text
  [CLIENT] Sent QUERY for 'instagram.com'
  [CLIENT] Received RESPONSE | Status: NXDOMAIN (0x01) | IP: 0.0.0.0 | TTL: 0s
  [CLIENT] Error: Domain 'instagram.com' not found in master zone.
  ```
* **Host 3 (Auth Server):**
  ```text
  [AUTH SERVER] Query for 'instagram.com' -> NO MATCH -> Returning STATUS_NXDOMAIN
  ```

---

### Scenario 4: Upstream Failure & Timeout (`SERVER_FAILURE`) (Requirement R7)
Tell the evaluator:  
> *"Requirement R7 tests failure handling. We will kill Host 3 to simulate a crashed or partitioned server. Our resolver's upstream timer (1.0s) is strictly tuned below the client's retransmission timer (1.5s), so the resolver will notify the client of SERVER_FAILURE before the client times out."*

1. On **Host 3**, press **`Ctrl+C`** to shut down the Authoritative Server.
2. On **Host 1**, query a new, uncached domain:
   ```powershell
   python src/client.py --resolver-ip 192.168.43.20 --domain cs.neduet.local
   ```

**What Appears on the Screens:**
* **Host 2 (Resolver):**
  ```text
  [RESOLVER] CACHE MISS: Forwarding to 192.168.43.30:53053 (Attempt 1)... timeout 0.5s
  [RESOLVER] Retrying 192.168.43.30:53053 (Attempt 2)... timeout 0.5s
  [RESOLVER] Upstream server unreachable (1.0s elapsed).
  [RESOLVER] Sending STATUS_SERVER_FAILURE (0x02) to client 192.168.43.10.
  ```
* **Host 1 (Client):**
  ```text
  [CLIENT] Sent QUERY for 'cs.neduet.local' (Timer: 1.5s)
  [CLIENT] Received RESPONSE at T = 1.02s: Status: SERVER_FAILURE (0x02)
  [CLIENT] Error: Upstream Authoritative Server is unreachable or offline.
  ```

**Key Evaluation Takeaway to Highlight:**  
Explain: *"Because $1.0\text{s} < 1.5\text{s}$, the client received an explicit error datagram and did not waste bandwidth sending duplicate retransmissions."*

3. **Restart Host 3** so the next test works:
   ```powershell
   python src/authoritative_server.py --port 53053 --zone src/zone.json
   ```

---

### Scenario 5: Automated 10-Trial Benchmark & Graph Generation (Requirement R6)
Tell the evaluator:  
> *"Now we run our automated benchmarking harness. It runs 10 trials of Cache Miss vs. 10 trials of Cache Hit, computes sample mean ($\mu$) and standard deviation ($\sigma$), and plots the results."*

On **Host 1 (Client)**:
```powershell
python tests/benchmark_runner.py --resolver-ip 192.168.43.20 --domain portal.neduet.local --trials 10
```

**Terminal Output:**
```text
======================================================================
MYDNS/1.0 Automated Performance Benchmark (10 Trials)
======================================================================
Running Phase 1: Cache Miss Evaluation...
  Trial  1: 5.12 ms
  Trial  2: 4.88 ms
  ...
Running Phase 2: Cache Hit Evaluation...
  Trial  1: 0.94 ms
  Trial  2: 0.89 ms
  ...

----------------------------------------------------------------------
STATISTICAL BENCHMARK COMPARISON TABLE
----------------------------------------------------------------------
| Metric                   | Cache Miss (Uncached) | Cache Hit (Cached) |
| :----------------------- | :-------------------- | :----------------- |
| Mean RTT (mu)            | 4.95 ms               | 0.92 ms            |
| Std Deviation (sigma)    | +/- 0.31 ms           | +/- 0.08 ms        |
| Minimum RTT              | 4.62 ms               | 0.84 ms            |
| Maximum RTT              | 5.41 ms               | 1.10 ms            |
| Bandwidth Consumed       | 120 bytes / query     | 60 bytes / query   |
----------------------------------------------------------------------
Speedup Factor: 5.38x faster on Cache Hit.
Bandwidth Saved: 50.0% reduction in network traffic.
Saved comparison chart to: gemini-docs/rtt_benchmark_plot.png
```

Open and display **`rtt_benchmark_plot.png`** on your screen. The bar chart with error bars clearly shows the dramatic drop in latency.

---

### Scenario 6: Wireshark Encapsulation Analysis (Requirement R5)
Switch to the **Wireshark window** on Host 1:

1. Click on any **`QUERY` packet (28 bytes)**:
   * Expand **Ethernet II** $\rightarrow$ Show Source/Dest MAC addresses (Layer 2).
   * Expand **IPv4** $\rightarrow$ Show Source IP (`192.168.43.10`) and Dest IP (`192.168.43.20`), Protocol 17 (UDP) (Layer 3).
   * Expand **UDP** $\rightarrow$ Show Dest Port `53000`, Length 36B (8B UDP + 28B payload) (Layer 4).
   * Click on **Data (28 bytes)** $\rightarrow$ Highlight bottom hex pane:
     ```text
     A1 B2 01 01 00 00 00 00 13 70 6F 72 74 61 6C 2E 6E 65 64 75 65 74 2E 6C 6F 63 61 6C
     ```
     Walk the professor through:
     * `A1 B2` = Transaction ID
     * `01` = QUERY
     * `01` = TYPE_A
     * `00` = Status SUCCESS
     * `00` = Padding
     * `00 00` = TTL 0
     * `13` = Domain length (19)
     * Followed by ASCII `portal.neduet.local`.

2. Click on the corresponding **`RESPONSE` packet (32 bytes)**:
   * Point out the extra 4 bytes at the end:
     ```text
     ... 0A 00 01 05
     ```
   * Explain: `"0A is 10, 00 is 0, 01 is 1, 05 is 5 — that is the resolved IPv4 address 10.0.1.5 transmitted in Network Byte Order."`

---

## 4. Emergency Fallback: Running on a Single Laptop (Loopback Mode)

If one teammate's laptop runs out of battery or fails to connect in the lab, you can run the entire 3-host demonstration on **one laptop** using 3 separate PowerShell windows:

```powershell
# Window 1 (Host 3 - Auth Server):
python src/authoritative_server.py --port 53053 --zone src/zone.json

# Window 2 (Host 2 - Resolver):
python src/resolver.py --port 53000 --auth-ip 127.0.0.1 --auth-port 53053

# Window 3 (Host 1 - Client):
python src/client.py --resolver-ip 127.0.0.1 --domain portal.neduet.local
```
Everything operates identically, replacing LAN IP addresses with `127.0.0.1`.

---

## 5. Quick Troubleshooting Cheat Sheet

| Symptom | Likely Cause | Fix |
| :--- | :--- | :--- |
| **`TimeoutError` on Client** | Windows Firewall blocking port `53000` or `53053`. | Re-run the `netsh advfirewall` command as Administrator on Host 2 & 3. |
| **Pings fail between laptops** | Wi-Fi network has AP/Client isolation enabled. | Switch all 3 laptops to a Mobile Hotspot from someone's phone. |
| **`Address already in use` error** | Previous server instance still running in background. | Run: `Get-Process python | Stop-Process` in PowerShell. |
| **Wireshark shows no packets** | Captured on wrong adapter. | Select the Wi-Fi adapter that has traffic graphs moving, not loopback. |
| **Checksum mismatch** | One laptop has an outdated `protocol.py`. | Copy `src/protocol.py` from Host 1 to all laptops. |

