package main

import (
    "log"
    "time"
    "github.com/nats-io/nats.go"
)

func main() {
    nc, err := nats.Connect(nats.DefaultURL) // production: use creds and TLS
    if err != nil { log.Fatal(err) }
    js, err := nc.JetStream() // durable stream use
    if err != nil { log.Fatal(err) }

    // Publisher: attach minimal provenance and trace headers.
    publish := func(subject string, data []byte) {
        m := nats.NewMsg(subject)
        m.Header.Set("Device-ID","sensor-42")                   // short id
        m.Header.Set("Seq","000123")                            // monotonic sequence
        m.Header.Set("Traceparent","00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01") // W3C
        m.Header.Set("Semantic-Type","temperature.celsius")
        m.Data = data
        if _, err := js.PublishMsg(m); err != nil { log.Println("pub err", err) }
    }

    // Subscriber: reads headers, appends local provenance, and forwards.
    _, err = nc.Subscribe("sensors.>", func(msg *nats.Msg) {
        // Read and validate headers; add gateway provenance.
        device := msg.Header.Get("Device-ID")
        seq := msg.Header.Get("Seq")
        // Minimal validation and audit log entry.
        log.Printf("recv %s seq=%s", device, seq)
        // Append gateway provenance header and forward to regional subject.
        forward := nats.NewMsg("regional."+msg.Subject)
        for k, v := range msg.Header {
            for _, val := range v { forward.Header.Add(k, val) }
        }
        forward.Header.Add("Gateway-ID", "gw-nyc-1")
        forward.Header.Add("Gateway-Ts", time.Now().UTC().Format(time.RFC3339Nano))
        forward.Data = msg.Data
        if err := nc.PublishMsg(forward); err != nil { log.Println("forward err", err) }
    })
    if err != nil { log.Fatal(err) }

    select {} // run forever
}