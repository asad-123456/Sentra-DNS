# Key Areas to Refine for a Perfect 50/50 Rubric Score
**Project:** CS-327 Computer Communication Networks — Complex Engineering Problem (CEP)  
**Track:** Option B — Mini DNS Service (`MYDNS/1.0`)  
**Target:** Level 4 (8–10 Marks across all 5 Criteria = 40–50 / 50 Total Marks)

This document details the critical engineering nuances and evaluation criteria needed to secure maximum marks on the final implementation, demonstration, and report.

---

## 1. Concurrency & Multi-Client Support (Criterion 2: 8–10 Marks)
* **The Rubric Expectation:**
  > *"The application runs correctly across three independent hosts holding distinct IP addresses... and the system handles concurrent clients or multiple servers cleanly. Sockets are used directly with no application protocol library, and the demonstration runs without intervention."*
* **The Pitfall:**
  A naive UDP server in a single-threaded `while True: recvfrom()` loop processes queries sequentially. If multiple clients query simultaneously, or if the resolver is blocked waiting for an authoritative server response during a cache miss, subsequent client queries stall in the OS UDP receive buffer.
* **The Engineering Fix:**
  * Implement Host 2 (Resolver) with **non-blocking asynchronous I/O** or **multi-threaded handling** (e.g., using Python's `socketserver.ThreadingUDPServer` or spawning worker threads per incoming datagram).
  * Ensure the in-memory cache dictionary is thread-safe (e.g., protected by a `threading.Lock()` or using thread-safe atomic operations) so that simultaneous reads and writes never corrupt TTL or mapping states.
  * Demonstrate 2 clients querying the resolver at the exact same instant during the live demo.

---

## 2. Formal Protocol Specification & State Machines (Criterion 1: 8–10 Marks)
* **The Rubric Expectation:**
  > *"A precise specification that another group could implement from, including status and error codes. The encapsulation analysis relates each captured header to the layered model and explains what that layer contributed."*
* **The Pitfall:**
  Merely displaying the struct header diagram is not enough for top marks. The evaluators require a comprehensive formal protocol RFC.
* **The Engineering Fix:**
  * Include a complete **Message Exchange Sequence Diagram** for:
    1. **Cache Hit:** Client $\rightarrow$ Resolver $\rightarrow$ Client.
    2. **Cache Miss:** Client $\rightarrow$ Resolver $\rightarrow$ Authoritative Server $\rightarrow$ Resolver $\rightarrow$ Client.
    3. **Domain Not Found (`NXDOMAIN`):** Client $\rightarrow$ Resolver $\rightarrow$ Auth $\rightarrow$ Resolver (NXDOMAIN) $\rightarrow$ Client.
    4. **Server Failure / Timeout:** Client $\rightarrow$ Resolver $\rightarrow$ (Auth down) $\rightarrow$ Resolver retry timeout $\rightarrow$ Resolver sends `SERVER_FAILURE` to Client.
  * Include a **Protocol State Transition Table** for both Client and Resolver.
  * In the Wireshark packet analysis, explicitly document the byte offset and purpose of every header field across the 4 layers:
    * Layer 2 (Ethernet II): Preamble, Source/Destination MAC, EtherType (`0x0800`).
    * Layer 3 (IPv4): Version, IHL, Total Length, TTL, Protocol (`17` for UDP), Source/Destination IP.
    * Layer 4 (UDP): Source Port, Destination Port, Length, Checksum.
    * Layer 7 (`MYDNS/1.0`): Transaction ID (16-bit), Flags/Type (8-bit), Query Type (8-bit), Status (8-bit), Padding (8-bit), TTL (16-bit), Domain Length, Domain Name, IPv4 Address.

---

## 3. Empirical Measurement Rigor, Spread & Delay Modeling (Criterion 3: 8–10 Marks)
* **The Rubric Expectation:**
  > *"Measurements are repeated and averaged across at least two conditions, presented in a table and a graph, and explained using the delay model... the analysis is genuinely critical. Anomalies in the data are noticed and explained rather than hidden, trade-offs are resolved by reference to the group's own numbers, and the limitations of the measurement method are acknowledged."*
* **The Pitfall:**
  Presenting only average RTTs without variance, or fabricating smooth theoretical numbers that don't reflect real-world network fluctuations.
* **The Engineering Fix:**
  * Run **$\ge 5$ automated trials** (e.g., 10 to 20 trials) for both Cache Hit and Cache Miss.
  * Report:
    * Minimum ($RTT_{min}$), Maximum ($RTT_{max}$), Arithmetic Mean ($\mu$), and Sample Standard Deviation ($\sigma$ / spread).
  * Present results in:
    * **Table:** Raw trials + statistical aggregates.
    * **Graph:** Bar chart with standard deviation error bars, or a line plot of trial vs. RTT comparing Miss vs. Hit.
  * Map directly to the Lecture 02 Nodal Delay equation:
    $$T_{nodal} = d_{proc} + d_{queue} + d_{trans} + d_{prop}$$
    * Explain that for a Cache Hit, $d_{prop}$ and $d_{trans}$ on the Resolver-to-Authoritative link are completely eliminated ($0\text{ ms}$), and $d_{proc}$ is simply an in-memory dictionary lookup ($\approx \mu\text{s}$).
  * **Critical Analysis of Anomalies:** Notice and explain why Trial 1 (cold start) or sporadic Wi-Fi retransmissions cause high latency spikes (e.g., ARP resolution delay on initial packet, OS timer quantum, or CSMA/CA backoff on wireless links).

---

## 4. Realistic Population Scaling & Energy Modeling (Criterion 4: 8–10 Marks)
* **The Rubric Expectation:**
  > *"Quantifies the bytes saved by a specific design choice such as caching... projects the saving to a realistic population of users, reasons about the bandwidth and energy implications at scale, and states the assumptions behind the projection honestly."*
* **The Pitfall:**
  Vague claims such as "caching saves green energy and reduces carbon footprints."
* **The Engineering Fix:**
  * **Exact Byte Arithmetic:**
    * Cache Miss query exchange: 4 packets total (Client $\rightarrow$ Resolver, Resolver $\rightarrow$ Auth, Auth $\rightarrow$ Resolver, Resolver $\rightarrow$ Client) $\approx 4 \times (14\text{ Ethernet} + 20\text{ IP} + 8\text{ UDP} + 25\text{ MYDNS payload}) = 268\text{ bytes}$ on the wire.
    * Cache Hit query exchange: 2 packets total (Client $\rightarrow$ Resolver, Resolver $\rightarrow$ Client) $\approx 2 \times 67\text{ bytes} = 134\text{ bytes}$.
    * **Net Wire Saving:** $134\text{ bytes}$ per query (**$50\%$ bandwidth reduction**).
  * **Campus Population Projection (NED University Case Study):**
    * *Assumptions stated honestly:*
      * Active campus population: $12,000$ students/faculty.
      * Average user device queries: $60$ DNS lookups/day during campus hours.
      * Expected cache hit ratio: $80\%$ (industry-standard DNS cache behavior for common services like Google, Moodle, LMS).
    * *Daily Traffic Calculation:*
      * Total daily queries $= 12,000 \times 60 = 720,000\text{ queries/day}$.
      * Without Caching (100% Misses): $720,000 \times 268\text{ bytes} \approx 192.96\text{ MB/day}$.
      * With 80% Cache Hits:
        * $144,000\text{ Misses} \times 268\text{ bytes} = 38.59\text{ MB}$.
        * $576,000\text{ Hits} \times 134\text{ bytes} = 77.18\text{ MB}$.
        * Total with Caching $= 115.77\text{ MB/day}$.
      * **Net Campus Wire Savings:** $\approx 77.19\text{ MB/day} \approx 2.31\text{ GB/month}$ on the local network infrastructure.
    * *Energy & Infrastructure Implications:*
      * Reduced processing interrupts on the core campus router and authoritative server NICs.
      * Decreased buffer queue occupancy ($d_{queue} \rightarrow 0$), preventing packet drops and power-hungry retransmission cycles.

---

## 5. Report Quality & Submission Rules Checklist (Criterion 5)
* [ ] **Rubric Title Page:** Attach the provided official grading rubric page as the exact cover page with names, roll numbers, and group number filled in. (No custom title page).
* [ ] **Strict Page Limit:** Body of report must be $\le 10$ pages (excluding rubric title page, references, and code appendix).
* [ ] **Typography:** Times New Roman, font size 12 for body text, 14 for headings.
* [ ] **Network Diagram & IP Plan:** Clearly labelled diagram with actual IP configurations (`ipconfig` / `ip addr` screenshots).
* [ ] **Signed Contributions Table:** Complete table detailing the exact contribution of each group member, signed by all 3 members.
* [ ] **AI Assistance Declaration Appendix:** Transparent statement detailing how AI tools (e.g., Gemini) were utilized during the project.
* [ ] **PDF Naming Convention:** Name the online PDF file `CS24XXX.pdf` using the student's roll number (e.g., `CS24082.pdf`).

