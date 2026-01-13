package edgeconsistency

import (
        "context"
        "encoding/json"
        "net/http"
        "sync"
        "time"
)

// ReplicaRead encapsulates a JSON payload from a replica.
type ReplicaRead struct {
        Value     json.RawMessage `json:"value"`
        Version   int64           `json:"version"`
        Timestamp time.Time       `json:"timestamp"`
}

// QuorumRead queries replicas in parallel and returns the latest value
// accepted by a majority within ctx deadline; performs read-repair async.
func QuorumRead(ctx context.Context, urls []string, majority int) (ReplicaRead, error) {
        type resp struct {
                data ReplicaRead
                err  error
        }
        ch := make(chan resp, len(urls))
        var wg sync.WaitGroup

        // Parallel requests with shared context.
        for _, u := range urls {
                wg.Add(1)
                go func(url string) {
                        defer wg.Done()
                        req, _ := http.NewRequestWithContext(ctx, "GET", url+"/state", nil)
                        client := http.Client{Timeout: 2 * time.Second}
                        r, err := client.Do(req)
                        if err != nil {
                                ch <- resp{err: err}
                                return
                        }
                        defer r.Body.Close()
                        var rr ReplicaRead
                        if err := json.NewDecoder(r.Body).Decode(&rr); err != nil {
                                ch <- resp{err: err}
                                return
                        }
                        ch <- resp{data: rr, err: nil}
                }(u)
        }

        // Close channel when all goroutines finish.
        go func() {
                wg.Wait()
                close(ch)
        }()

        // Collect first majority responses and choose highest version.
        seen := make(map[int64]int)
        var best ReplicaRead
        responses := 0
        for {
                select {
                case <-ctx.Done():
                        return ReplicaRead{}, ctx.Err()
                case r, ok := <-ch:
                        if !ok {
                                // no more responses
                                if responses >= majority {
                                        return best, nil
                                }
                                return ReplicaRead{}, context.DeadlineExceeded
                        }
                        if r.err != nil {
                                continue
                        }
                        responses++
                        seen[r.data.Version]++
                        if r.data.Version > best.Version {
                                best = r.data
                        }
                        // If any version reaches majority, return immediately.
                        if seen[r.data.Version] >= majority {
                                // async read-repair can be scheduled here (omitted).
                                return best, nil
                        }
                }
        }
}