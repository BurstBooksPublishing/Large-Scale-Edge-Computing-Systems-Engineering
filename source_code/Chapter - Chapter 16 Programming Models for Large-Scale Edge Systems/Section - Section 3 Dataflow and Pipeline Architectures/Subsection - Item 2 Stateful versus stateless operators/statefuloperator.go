package main

import (
        "bytes"
        "context"
        "encoding/binary"
        "log"
        "net/http"
        "time"

        "github.com/dgraph-io/badger/v3" // embedded persistent state
)

// simple aggregator state per key: sum and count
type AggState struct{ Sum float64; Count uint64 }

func encode(s AggState) []byte {
        buf := new(bytes.Buffer)
        _ = binary.Write(buf, binary.LittleEndian, s.Sum)
        _ = binary.Write(buf, binary.LittleEndian, s.Count)
        return buf.Bytes()
}
func decode(b []byte) AggState {
        var s AggState
        buf := bytes.NewReader(b)
        _ = binary.Read(buf, binary.LittleEndian, &s.Sum)
        _ = binary.Read(buf, binary.LittleEndian, &s.Count)
        return s
}

func main() {
        // open local persistent store; suitable for ARM/SoC flash
        db, err := badger.Open(badger.DefaultOptions("/var/lib/edge_agg/badger"))
        if err != nil {
                log.Fatal(err)
        }
        defer db.Close()

        // event loop (replace with MQTT/Kafka consumer in production)
        events := make(chan struct {
                Key   string
                Value float64
        }, 1024)

        // snapshot checkpoint ticker
        checkpointTicker := time.NewTicker(30 * time.Second)
        ctx, cancel := context.WithCancel(context.Background())
        defer cancel()

        go func() {
                for {
                        select {
                        case ev := <-events:
                                // update aggregate atomically
                                err := db.Update(func(txn *badger.Txn) error {
                                        item, err := txn.Get([]byte(ev.Key))
                                        var s AggState
                                        if err == nil {
                                                val, _ := item.ValueCopy(nil)
                                                s = decode(val)
                                        }
                                        s.Sum += ev.Value
                                        s.Count++
                                        return txn.Set([]byte(ev.Key), encode(s))
                                })
                                if err != nil {
                                        log.Printf("state update error: %v", err)
                                }
                        case <-checkpointTicker.C:
                                // perform snapshot and upload (nonblocking)
                                go checkpointAndUpload(ctx, db, "https://aggregator.example/api/checkpoint")
                        case <-ctx.Done():
                                return
                        }
                }
        }()
        // production: replace with actual event ingestion
}

// create DB value snapshot and upload to remote checkpoint endpoint
func checkpointAndUpload(ctx context.Context, db *badger.DB, url string) {
        tmp := new(bytes.Buffer)
        // iterate DB to create snapshot (compact representation)
        _ = db.View(func(txn *badger.Txn) error {
                opts := badger.DefaultIteratorOptions
                it := txn.NewIterator(opts)
                defer it.Close()
                for it.Rewind(); it.Valid(); it.Next() {
                        item := it.Item()
                        k := item.KeyCopy(nil)
                        v, _ := item.ValueCopy(nil)
                        // simple length-prefixed key/value pairs
                        binary.Write(tmp, binary.LittleEndian, uint32(len(k)))
                        tmp.Write(k)
                        binary.Write(tmp, binary.LittleEndian, uint32(len(v)))
                        tmp.Write(v)
                }
                return nil
        })
        // upload snapshot with context deadline
        req, _ := http.NewRequestWithContext(ctx, "POST", url, bytes.NewReader(tmp.Bytes()))
        req.Header.Set("Content-Type", "application/octet-stream")
        client := http.Client{Timeout: 15 * time.Second}
        resp, err := client.Do(req)
        if err != nil {
                log.Printf("checkpoint upload failed: %v", err)
                return
        }
        resp.Body.Close()
}