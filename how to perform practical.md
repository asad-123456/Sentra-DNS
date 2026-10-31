# MYDNS/1.0 — How to Perform the Live Group Practical

**Course:** CS-327 Computer Communication Networks — Complex Engineering Problem (CEP)  
**Project Track:** Option B — Mini DNS Service (`MYDNS/1.0`)  
**Team Members & Roles:**
* **Host 1 (Client & Benchmarking Lead):** Asadullah Zafar (`CS-24082`)
* **Host 2 (Caching Resolver Lead):** Atta-Ur-Rehman (`CS-24092`)
* **Host 3 (Protocol & Authoritative Server Lead):** Abdur Rahman (`CS-24098`)

---

## 1. Laptop & Service Allocation

| Member | Machine Role | Script to Run | Listening Port | Target / Upstream |
| :--- | :--- | :--- | :--- | :--- |
| **Abdur Rahman** (`CS-24098`) | **Host 3:** Authoritative Zone Server | `src/authoritative_server.py` | UDP `53053` | None (reads `src/zone.json`) |
| **Atta-Ur-Rehman** (`CS-24092`) | **Host 2:** Caching Recursive Resolver | `src/resolver.py` | UDP `53000` | Upstream Host 3 (`<Abdur-IP>:53053`) |
| **Asadullah Zafar** (`CS-24082`) | **Host 1:** Client Engine & Benchmarking | `src/client.py` | Ephemeral port | Queries Host 2 (`<Atta-IP>:53000`) |

---

## 2. Stage 1: Pre-Demonstration Physical Setup (5 Minutes Prior)

Arrange the 3 laptops side by side on the lab desk:
```
[ LAPTOP 1: ASADULLAH ]         [ LAPTOP 2: ATTA ]         [ LAPTOP 3: ABDUR ]
       (Client)                     (Resolver)                (Auth Server)
```

### Step 1.1: Connect to a Shared Mobile Hotspot
* Turn on the **Mobile Hotspot** on one team member's smartphone.
* Connect all 3 laptops to this Wi-Fi hotspot.
> **Why Hotspot?** University campus Wi-Fi enforces **Access Point (AP) Client Isolation**, which blocks peer-to-peer laptop traffic. A personal hotspot guarantees peer-to-peer UDP packet transmission.

### Step 1.2: Obtain and Record Real IPv4 Addresses
On each laptop, open PowerShell and run:
```powershell
ipconfig
```
Find the IPv4 address under `Wireless LAN adapter Wi-Fi`. Write them down:
* **Host 1 (Asadullah - Client):** `____________________` (e.g., `192.168.43.10`)
* **Host 2 (Atta - Resolver):** `____________________` (e.g., `192.168.43.20`)
* **Host 3 (Abdur - Auth Server):** `____________________` (e.g., `192.168.43.30`)

### Step 1.3: Configure Windows Firewall on Hosts 2 and 3
On **Laptop 2** and **Laptop 3**, open PowerShell as Administrator and run:
```powershell
# On Abdur's Laptop (Host 3 - Auth Server):
netsh advfirewall firewall add rule name="MYDNS_AUTH" dir=in action=allow protocol=UDP localport=53053

# On Atta's Laptop (Host 2 - Resolver):
netsh advfirewall firewall add rule name="MYDNS_RESOLVER" dir=in action=allow protocol=UDP localport=53000
```
*(Alternatively, when Windows pops up a Defender alert, ensure **Private Networks** is checked and click **Allow Access**).*

### Step 1.4: Physical Connectivity Sanity Check (ICMP Ping)
* From Laptop 1: `ping <Atta-IP>`
* From Laptop 2: `ping <Abdur-IP>`  
Ensure 0% packet loss before proceeding.

### Step 1.5: Arm Wireshark on Laptop 1 (Requirement R5)
On **Laptop 1 (Asadullah)**:
1. Open **Wireshark**.
2. Double-click the active **Wi-Fi** network interface card.
3. In the display filter bar at the top, enter:
   ```text
   udp.port == 53000 || udp.port == 53053
   ```
4. Press **Enter**. Wireshark is now armed to capture only `MYDNS/1.0` traffic.

---

## 3. Stage 2: Booting the System (Strict Reverse Dependency Order)

Always launch the nodes in reverse dependency order (Host 3 $\rightarrow$ Host 2 $\rightarrow$ Host 1):

### Step 2.1: Abdur Launches Host 3 (Authoritative Server)
On **Laptop 3**:
```powershell
python src/authoritative_server.py --port 53053 --zone src/zone.json
```
**Abdur introduces Host 3 to the instructor:**
> *"Sir, Host 3 is our Authoritative Zone Server. It has loaded our master zone database from `zone.json` containing authentic campus records and is listening on UDP port 53053."*

### Step 2.2: Atta Launches Host 2 (Caching Resolver)
On **Laptop 2** (substituting Abdur's actual IP):
```powershell
python src/resolver.py --port 53000 --auth-ip <Abdur-IP> --auth-port 53053
```
**Atta introduces Host 2 to the instructor:**
> *"Host 2 is our Recursive Caching Resolver. It establishes upstream connectivity to Abdur's server at port 53053, initializes an in-memory thread-safe cache with dynamic TTL decrementing, and listens for client queries on UDP port 53000."*

---

## 4. Stage 3: Live Evaluation Scenarios (Scripted Walkthrough)

### Scenario 1: Cache Miss (Full 4-Hop Nodal Traversal)
**Asadullah says to instructor:**
> *"Sir, the resolver's RAM cache is currently cold and empty. I will query `portal.neduet.local`. Watch as the query traverses all 4 network hops across Link 1 and Link 2."*

On **Laptop 1**, Asadullah runs:
```powershell
python src/client.py --resolver-ip <Atta-IP> --domain portal.neduet.local
```

**What to point out across the 3 screens:**
* **Laptop 1 (Asadullah):** `Received RESPONSE: 10.0.1.5 | Status: SUCCESS | TTL: 120s | RTT: ~4.85 ms`
* **Laptop 2 (Atta):** `CACHE MISS -> Forwarding to Host 3 (<Abdur-IP>:53053) -> Cached record -> Relaying to Client`
* **Laptop 3 (Abdur):** `Query from <Atta-IP> for 'portal.neduet.local' -> MATCH: 10.0.1.5 (TTL: 120s)`

---

### Scenario 2: Cache Hit & Dynamic TTL Decrementation
**Atta says to instructor:**
> *"Now Asadullah will query the exact same domain 10 seconds later. Notice two key points: First, Abdur's Authoritative Server will receive zero packets because Link 2 is bypassed. Second, our resolver returns a dynamically decremented TTL and latency drops to sub-millisecond level."*

Wait ~10 seconds. On **Laptop 1**, Asadullah runs the exact same command:
```powershell
python src/client.py --resolver-ip <Atta-IP> --domain portal.neduet.local
```

**What to point out:**
* **Laptop 3 (Abdur):** Terminal is **completely silent** (zero network packets received).
* **Laptop 2 (Atta):** `CACHE HIT! Remaining TTL: 110s. Responding directly (Zero upstream load).`
* **Laptop 1 (Asadullah):** `TTL: 110s` (decremented from 120s) and `RTT: ~0.85 ms` ($\approx 5\times$ speedup).

---

### Scenario 3: Non-Existent Domain Resolution (`NXDOMAIN`)
**Abdur says to instructor:**
> *"If an unregistered domain is queried, our system returns an RFC-standard NXDOMAIN status code cleanly without crashing."*

On **Laptop 1**, Asadullah runs:
```powershell
python src/client.py --resolver-ip <Atta-IP> --domain fake.local
```

**What appears:**
* **Laptop 3 (Abdur):** `Query for fake.local -> NO MATCH -> Returning STATUS_NXDOMAIN (0x01)`
* **Laptop 1 (Asadullah):** `Status: NXDOMAIN (0x01) | IP: 0.0.0.0 | Domain not found in authoritative zone`

---

### Scenario 4: Upstream Failure & Timeout Handling (Requirement R7)
**Atta says to instructor:**
> *"Requirement R7 mandates deterministic handling of network failures. We tuned our resolver's upstream timeout (0.5s x 2 tries = 1.0s) strictly below the client's retransmission timeout (1.5s). If the authoritative server crashes, the resolver returns SERVER_FAILURE before the client retransmits, saving network bandwidth."*

1. **Abdur presses `Ctrl + C`** on Laptop 3 to terminate the Authoritative Server.
2. **Asadullah queries a new uncached domain** on Laptop 1:
   ```powershell
   python src/client.py --resolver-ip <Atta-IP> --domain cs.neduet.local
   ```
3. **What happens:**
   * **Laptop 2 (Atta):** Attempts 2 upstream queries (0.5s each), detects timeout at $T = 1.0\text{s}$, and returns `STATUS_SERVER_FAILURE` (`0x02`).
   * **Laptop 1 (Asadullah):** Receives the packet at $T \approx 1.02\text{s}$ and displays:  
     `Status: SERVER_FAILURE (0x02) - Upstream Authoritative Server unreachable`.
4. **Abdur restarts Host 3** so subsequent tests work:
   ```powershell
   python src/authoritative_server.py --port 53053 --zone src/zone.json
   ```

---

### Scenario 5: Automated 10-Trial Benchmark & Statistical Graph (Requirement R6)
**Asadullah says to instructor:**
> *"Now we execute our automated benchmarking harness to measure empirical nodal delay ($T_{nodal}$) and application throughput across 10 trials."*

On **Laptop 1**, Asadullah runs:
```powershell
python tests/benchmark_runner.py --resolver-ip <Atta-IP> --domain portal.neduet.local --trials 10
```

1. Review the printed table:
   * **Mean RTT ($\mu$):** Cache Miss $\approx 4.9\text{ ms}$ vs. Cache Hit $\approx 0.9\text{ ms}$
   * **Sample Standard Deviation ($\sigma$):** Displays variance
   * **Throughput (QPS & Bytes/s):** Demonstrates cache speedup
   * **Sustainability (CLO-3):** 50% byte savings per query
2. Open **`docs/rtt_benchmark_plot.png`** in Windows Photos to present the high-resolution comparison bar chart with error bars.

---

### Scenario 6: Wireshark Encapsulation Analysis (Requirement R5)
**Abdur and Asadullah switch to Wireshark on Laptop 1:**

1. Click on a **Query Datagram (28 bytes)**:
   * **Ethernet II:** Layer 2 MAC framing.
   * **IPv4:** Layer 3 Source/Dest IP, Protocol `17` (UDP).
   * **UDP:** Layer 4 Source Ephemeral Port $\rightarrow$ Dest Port `53000`.
   * **Application Payload (8-Byte Header + Domain):**
     * `Bytes 0–1`: Transaction ID (16 bits)
     * `Byte 2`: `01` (`MSG_QUERY`)
     * `Byte 3`: `01` (`TYPE_A`)
     * `Byte 4`: `00` (`STATUS_SUCCESS`)
     * `Byte 5`: `00` (Reserved pad)
     * `Bytes 6–7`: `00 00` (`TTL 0`)
     * `Byte 8`: `13` (Domain length = 19 bytes)
     * `Bytes 9–27`: ASCII string `portal.neduet.local`
2. Click on the matching **Response Datagram (32 bytes)**:
   * Point out the trailing 4 bytes in the hex dump: `0A 00 01 05`.
   * Explain: `0A` = 10, `00` = 0, `01` = 1, `05` = 5 $\rightarrow$ `10.0.1.5` in Big-Endian Network Byte Order.

---

## 5. Troubleshooting Cheat Sheet

| Symptom | Cause | Solution |
| :--- | :--- | :--- |
| **`TimeoutError` on Client** | Windows Firewall blocking incoming UDP on Host 2 or 3. | Re-run `netsh advfirewall` command as Administrator on Hosts 2 and 3. |
| **Pings fail between laptops** | Wi-Fi network has AP isolation active. | Switch all 3 laptops to a Mobile Hotspot from a smartphone. |
| **`Address already in use`** | A previous Python server instance is still bound to the port. | Run `Get-Process python \| Stop-Process` in PowerShell. |
| **Wireshark shows no packets** | Captured on wrong network adapter. | Ensure you double-click the Wi-Fi adapter with active packet graphs. |

