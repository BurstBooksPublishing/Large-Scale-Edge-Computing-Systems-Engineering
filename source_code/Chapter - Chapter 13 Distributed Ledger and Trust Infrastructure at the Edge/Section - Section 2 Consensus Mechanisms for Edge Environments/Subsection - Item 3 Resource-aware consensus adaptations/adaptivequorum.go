package main

import (
        "context"
        "crypto/ed25519"
        "encoding/json"
        "log"
        "net/http"
        "sort"
        "time"

        "github.com/prometheus/client_golang/api"
        v1 "github.com/prometheus/client_golang/api/prometheus/v1"
)

// NodeMetrics holds normalized metrics for scoring.
type NodeMetrics struct {
        ID   string  `json:"id"`
        CPU  float64 `json:"cpu"`  // 0..1
        RTT  float64 `json:"rtt"`  // 0..1 (lower better)
        Eng  float64 `json:"eng"`  // 0..1
        Trust float64 `json:"trust"`
}

// SignedManifest is published to consensus clients.
type SignedManifest struct {
        Validators []string `json:"validators"`
        Ts         int64    `json:"ts"`
        Signature  []byte   `json:"sig"`
}

var (
        alpha, beta, gamma, delta = 0.4, 0.3, 0.2, 0.1
        privateKey ed25519.PrivateKey // load securely
        qMin       = 5                // example BFT quorum
)

func score(m NodeMetrics) float64 {
        return alpha*m.CPU + beta*(1.0-m.RTT) + gamma*m.Eng + delta*m.Trust
}

func fetchMetrics(promURL string) ([]NodeMetrics, error) {
        client, _ := api.NewClient(api.Config{Address: promURL})
        v1api := v1.NewAPI(client)
        ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
        defer cancel()
        // Query a combined vector; replace with real PromQL.
        result, _, err := v1api.Query(ctx, `node_metrics_vector`, time.Now())
        if err != nil {
                return nil, err
        }
        _ = result // map to NodeMetrics per deployment's metric exposition
        // Placeholder: in production parse samples into []NodeMetrics
        return []NodeMetrics{}, nil
}

func selectValidators(nodes []NodeMetrics) []string {
        type scored struct {
                id string; s float64; r float64
        }
        var arr []scored
        for _, n := range nodes {
                arr = append(arr, scored{n.ID, score(n), n.RTT})
        }
        // prefer high score, lower RTT as tiebreaker
        sort.Slice(arr, func(i,j int) bool {
                if arr[i].s==arr[j].s { return arr[i].r < arr[j].r }
                return arr[i].s>arr[j].s
        })
        var sel []string
        for i:=0; i
\section{Section 3: Blockchain Integration in Edge Systems}
\subsection{Item 1:  Lightweight node architectures}
Building on the resource-aware consensus adaptations and latency constraints discussed previously, lightweight node architectures intentionally reduce local state and compute to fit constrained edge platforms while preserving verifiability and interoperability with the broader ledger. The following develops design patterns, formal trade-offs, a concrete example, and deployment implications for edge-grade lightweight nodes.

Concept. Lightweight nodes perform a subset of ledger responsibilities. Common classes:
- Header-only light clients (SPV-style): store block headers and verify Merkle proofs for specific state or transactions.
- Verifier-agents: perform cryptographic validation of received proofs and forward requests to archive peers.
- Gateway / aggregation proxies: colocate with constrained sensors and expose a local API while performing remote validation.
- Trusted execution-backed nodes: run minimal verification inside TEEs (ARM TrustZone, OP-TEE, Intel SGX via OpenEnclave).

Design goals for the edge:
- Minimal persistent storage and CPU usage.
- Fast cold-start and bootstrap.
- Tolerance to intermittent connectivity.
- Strong authenticity and minimal trust assumptions (use of Merkle proofs, block headers, and attestations).

Theory. Let H be chain height and h the header size (bytes). Header-only storage S_headers scales linearly:
\begin{equation}[H]\label{eq:header_storage}
S_{\mathrm{headers}} \;=\; H \cdot h.
\end{equation}
For large public chains, pruning and snapshot checkpoints reduce S by a factor p (0
\subsection{Item 2:  Edge-to-ledger interaction patterns}
These interaction patterns build directly on lightweight node architectures, leveraging constrained end nodes and richer gateway nodes to bridge edge domains and ledgers. The patterns trade latency, bandwidth, and trust so system designers can choose a fit for industrial, telecom, or autonomous-platform constraints.

Edge-to-ledger interaction patterns — concept and theory
- Pattern taxonomy:
  1. Direct full node: an edge node runs a full ledger node (rare on constrained devices). Pros: maximal trust independence and on-device verification. Cons: large storage, CPU, and network overhead unsuitable for Cortex-M or many Cortex-A embedded SoCs.
  2. Light client (SPV / header-only): edge device verifies transactions using block headers and Merkle proofs. Works on devices running Linux or RTOS with occasional bursts. Requires header sync and cryptographic primitives; suitable for Cortex-A and high-end M-class devices.
  3. Gateway/aggregator proxy: constrained sensors (Zephyr/FreeRTOS on Cortex-M) forward events to an aggregator (Ubuntu Core on NXP i.MX or Jetson Xavier). The gateway batches, signs, and submits anchors or transactions to the ledger. This offloads consensus and heavy crypto.
  4. Anchor-only (commitment) pattern: only commitments (hashes) of local state are written on-chain. Full state stays off-chain, accessible via authenticated storage. This minimizes on-chain footprint and preserves privacy.
  5. State channels / sidechains: for repeated interactions among a fixed set of edge nodes, channels reduce on-chain operations to open/close events, providing low-latency local exchanges.
  6. Oracle/gatekeeper pattern: a trusted gateway publishes verified sensor attestations and feeds them to smart contracts or permissioned ledgers (Hyperledger Fabric chaincode). This is common in industrial telemetry.

- Latency and cost modeling:
  Decompose end-to-ledger latency for an event as
  \begin{equation}[H]\label{eq:latency_decomp}
  L = L_{proc} + L_{edge\rightarrow gw} + L_{gw\_batch} + L_{network} + L_{consensus}(f),
  \end{equation}
  where $L_{consensus}(f)$ grows with required finality confirmations $f$. When batching $n$ events into a single transaction, amortized cost per event is
  \begin{equation}[H]\label{eq:amortized_cost}
  C_{event} = \frac{C_{tx}+C_{sign}+C_{net}}{n} + C_{local}.
  \end{equation}
  Use these formulas to size batch interval versus acceptable $L$ and per-event cost. Higher $n$ reduces cost but increases $L$ and memory.

Example: anchoring industrial sensor logs
- Scenario: line PLCs produce high-frequency quality events. PLCs run small RTOS clients; a local gateway (NVIDIA Jetson or NXP i.MX8 running Ubuntu Core) collects events over CoAP/DTLS or MQTT with TLS, builds a Merkle root every T seconds, and anchors the root to an Ethereum-compatible permissioned chain (e.g., Quorum) or Hyperledger Fabric.
- Design choices:
  - Use TPM or HSM for gateway key protection; call PKCS#11 from gateway process.
  - Use libp2p or gRPC to communicate with cloud validators.
  - Configure batch interval T using equation (1) to meet worst-case latency SLA.

Practical implementation (production-ready gateway example)
- The listing is a compact asyncio-based gateway that:
  - collects events via MQTT,
  - builds a Merkle root,
  - signs and sends an Ethereum transaction using \lstinline|web3.py|.
\begin{lstlisting}[language=Python,caption={Edge gateway: batch, Merkle root, anchor to Ethereum-compatible ledger},label={lst:edge_anchor}]
import asyncio
import json
from hashlib import sha256
from web3 import Web3, HTTPProvider
from eth_account import Account

MQTT_BROKER = "mqtt.example.local"  # broker address
BATCH_SECONDS = 5
WEB3_URL = "https://node.example.local:8545"
PRIVATE_KEY = "0x..."               # store in TPM/HSM in production

w3 = Web3(HTTPProvider(WEB3_URL))
acct = Account.from_key(PRIVATE_KEY)

# Simple Merkle root computation
def merkle_root(leaves):
    if not leaves:
        return b'\x00' * 32
    nodes = [sha256(l.encode('utf-8')).digest() for l in leaves]
    while len(nodes) > 1:
        if len(nodes) % 2:
            nodes.append(nodes[-1])  # duplicate odd node
        nodes = [sha256(nodes[i] + nodes[i+1]).digest()
                 for i in range(0, len(nodes), 2)]
    return nodes[0]

# Placeholder: replace with actual MQTT client integration
async def collect_events(queue):
    while True:
        # receive an event from sensor gateway (application-specific)
        event = await asyncio.get_event_loop().run_in_executor(None, input)
        await queue.put(event.strip())

async def batch_and_anchor(queue):
    while True:
        await asyncio.sleep(BATCH_SECONDS)
        leaves = []
        while not queue.empty():
            leaves.append(await queue.get())
        if not leaves:
            continue
        root = merkle_root(leaves).hex()
        tx = {
            'to': acct.address,              # anchor contract or zero-address
            'value': 0,
            'data': Web3.toHex(text=root),
            'gas': 200000,
            'nonce': w3.eth.get_transaction_count(acct.address),
        }
        signed = acct.sign_transaction(tx)   # production: use HSM signing
        tx_hash = w3.eth.send_raw_transaction(signed.rawTransaction)
        print("Anchored", len(leaves), "events ->", tx_hash.hex())

async def main():
    queue = asyncio.Queue()
    await asyncio.gather(collect_events(queue), batch_and_anchor(queue))

if __name__ == "__main__":
    asyncio.run(main())