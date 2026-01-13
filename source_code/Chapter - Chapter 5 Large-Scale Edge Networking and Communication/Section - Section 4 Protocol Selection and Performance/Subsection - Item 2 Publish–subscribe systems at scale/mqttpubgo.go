package main

import (
        "crypto/tls"
        "log"
        "time"

        mqtt "github.com/eclipse/paho.mqtt.golang"
)

func main() {
        tlsCfg := &tls.Config{MinVersion: tls.VersionTLS12}
        opts := mqtt.NewClientOptions().
                AddBroker("tls://edge-broker.example.com:8883").
                SetClientID("gateway-publisher-01").
                SetTLSConfig(tlsCfg).
                SetKeepAlive(30 * time.Second).
                SetAutoReconnect(true).
                SetConnectRetry(true).
                SetDefaultPublishHandler(func(client mqtt.Client, msg mqtt.Message) {})

        // Last Will to signal unexpected disconnects
        opts.SetWill("devices/gateway/status", "offline", 1, true)

        client := mqtt.NewClient(opts)
        if token := client.Connect(); token.Wait() && token.Error() != nil {
                log.Fatalf("connect error: %v", token.Error())
        }
        defer client.Disconnect(250)

        // publish loop with QoS 1 and persistence retry
        topic := "factory/line1/sensors"
        for i := 0; ; i++ {
                payload := []byte(fmt.Sprintf("{\"seq\":%d,\"ts\":%d}", i, time.Now().Unix()))
                token := client.Publish(topic, 1, false, payload) // QoS 1
                token.WaitTimeout(2 * time.Second)                // bound latency
                if token.Error() != nil {
                        log.Printf("publish failed: %v", token.Error())
                }
                time.Sleep(100 * time.Millisecond)
        }
}