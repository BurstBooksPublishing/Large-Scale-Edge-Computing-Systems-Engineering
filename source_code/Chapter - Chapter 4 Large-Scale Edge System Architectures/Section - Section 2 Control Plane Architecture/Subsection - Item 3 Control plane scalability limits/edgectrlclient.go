package main

import (
        "context"
        "encoding/json"
        "log"
        "math/rand"
        "net/http"
        "sync"
        "time"

        "golang.org/x/time/rate"
)

// production-ready constants
const (
        controllerURL = "https://controller.example.local/v1/heartbeat"
        maxBurst      = 5
        ratePerSec    = 0.5 // heartbeat tokens per second
)

type Heartbeat struct {
        NodeID    string `json:"node_id"`
        Timestamp int64  `json:"ts"`
        Metrics   map[string]any `json:"metrics"`
}

func sendHeartbeat(ctx context.Context, client *http.Client, h Heartbeat) error {
        body, _ := json.Marshal(h)
        req, _ := http.NewRequestWithContext(ctx, http.MethodPost, controllerURL, bytes.NewReader(body))
        req.Header.Set("Content-Type", "application/json")
        resp, err := client.Do(req)
        if err != nil {
                return err
        }
        resp.Body.Close()
        if resp.StatusCode >= 500 {
                return fmt.Errorf("server error: %d", resp.StatusCode)
        }
        return nil
}

func worker(ctx context.Context, wg *sync.WaitGroup, limiter *rate.Limiter, client *http.Client, nodeID string) {
        defer wg.Done()
        backoffBase := 200 * time.Millisecond
        for {
                if err := limiter.Wait(ctx); err != nil { // token bucket blocks
                        return
                }
                h := Heartbeat{NodeID: nodeID, Timestamp: time.Now().Unix(), Metrics: map[string]any{"cpu": 0.1}}
                // retry with exponential backoff and jitter
                var attempt int
                for {
                        attempt++
                        err := sendHeartbeat(ctx, client, h)
                        if err == nil {
                                break
                        }
                        // simple backoff with jitter
                        sleep := backoffBase * (1 << (attempt - 1))
                        sleep = sleep + time.Duration(rand.Int63n(int64(sleep/2)))
                        select {
                        case <-time.After(sleep):
                                continue
                        case <-ctx.Done():
                                return
                        }
                }
        }
}

func main() {
        ctx, cancel := context.WithCancel(context.Background())
        defer cancel()
        limiter := rate.NewLimiter(rate.Limit(ratePerSec), maxBurst)
        client := &http.Client{Timeout: 5 * time.Second}
        var wg sync.WaitGroup
        wg.Add(1)
        go worker(ctx, &wg, limiter, client, "edge-node-42")
        // run until signaled; omitted signal handling for brevity
        time.Sleep(10 * time.Minute)
        cancel()
        wg.Wait()
}