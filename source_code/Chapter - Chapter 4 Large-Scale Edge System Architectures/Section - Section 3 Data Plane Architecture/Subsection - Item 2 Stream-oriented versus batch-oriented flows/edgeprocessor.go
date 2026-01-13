package main

import (
        "context"
        "encoding/json"
        "flag"
        "log"
        "os"
        "os/signal"
        "sync"
        "syscall"
        "time"

        mqtt "github.com/eclipse/paho.mqtt.golang"
        "github.com/nats-io/nats.go"
)

var (
        mode      = flag.String("mode", "stream", "stream or batch")
        batchWin  = flag.Duration("batch-window", 5*time.Second, "batch window duration")
        mqttBroker = flag.String("mqtt", "tcp://localhost:1883", "MQTT broker URL")
        natsURL   = flag.String("nats", nats.DefaultURL, "NATS server URL")
        topic     = flag.String("topic", "sensors/+", "MQTT topic")
)

type Event struct {
        DeviceID string  `json:"device_id"`
        Ts       int64   `json:"ts"`
        Value    float64 `json:"value"`
}

func main() {
        flag.Parse()
        ctx, cancel := context.WithCancel(context.Background())
        defer cancel()

        // graceful shutdown
        sig := make(chan os.Signal, 1)
        signal.Notify(sig, syscall.SIGINT, syscall.SIGTERM)
        go func() {
                <-sig
                cancel()
        }()

        // connect to MQTT
        opts := mqtt.NewClientOptions().AddBroker(*mqttBroker).SetClientID("edge-processor")
        mc := mqtt.NewClient(opts)
        if token := mc.Connect(); token.Wait() && token.Error() != nil {
                log.Fatalf("mqtt connect: %v", token.Error())
        }
        defer mc.Disconnect(250)

        // connect to NATS for downstream
        nc, err := nats.Connect(*natsURL, nats.Name("edge-processor"))
        if err != nil {
                log.Fatalf("nats connect: %v", err)
        }
        defer nc.Close()

        events := make(chan Event, 1024)
        var wg sync.WaitGroup

        // MQTT handler pushes into channel
        if token := mc.Subscribe(*topic, 1, func(_ mqtt.Client, msg mqtt.Message) {
                var e Event
                if err := json.Unmarshal(msg.Payload(), &e); err != nil {
                        // drop malformed messages
                        return
                }
                select {
                case events <- e:
                default:
                        // backpressure: drop or apply other policy
                }
        }); token.Wait() && token.Error() != nil {
                log.Fatalf("subscribe: %v", token.Error())
        }

        // processing goroutine(s)
        wg.Add(1)
        go func() {
                defer wg.Done()
                if *mode == "stream" {
                        streamLoop(ctx, events, nc)
                } else {
                        batchLoop(ctx, events, nc, *batchWin)
                }
        }()

        <-ctx.Done()
        close(events)
        wg.Wait()
}

// process each event immediately
func streamLoop(ctx context.Context, in <-chan Event, nc *nats.Conn) {
        for {
                select {
                case <-ctx.Done():
                        return
                case e, ok := <-in:
                        if !ok {
                                return
                        }
                        // lightweight inference or filtering here
                        b, _ := json.Marshal(e)
                        _ = nc.Publish("edge.stream", b) // fire-and-forget
                }
        }
}

// accumulate windows and publish batches
func batchLoop(ctx context.Context, in <-chan Event, nc *nats.Conn, win time.Duration) {
        ticker := time.NewTicker(win)
        defer ticker.Stop()
        var batch []Event
        for {
                select {
                case <-ctx.Done():
                        flushBatch(nc, batch)
                        return
                case e, ok := <-in:
                        if !ok {
                                flushBatch(nc, batch)
                                return
                        }
                        batch = append(batch, e)
                case <-ticker.C:
                        if len(batch) > 0 {
                                flushBatch(nc, batch)
                                batch = nil
                        }
                }
        }
}

func flushBatch(nc *nats.Conn, batch []Event) {
        if len(batch) == 0 {
                return
        }
        b, _ := json.Marshal(batch)
        // durable publish or push to Kafka connector in production
        _ = nc.Publish("edge.batch", b)
}