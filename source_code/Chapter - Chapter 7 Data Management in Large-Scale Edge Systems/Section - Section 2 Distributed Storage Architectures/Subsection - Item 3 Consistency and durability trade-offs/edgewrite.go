package edgewrite

import (
        "bytes"
        "context"
        "encoding/json"
        "errors"
        "net/http"
        "sync"
        "time"

        badger "github.com/dgraph-io/badger/v3"
)

// DurabilityPolicy enumerates write durability options.
type DurabilityPolicy int
const (
        LocalSync DurabilityPolicy = iota
        RemoteSync    // wait for W remote acks
        AsyncReplicate
)

// WriteRequest holds data for a key write.
type WriteRequest struct {
        Key   string
        Value []byte
}

// WriteWithDurability writes key/value with selected policy.
// replicas: full HTTP endpoints of replica nodes.
// w: required ack count when using RemoteSync (includes local node).
func WriteWithDurability(ctx context.Context, db *badger.DB, req WriteRequest, policy DurabilityPolicy, replicas []string, w int) error {
        // local write and optional sync
        err := db.Update(func(txn *badger.Txn) error {
                // Set option SyncWrites=true when opening DB in production for durable writes.
                return txn.Set([]byte(req.Key), req.Value)
        })
        if err != nil {
                return err
        }

        // Force a local fsync if LocalSync or if RemoteSync must include local persistence.
        if policy == LocalSync || policy == RemoteSync {
                if err := db.Sync(); err != nil { // Badger DB.Sync flushes value log to disk.
                        return err
                }
        }

        switch policy {
        case LocalSync:
                return nil

        case RemoteSync:
                // include local ack as 1; need (w-1) remote acks.
                required := w - 1
                if required <= 0 {
                        return nil
                }
                // issue parallel POSTs and wait for required successes
                type result struct{ ok bool }
                resCh := make(chan result, len(replicas))
                var wg sync.WaitGroup
                client := &http.Client{Timeout: 2 * time.Second}
                ctx, cancel := context.WithTimeout(ctx, 5*time.Second) // overall deadline
                defer cancel()

                for _, url := range replicas {
                        wg.Add(1)
                        go func(u string) {
                                defer wg.Done()
                                body, _ := json.Marshal(req)
                                reqHttp, _ := http.NewRequestWithContext(ctx, "POST", u+"/replicate", bytes.NewReader(body))
                                reqHttp.Header.Set("Content-Type", "application/json")
                                resp, err := client.Do(reqHttp)
                                if err == nil && resp.StatusCode == http.StatusOK {
                                        resCh <- result{ok: true}
                                        resp.Body.Close()
                                        return
                                }
                                resCh <- result{ok: false}
                        }(url)
                }

                // collect results until required successes or exhausted
                successes := 0
                finished := make(chan struct{})
                go func() {
                        wg.Wait()
                        close(finished)
                }()
                for {
                        select {
                        case r := <-resCh:
                                if r.ok {
                                        successes++
                                        if successes >= required {
                                                return nil
                                        }
                                }
                        case <-finished:
                                if successes >= required {
                                        return nil
                                }
                                return errors.New("insufficient remote acknowledgements")
                        case <-ctx.Done():
                                return ctx.Err()
                        }
                }

        case AsyncReplicate:
                // background replication: spawn goroutine and return immediately.
                go func(req WriteRequest, replicas []string) {
                        client := &http.Client{Timeout: 2 * time.Second}
                        body, _ := json.Marshal(req)
                        for _, u := range replicas {
                                // Best-effort retry loop with backoff omitted for brevity.
                                _, _ = client.Post(u+"/replicate", "application/json", bytes.NewReader(body))
                        }
                }(req, replicas)
                return nil

        default:
                return errors.New("unsupported policy")
        }
}