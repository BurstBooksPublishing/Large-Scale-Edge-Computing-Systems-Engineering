package state

import (
        "context"
        "errors"
        "time"
        "google.golang.org/grpc"
)

// VectorClock stores per-node counters.
type VectorClock map[string]uint64

// Versioned holds value and its vector clock.
type Versioned struct {
        Value []byte
        Clock VectorClock
}

// compare returns -1 if ab.
func compare(a, b VectorClock) int {
        less, greater := false, false
        for k := range mergeKeys(a,b) {
                av, bv := a[k], b[k]
                if av < bv { less = true }
                if av > bv { greater = true }
        }
        switch { case less && !greater: return -1; case !less && greater: return 1; default: return 0 }
}
func mergeKeys(a,b VectorClock) map[string]struct{} {
        keys := map[string]struct{}{}
        for k := range a { keys[k] = struct{}{} }
        for k := range b { keys[k] = struct{}{} }
        return keys
}

// QuorumRead performs parallel reads to endpoints, returns merged Versioned.
func QuorumRead(ctx context.Context, endpoints []string, readQuorum int, timeout time.Duration) (Versioned, error) {
        type resp struct { v Versioned; err error }
        ctx, cancel := context.WithTimeout(ctx, timeout); defer cancel()
        ch := make(chan resp, len(endpoints))

        for _, ep := range endpoints {
                go func(ep string) {
                        // per-call timeout
                        cctx, ccancel := context.WithTimeout(ctx, timeout/2); defer ccancel()
                        conn, err := grpc.DialContext(cctx, ep, grpc.WithBlock()) // configure TLS in DialOptions
                        if err != nil { ch <- resp{err: err}; return }
                        defer conn.Close()
                        client := NewStateServiceClient(conn) // generated gRPC client
                        r, err := client.ReadState(cctx, &ReadRequest{}) // service returns Value and VectorClock map
                        if err != nil { ch <- resp{err: err}; return }
                        ch <- resp{v: Versioned{Value: r.Value, Clock: r.Clock}}
                }(ep)
        }

        var collected []Versioned
        for i := 0; i < len(endpoints); i++ {
                select {
                case r := <-ch:
                        if r.err == nil { collected = append(collected, r.v) }
                        if len(collected) >= readQuorum { goto merge }
                case <-ctx.Done():
                        goto merge
                }
        }
merge:
        if len(collected) < readQuorum { return Versioned{}, errors.New("quorum not reached") }
        // merge using vector-clock dominance; if concurrent, return application-level merge or conflict.
        best := collected[0]
        for _, v := range collected[1:] {
                cmp := compare(best.Clock, v.Clock)
                if cmp == -1 { best = v }            // v dominates
                if cmp == 0 { best = resolve(best, v) } // merge concurrent
        }
        return best, nil
}

// resolve implements application-specific conflict resolution (e.g., merging CRDT payloads).
func resolve(a, b Versioned) Versioned { return a } // replace with real merge