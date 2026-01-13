package main

import (
        "context"
        "encoding/json"
        "log"
        "math"
        "net/http"
        "time"
)

// Production-ready safe defaults.
const (
        localInterval  = 1 * time.Millisecond   // fast local loop
        syncInterval   = 10 * time.Second      // slow global sync
        policyEndpoint = "https://region-control.example/api/policy"
        maxBackoff     = 60 * time.Second
)

// Policy is the global reference payload.
type Policy struct {
        Ref   float64 `json:"ref"`
        Gain  float64 `json:"gain"`
        Valid bool    `json:"valid"`
}

func main() {
        ctx, cancel := context.WithCancel(context.Background())
        defer cancel()

        // Shared state between goroutines.
        policyCh := make(chan Policy, 1)
        policyCh <- Policy{Ref: 0.0, Gain: 0.5, Valid: true} // initial safe setpoint

        // Start async policy sync.
        go policySync(ctx, policyCh)

        // Local deterministic control loop.
        ticker := time.NewTicker(localInterval)
        defer ticker.Stop()
        var x float64 = 0.0 // process state
        for {
                select {
                case <-ctx.Done():
                        return
                case <-ticker.C:
                        p := latestPolicy(policyCh)
                        // Simple contractive update, safe-guard gain range.
                        alpha := math.Max(0.0, math.Min(p.Gain, 1.0))
                        x = (1-alpha)*x + alpha*p.Ref
                        // Actuate via hardware API (placeholder).
                        // writeActuator(x)
                        _ = x // in real code, send to DAC/PWM driver
                }
        }
}

// latestPolicy peeks the most recent policy without blocking.
func latestPolicy(ch chan Policy) Policy {
        select {
        case p := <-ch:
                // push back latest for future readers
                select {
                case ch <- p:
                default:
                }
                return p
        default:
                // return default safe policy if none available
                return Policy{Ref: 0.0, Gain: 0.1, Valid: false}
        }
}

// policySync fetches policy periodically with backoff and updates channel.
func policySync(ctx context.Context, ch chan<- Policy) {
        backoff := 1 * time.Second
        for {
                if err := fetchAndSend(ctx, ch); err != nil {
                        log.Printf("policy sync failed: %v, backing off %s", err, backoff)
                        select {
                        case <-time.After(backoff):
                                backoff = time.Duration(math.Min(float64(maxBackoff), float64(backoff)*2))
                        case <-ctx.Done():
                                return
                        }
                } else {
                        backoff = 1 * time.Second
                        select {
                        case <-time.After(syncInterval):
                        case <-ctx.Done():
                                return
                        }
                }
        }
}

func fetchAndSend(ctx context.Context, ch chan<- Policy) error {
        req, _ := http.NewRequestWithContext(ctx, "GET", policyEndpoint, nil)
        resp, err := http.DefaultClient.Do(req)
        if err != nil {
                return err
        }
        defer resp.Body.Close()
        var p Policy
        if err := json.NewDecoder(resp.Body).Decode(&p); err != nil {
                return err
        }
        // Validate policy ranges before applying.
        if p.Gain < 0 || p.Gain > 2 {
                p.Gain = math.Max(0.0, math.Min(p.Gain, 1.0))
        }
        select {
        case ch <- p:
        default:
                // keep most recent; drop if buffer full
        }
        return nil
}