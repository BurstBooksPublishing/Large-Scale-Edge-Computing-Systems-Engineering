package quorum

import (
        "context"
        "net/http"
        "sync"
        "time"
)

// Client represents a quorum client against N replicas.
type Client struct {
        Replicas []string       // replica base URLs
        HTTP     *http.Client   // configured with timeouts, keep-alive
        R, W     int            // read and write quorum sizes
}

// Write sends write requests to all replicas and waits for W successes.
func (c *Client) Write(ctx context.Context, path string, body []byte) error {
        ctx, cancel := context.WithTimeout(ctx, 2*time.Second) // overall write timeout
        defer cancel()
        type res struct{ err error }
        ch := make(chan res, len(c.Replicas))
        var wg sync.WaitGroup
        for _, r := range c.Replicas {
                wg.Add(1)
                go func(url string) {
                        defer wg.Done()
                        req, _ := http.NewRequestWithContext(ctx, "POST", url+path, bytes.NewReader(body))
                        // short per-request timeout
                        resp, err := c.HTTP.Do(req)
                        if err == nil { resp.Body.Close() }
                        ch <- res{err: err}
                }(r)
        }
        // collect responses until W successes or timeout
        success := 0
        failures := 0
        for i := 0; i < len(c.Replicas); i++ {
                select {
                case r := <-ch:
                        if r.err == nil { success++ } else { failures++ }
                        if success >= c.W {
                                // drain goroutines and return
                                go func(){ wg.Wait(); close(ch) }()
                                return nil
                        }
                        if failures > len(c.Replicas)-c.W {
                                go func(){ wg.Wait(); close(ch) }()
                                return fmt.Errorf("write quorum failed")
                        }
                case <-ctx.Done():
                        go func(){ wg.Wait(); close(ch) }()
                        return ctx.Err()
                }
        }
        return fmt.Errorf("write incomplete")
}