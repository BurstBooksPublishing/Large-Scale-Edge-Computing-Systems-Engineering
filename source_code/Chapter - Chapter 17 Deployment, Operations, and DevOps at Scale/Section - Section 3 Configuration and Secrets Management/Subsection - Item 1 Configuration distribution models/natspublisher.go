package main

import (
  "crypto/ed25519"
  "crypto/rand"
  "log"
  "time"

  "github.com/nats-io/nats.go"
)

func sign(priv ed25519.PrivateKey, msg []byte) []byte {
  sig := ed25519.Sign(priv, msg)
  // payload = signature || message
  out := append(sig, msg...)
  return out
}

func main() {
  nc, err := nats.Connect(nats.DefaultURL)
  if err != nil { log.Fatal(err) }
  defer nc.Drain()

  // production: load keys from secure HSM/KMS; shown here ephemeral for clarity
  pub, priv, _ := ed25519.GenerateKey(rand.Reader)

  cfg := []byte(`{"threshold":42,"version":"2025-12-29"}`)
  payload := sign(priv, cfg)

  // publish with header metadata for replay/backoff policies if using JetStream
  if err := nc.Publish("configs.edge", payload); err != nil { log.Fatal(err) }
  log.Printf("published config signed by %x", pub[:6])

  time.Sleep(100 * time.Millisecond)
}