# Physical Setup & Multi-Host Deployment Guide
**Project:** CS-327 Computer Communication Networks — Complex Engineering Problem (CEP)  
**Track:** Option B — Mini DNS Service (`MYDNS/1.0`)  
**Requirement Addressed:** Mandatory Requirement R3 & Criterion 2 (3 Independent Network Endpoints)

---

## 1. Architecture & Port Mapping

```
[ HOST 1: CLIENT ]                   [ HOST 2: RESOLVER ]                  [ HOST 3: AUTH SERVER ]
   (e.g., 192.168.43.10)                 (e.g., 192.168.43.20)                 (e.g., 192.168.43.30)
            |                                      |                                      |
            |--- UDP Query (Port 53000) ---------->|                                      |
            |                                      |--- UDP Query (Port 53053) ---------->|
            |                                      |<-- UDP Response ---------------------|
            |<-- UDP Response ---------------------|                                      |
```

| Host Role | Script File | Default Listening Port | Target Connection |
| :--- | :--- | :--- | :--- |
| **Host 3 (Authoritative)** | `src/authoritative_server.py` | UDP `53053` | None (Listens only) |
| **Host 2 (Resolver)** | `src/resolver.py` | UDP `53000` | Forwards uncached queries to Host 3 (`53053`) |
| **Host 1 (Client)** | `src/client.py` | Ephemeral OS port | Queries Host 2 (`53000`) |

---

## 2. Option A: 3 Physical Laptops via Mobile Hotspot or Lab Wi-Fi (Recommended)

This is the most reliable, plug-and-play arrangement for campus demonstrations.

### Step 1: Network Association
1. Turn on a **Mobile Hotspot** on one smartphone (or connect all 3 laptops to the same department lab Wi-Fi/switch).
   > **Important:** Some university Wi-Fi networks have **Client Isolation** (AP isolation) enabled, which prevents peer-to-peer laptop communication. A mobile hotspot or personal router avoids this issue completely.
2. Connect all 3 laptops to this Wi-Fi network.

### Step 2: Extract Real IP Configurations
On each laptop, open PowerShell or Terminal:
* **Windows:**
  ```powershell
  ipconfig
  ```
  Look for `Wireless LAN adapter Wi-Fi` $\rightarrow$ `IPv4 Address` (e.g., `192.168.43.15`).
* **Linux:**
  ```bash
  ip -4 addr show
  ```
* **macOS:**
  ```bash
  ifconfig | grep "inet "
  ```
> **Deliverable Note:** Take a screenshot of the `ipconfig` / `ip addr` output on each machine. You are required to include these screenshots in Section 3 of the final report!

### Step 3: Firewall Configuration (Crucial on Windows)
By default, Windows Defender Firewall blocks incoming UDP packets on non-standard ports.
* On **Host 3** (Authoritative Server) and **Host 2** (Resolver), run PowerShell as Administrator to allow UDP traffic:
  ```powershell
  # On Host 3: Allow incoming UDP 53053
  netsh advfirewall firewall add rule name="MYDNS_AUTH_53053" dir=in action=allow protocol=UDP localport=53053

  # On Host 2: Allow incoming UDP 53000
  netsh advfirewall firewall add rule name="MYDNS_RESOLVER_53000" dir=in action=allow protocol=UDP localport=53000
  ```
* Alternatively, when Windows pops up the alert *"Windows Defender Firewall has blocked some features of Python"*, ensure **"Private networks"** is checked and click **"Allow Access"**.

### Step 4: Connectivity Sanity Check (ICMP Ping)
Before running the Python scripts, test baseline connectivity between the nodes:
* From Host 1: `ping <Host-2-IP>`
* From Host 2: `ping <Host-3-IP>`
If pings time out, re-check firewall settings or mobile hotspot settings.

---

## 3. Option B: 1 Laptop + 2 Virtual Machines (Bridged Networking)

If you are developing or testing when team members are not physically together, you can run all 3 endpoints on a single computer using virtualization **without violating the loopback rule**.

1. In **VirtualBox** or **VMware Workstation**:
   * Create two Linux (e.g., Ubuntu Server/Desktop) or Windows VMs.
   * Go to **VM Settings $\rightarrow$ Network $\rightarrow$ Adapter 1**.
   * Change *Attached to:* from `NAT` to **`Bridged Adapter`**.
   * Select your active Wi-Fi or Ethernet network interface.
2. Boot both VMs. Each VM will request and obtain a distinct, routable IP address from your local router's DHCP pool (e.g., Host: `192.168.1.10`, VM1: `192.168.1.11`, VM2: `192.168.1.12`).
3. Run `ip addr` in each VM to confirm independent IP assignments.

---

## 4. Execution Order & Command Line Arguments

Always launch the nodes in **reverse dependency order** (Back-end $\rightarrow$ Middle-tier $\rightarrow$ Front-end):

### Phase 1: Start Authoritative Server (Host 3)
On Host 3 (`192.168.43.30`):
```bash
python src/authoritative_server.py --port 53053 --zone src/zone.json
```
*Expected Terminal Output:*
```
[AUTH SERVER] Loaded 6 zone records from src/zone.json
[AUTH SERVER] Listening for MYDNS/1.0 queries on 0.0.0.0:53053...
```

### Phase 2: Start Caching Resolver (Host 2)
On Host 2 (`192.168.43.20`):
```bash
python src/resolver.py --port 53000 --auth-ip 192.168.43.30 --auth-port 53053
```
*Expected Terminal Output:*
```
[RESOLVER] Initialized in-memory thread-safe cache engine.
[RESOLVER] Configured upstream Authoritative Server at 192.168.43.30:53053
[RESOLVER] Listening for client queries on 0.0.0.0:53000...
```

### Phase 3: Run Client Lookups & Benchmarks (Host 1)
On Host 1 (`192.168.43.10`):

1. **Single Interactive Query:**
   ```bash
   python src/client.py --resolver-ip 192.168.43.20 --resolver-port 53000 --domain portal.neduet.local
   ```
   *First Run (Cache Miss):*
   ```
   [CLIENT] Sent QUERY (TxID: 0xA1B2, Domain: portal.neduet.local)
   [CLIENT] Received RESPONSE: 10.0.1.5 (TTL: 120s, Status: SUCCESS)
   [CLIENT] Measured RTT: 4.82 ms (CACHE MISS)
   ```
   *Second Run (Immediate Cache Hit):*
   ```bash
   python src/client.py --resolver-ip 192.168.43.20 --resolver-port 53000 --domain portal.neduet.local
   ```
   ```
   [CLIENT] Sent QUERY (TxID: 0xC3D4, Domain: portal.neduet.local)
   [CLIENT] Received RESPONSE: 10.0.1.5 (TTL: 116s, Status: SUCCESS)
   [CLIENT] Measured RTT: 0.94 ms (CACHE HIT)
   ```

2. **Automated Multi-Trial Benchmark Suite (R6):**
   ```bash
   python tests/benchmark_runner.py --resolver-ip 192.168.43.20 --trials 10 --domain portal.neduet.local
   ```

---

## 5. Packet Capture with Wireshark (R5)

To produce the required annotated screenshot in the report:
1. Open **Wireshark** on Host 1 or Host 2.
2. Select your active Wi-Fi interface.
3. In the display filter bar, enter:
   ```wireshark
   udp.port == 53000 || udp.port == 53053
   ```
4. Trigger a query from Host 1.
5. Stop the capture. You will see the UDP datagrams.
6. Click on the packet and inspect the Wireshark packet details pane:
   * **Frame:** Layer 2 (Ethernet / 802.11)
   * **IPv4:** Layer 3 (Source & Destination IP addresses)
   * **UDP:** Layer 4 (Source & Destination Ports)
   * **Data:** Layer 7 (`MYDNS/1.0` binary payload)
7. Right-click the Data payload $\rightarrow$ select **"Show Packet Bytes"** to highlight your custom 8-byte header!

