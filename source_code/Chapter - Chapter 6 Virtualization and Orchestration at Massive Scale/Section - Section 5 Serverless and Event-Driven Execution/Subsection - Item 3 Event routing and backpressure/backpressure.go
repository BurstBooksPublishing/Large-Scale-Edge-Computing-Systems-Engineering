package main

import (
        "context"
        "log"
        "sync/atomic"
        "time"

        "github.com/nats-io/nats.go"
)

// per-target state
type Target struct {
        topic     string
        credits   int64 // atomic
        maxCredits int64
}

// decrement returns true if allowed, false if no credit
func (t *Target) allow() bool {
        for {
                c := atomic.LoadInt64(&t.credits)
                if c <= 0 { return false }
                if atomic.CompareAndSwapInt64(&t.credits, c, c-1) { return true }
        }
}

// refill loop replenishes credits proportional to capacity
func (t *Target) refill(rate int64, period time.Duration) {
        ticker := time.NewTicker(period)
        for range ticker.C {
                atomic.AddInt64(&t.credits, rate)
                // cap at maxCredits
                if atomic.LoadInt64(&t.credits) > t.maxCredits {
                        atomic.StoreInt64(&t.credits, t.maxCredits)
                }
        }
}

func main() {
        // NATS connection to edge broker; use TLS in production
        nc, _ := nats.Connect(nats.DefaultURL)
        js, _ := nc.JetStream()

        // target map: local functions and cloud spill topic
        targets := map[string]*Target{
                "jetson-1": {topic: "fn.jetson-1", credits: 100, maxCredits: 100},
                "jetson-2": {topic: "fn.jetson-2", credits: 50, maxCredits: 50}, // lower capacity
        }
        // start refillers
        for _, t := range targets {
                go t.refill(t.maxCredits/10, 100*time.Millisecond) // configurable
        }

        sub, _ := nc.Subscribe("sensors.>", func(m *nats.Msg) {
                ctx, cancel := context.WithTimeout(context.Background(), 50*time.Millisecond)
                defer cancel()

                // simple partition key: device id in subject part 2
                parts := nats.SplitSubject(m.Subject)
                key := parts[1] // safe for known subjects

                // choose target by simple map (replace with weighted consistent hash)
                target := targets["jetson-1"]
                if key == "machineB" { target = targets["jetson-2"] }

                // apply credit-based backpressure
                if target.allow() {
                        // publish to local function topic; non-blocking with context
                        _, err := js.PublishAsync(target.topic, m.Data, nats.Context(ctx))
                        if err != nil {
                                log.Printf("publish fail: %v", err)
                        }
                        return
                }

                // spillover: forward to regional cloud topic for batch processing
                if err := nc.Publish("cloud.spill", m.Data); err != nil {
                        log.Printf("spill publish fail: %v", err)
                }
        })
        _ = sub

        // keep running
        select {}
}