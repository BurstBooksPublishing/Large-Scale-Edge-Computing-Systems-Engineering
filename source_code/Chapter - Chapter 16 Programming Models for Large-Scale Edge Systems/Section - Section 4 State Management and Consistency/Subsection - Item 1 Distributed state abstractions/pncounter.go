package crdt

import (
        "encoding/json"
        "sync"
)

// PNCount holds positive and negative counts per node.
type PNCount struct {
        mu sync.Mutex
        // P and N track per-node counters; keys are node IDs.
        P map[string]uint64 `json:"p"`
        N map[string]uint64 `json:"n"`
}

// NewPN creates an initialized PN-Counter.
func NewPN() *PNCount {
        return &PNCount{P: make(map[string]uint64), N: make(map[string]uint64)}
}

// Inc increments this node's positive counter.
func (c *PNCount) Inc(node string, delta uint64) {
        c.mu.Lock()
        c.P[node] += delta
        c.mu.Unlock()
}

// Dec increments this node's negative counter.
func (c *PNCount) Dec(node string, delta uint64) {
        c.mu.Lock()
        c.N[node] += delta
        c.mu.Unlock()
}

// Value computes the current logical value.
func (c *PNCount) Value() int64 {
        c.mu.Lock()
        defer c.mu.Unlock()
        var pSum, nSum uint64
        for _, v := range c.P {
                pSum += v
        }
        for _, v := range c.N {
                nSum += v
        }
        return int64(pSum - nSum)
}

// Merge integrates remote state using element-wise max.
// This merge is associative, commutative, idempotent.
func (c *PNCount) Merge(remote *PNCount) {
        c.mu.Lock()
        defer c.mu.Unlock()
        for k, v := range remote.P {
                if cur, ok := c.P[k]; !ok || v > cur {
                        c.P[k] = v
                }
        }
        for k, v := range remote.N {
                if cur, ok := c.N[k]; !ok || v > cur {
                        c.N[k] = v
                }
        }
}

// Marshal serializes the state for network transport.
func (c *PNCount) Marshal() ([]byte, error) {
        c.mu.Lock()
        defer c.mu.Unlock()
        return json.Marshal(c)
}

// Unmarshal deserializes state from a peer and returns a PNCount.
func Unmarshal(data []byte) (*PNCount, error) {
        var p PNCount
        if err := json.Unmarshal(data, &p); err != nil {
                return nil, err
        }
        // Ensure maps are non-nil for safety.
        if p.P == nil {
                p.P = make(map[string]uint64)
        }
        if p.N == nil {
                p.N = make(map[string]uint64)
        }
        return &p, nil
}