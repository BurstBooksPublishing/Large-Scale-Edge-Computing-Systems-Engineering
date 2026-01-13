package main

import (
        "context"
        "crypto/tls"
        "log"
        "os"
        "os/signal"
        "time"

        mqtt "github.com/eclipse/paho.mqtt.golang"
        "github.com/Shopify/sarama"
)

// configuration constants tuned per-device/class
const (
        BufferSize    = 200000            // bounded event buffer
        MaxBatchSize  = 1000              // events per batch
        BatchWait     = 50 * time.Millisecond // max wait to flush batch
        KafkaTimeout  = 5 * time.Second
        MqttBrokerURL = "tcp://127.0.0.1:1883"
        KafkaBrokers  = "kafka-1:9092,kafka-2:9092"
        Topic         = "edge-telemetry"
)

func main() {
        // context and signal handling
        ctx, cancel := context.WithCancel(context.Background())
        defer cancel()
        sig := make(chan os.Signal, 1)
        go func(){ <-sig; cancel() }()

        // setup Kafka async producer with TLS and retries
        kcfg := sarama.NewConfig()
        kcfg.Producer.Return.Successes = false
        kcfg.Producer.Return.Errors = true
        kcfg.Producer.Flush.MaxMessages = MaxBatchSize
        kcfg.Net.DialTimeout = KafkaTimeout
        kcfg.Producer.RequiredAcks = sarama.WaitForLocal
        // optionally set TLS config for secure clusters
        kcfg.Net.TLS.Enable = false
        producer, err := sarama.NewAsyncProducer([]string{KafkaBrokers}, kcfg)
        if err != nil { log.Fatalf("kafka producer: %v", err) }
        defer producer.Close()

        // bounded channel implements backpressure
        events := make(chan []byte, BufferSize)

        // MQTT client options with small in-memory queue to avoid uncontrolled growth
        opts := mqtt.NewClientOptions().AddBroker(MqttBrokerURL).SetClientID("edge-ingest")
        opts.AutoReconnect = true
        opts.ConnectTimeout = 3 * time.Second
        mclient := mqtt.NewClient(opts)
        if token := mclient.Connect(); token.Wait() && token.Error() != nil {
                log.Fatalf("mqtt connect: %v", token.Error())
        }
        // subscribe and push into bounded channel; blocks when full
        if token := mclient.Subscribe("sensors/+/telemetry", 0, func(_ mqtt.Client, msg mqtt.Message) {
                // copy payload to avoid reuse by client
                payload := append([]byte(nil), msg.Payload()...)
                events <- payload // blocks when channel full: backpressure
        }); token.Wait() && token.Error() != nil {
                log.Fatalf("mqtt subscribe: %v", token.Error())
        }

        // batcher: collects events up to MaxBatchSize or BatchWait
        go func() {
                batch := make([][]byte, 0, MaxBatchSize)
                timer := time.NewTimer(BatchWait)
                defer timer.Stop()
                flush := func() {
                        if len(batch) == 0 { return }
                        // create sarama messages
                        for _, e := range batch {
                                producer.Input() <- &sarama.ProducerMessage{Topic: Topic, Value: sarama.ByteEncoder(e)}
                        }
                        batch = batch[:0]
                }
                for {
                        select {
                        case <-ctx.Done():
                                flush()
                                return
                        case e := <-events:
                                batch = append(batch, e)
                                if len(batch) >= MaxBatchSize {
                                        flush()
                                        timer.Reset(BatchWait)
                                }
                        case <-timer.C:
                                flush()
                                timer.Reset(BatchWait)
                        }
                }
        }()

        // monitor producer errors and log
        go func() {
                for err := range producer.Errors() {
                        log.Printf("producer error: %v", err)
                }
        }()

        // run until cancelled
        <-ctx.Done()
        mclient.Disconnect(250)
}