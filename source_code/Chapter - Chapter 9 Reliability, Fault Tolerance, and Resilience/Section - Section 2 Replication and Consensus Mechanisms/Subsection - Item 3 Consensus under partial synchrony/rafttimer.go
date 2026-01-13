package consensus

import (
        "context"
        "log"
        "math/rand"
        "sync/atomic"
        "time"
)

// Transport abstracts sending RPCs; implement with gRPC/libp2p/UDP.
type Transport interface {
        SendHeartbeat(ctx context.Context, to string, leaderID string) error
        RequestVote(ctx context.Context, to string, term uint64) (granted bool, err error)
}

// NodeID type for clarity.
type NodeID string

// Node encapsulates minimal state needed for elections.
type Node struct {
        id        NodeID
        peers     []string
        transport Transport
        term      uint64
        leader    atomic.Value // holds NodeID
        ctx       context.Context
        cancel    context.CancelFunc
}

// NewNode constructs node; transport must be provided.
func NewNode(id NodeID, peers []string, transport Transport) *Node {
        ctx, cancel := context.WithCancel(context.Background())
        n := &Node{id: id, peers: peers, transport: transport, ctx: ctx, cancel: cancel}
        n.leader.Store(NodeID(""))
        return n
}

// startElectionTimer runs adaptive elections with jitter.
func (n *Node) startElectionTimer(base time.Duration) {
        go func() {
                r := rand.New(rand.NewSource(time.Now().UnixNano()))
                for {
                        select {
                        case <-n.ctx.Done():
                                return
                        case <-time.After(base + time.Duration(r.Int63n(int64(base/2)))):
                                // Trigger election in separate goroutine to avoid blocking timer.
                                go n.initiateElection()
                                // Exponential backoff on repeated failures can be added here.
                        }
                }
        }()
}

// initiateElection implements a simple RequestVote phase.
func (n *Node) initiateElection() {
        // increase term
        term := atomic.AddUint64(&n.term, 1)
        grants := 1 // self-vote
        ctx, cancel := context.WithTimeout(n.ctx, 2*time.Second)
        defer cancel()
        for _, p := range n.peers {
                grant, err := n.transport.RequestVote(ctx, p, term)
                if err != nil {
                        log.Printf("vote request to %s failed: %v", p, err)
                        continue
                }
                if grant {
                        grants++
                }
        }
        // majority check (n is peers+1)
        if grants*2 > len(n.peers)+1 {
                n.leader.Store(n.id)
                log.Printf("node %s became leader term=%d", n.id, term)
                // start heartbeat loop (implementation omitted for brevity).
        }
}

// Shutdown stops timers and background work.
func (n *Node) Shutdown() { n.cancel() }