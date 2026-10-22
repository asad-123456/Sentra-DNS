# Member 1 Module Guide: Client Engine, Benchmarking & Delay Modeling
**Lead:** Asadullah Zafar (`CS-24082`)  
**Core Responsibilities:**
1. Client Query Engine & Retransmission Timers (`src/client.py`)
2. Automated Multi-Trial Benchmarking Suite (`tests/benchmark_runner.py`)
3. Statistical Profiling: Minimum, Maximum, Mean ($\mu$), and Spread / Standard Deviation ($\sigma$)
4. Mathematical Delay Modeling (Lecture 02 $T_{nodal}$) & Sustainability Analysis (CLO-3)

---

## 1. Technical Overview & Role in the System
As Member 1, your module is the **face of the application and the evaluation driver**. You initiate queries, enforce reliable delivery over unreliable UDP, capture high-precision microsecond timestamps, collect the empirical evidence for the final report, and calculate the sustainability benefits.

```
+------------------------------------+
|           HOST 1: CLIENT           |
|   (Asadullah Zafar's Core Module)  |
|                                    |
| 1. High-precision RTT Profiler     |
| 2. Stop-and-Wait Retransmit Timer  |
| 3. Automated 10-Trial Benchmark    |
| 4. Matplotlib Graph Generator      |
+------------------------------------+
                  |
                  | Query (UDP 53000)
                  v
       [ HOST 2: RESOLVER ]
```

---

## 2. Client Query Engine (`src/client.py`)

### Requirements
* Accept command-line arguments: `--resolver-ip`, `--resolver-port` (default 53000), `--domain`.
* Generate a random 16-bit Transaction ID (`os.urandom(2)`).
* Measure round-trip time with microsecond accuracy using `time.perf_counter()`.
* Implement **stop-and-wait timeout and retransmission**:
  ```python
  import socket
  import time
  import random
  from protocol import MYDNSMessage, MSG_QUERY, TYPE_A

  def query_domain(resolver_ip: str, resolver_port: int, domain: str, timeout: float = 1.5, max_retries: int = 3):
      sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
      sock.settimeout(timeout)
      
      tx_id = random.randint(1, 65535)
      msg = MYDNSMessage(tx_id=tx_id, msg_type=MSG_QUERY, query_type=TYPE_A, domain=domain)
      packet = msg.pack()
      
      for attempt in range(1, max_retries + 1):
          try:
              t_start = time.perf_counter()
              sock.sendto(packet, (resolver_ip, resolver_port))
              data, addr = sock.recvfrom(512)
              t_end = time.perf_counter()
              
              rtt_ms = (t_end - t_start) * 1000.0
              response = MYDNSMessage.unpack(data)
              
              # Verify Transaction ID matching
              if response.tx_id != tx_id:
                  continue
                  
              return response, rtt_ms
          except socket.timeout:
              print(f"[CLIENT WARN] Attempt {attempt} timed out after {timeout}s. Retrying...")
              
      sock.close()
      raise TimeoutError(f"Query for {domain} failed after {max_retries} attempts.")
  ```

---

## 3. Automated Benchmarking Suite (`tests/benchmark_runner.py`)

Rubric Criterion 3 requires: *"Measurements are repeated and averaged across at least two conditions, presented in a table and a graph, and explained using the delay model... Anomalies in the data are noticed and explained rather than hidden."*

### Implementation Workflow
1. Run **$\ge 5$ consecutive trials** (recommend 10 trials) for:
   * **Condition A (Cache Miss):** Query a new un-cached domain or query after TTL expiry.
   * **Condition B (Cache Hit):** Query the same domain immediately while cached.
2. For each condition, record individual trial RTTs:
   * Compute **Mean ($\mu$)**: $\mu = \frac{1}{N} \sum_{i=1}^N RTT_i$
   * Compute **Sample Standard Deviation ($\sigma$ / spread)**: $\sigma = \sqrt{\frac{1}{N-1}\sum_{i=1}^N (RTT_i - \mu)^2}$
   * Record **Min** and **Max** to capture network jitter.
3. Automatically generate a high-resolution comparison chart using `matplotlib` and save it as `gemini-docs/rtt_benchmark_plot.png`.

---

## 4. Analytical Delay Modeling ($T_{nodal}$)

In Section 6 of your final report, you must explain your empirical numbers using the Lecture 02 Nodal Delay equation:
$$T_{nodal} = d_{proc} + d_{queue} + d_{trans} + d_{prop}$$

### Deconstructing Cache Miss vs. Cache Hit
1. **Cache Miss Traversal:**
   $$RTT_{miss} = 2 \cdot (d_{prop,1} + d_{trans,1}) + 2 \cdot (d_{prop,2} + d_{trans,2}) + d_{proc,res} + d_{proc,auth} + d_{queue}$$
   * Packets traverse two physical network links twice (Client $\rightarrow$ Resolver $\rightarrow$ Auth $\rightarrow$ Resolver $\rightarrow$ Client).
2. **Cache Hit Traversal:**
   $$RTT_{hit} = 2 \cdot (d_{prop,1} + d_{trans,1}) + d_{proc,cache}$$
   * The second link traversal (Resolver $\leftrightarrow$ Auth) is completely bypassed.
   * $d_{proc,cache}$ is an $O(1)$ memory hash table lookup, taking $< 5\,\mu\text{s}$.
3. **Explaining Empirical Anomalies:**
   * In Trial 1, RTT is noticeably higher due to **cold start ARP resolution** (resolving MAC addresses) and OS socket allocation. Acknowledge this honestly in the report for Level 4 marks!

---

## 5. Sustainability & Scaled Efficiency Model (Section 7)

Quantify the environmental and network efficiency:
* **Byte Reduction Arithmetic:**
  * Cache Miss Exchange: 4 packets $\approx 268\text{ bytes}$ on the wire.
  * Cache Hit Exchange: 2 packets $\approx 134\text{ bytes}$ on the wire.
  * Direct Wire Traffic Reduction: **50%**.
* **Campus Scale (NED University Projections):**
  * $12,000$ active students/staff $\times 60$ daily DNS requests $= 720,000$ queries/day.
  * With an $80\%$ cache hit ratio:
    * Misses ($20\%$): $144,000 \times 268\text{ bytes} = 38.59\text{ MB}$.
    * Hits ($80\%$): $576,000 \times 134\text{ bytes} = 77.18\text{ MB}$.
    * Total with Caching: $115.77\text{ MB/day}$ vs. $192.96\text{ MB/day}$ without caching.
    * **Net Daily Saving:** $\approx 77.19\text{ MB/day}$ ($\approx 2.31\text{ GB/month}$) on the campus distribution link.
* **Energy Impact:**
  * Less packet buffering on edge switch interfaces lowers device operating temperatures and eliminates wasted retransmission energy caused by buffer bloat.

---

## 6. Getting Started Checklist
- [ ] Review `src/protocol.py` written by Member 3.
- [ ] Implement `src/client.py` with CLI arguments and timeout retransmissions.
- [ ] Implement `tests/benchmark_runner.py` with statistical calculations and `matplotlib` plotting.
- [ ] Run test queries against Member 2's resolver.
- [ ] Gather 10-trial benchmark data for both Cache Hit and Cache Miss.
- [ ] Generate graphs and verify statistical spread.

