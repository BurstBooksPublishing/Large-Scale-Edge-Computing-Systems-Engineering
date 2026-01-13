package main

import (
  "encoding/json"
  "log"
  "net/http"
  "os"
  "time"

  "github.com/boltdb/bolt"           // embed local KV
  "github.com/go-redis/redis/v8"     // shared state
  "context"
)

var ctx = context.Background()

func main() {
  mode := os.Getenv("MODE") // "stateless" or "stateful"
  if mode == "stateless" {
    rdb := redis.NewClient(&redis.Options{Addr: "redis:6379"})
    http.HandleFunc("/item", func(w http.ResponseWriter, r *http.Request) {
      key := r.URL.Query().Get("key")
      val, err := rdb.Get(ctx, key).Result() // network IO
      if err != nil { http.Error(w, "miss", 404); return }
      w.Write([]byte(val))
    })
  } else {
    db, _ := bolt.Open("local.db", 0600, &bolt.Options{Timeout: 1 * time.Second})
    defer db.Close()
    http.HandleFunc("/item", func(w http.ResponseWriter, r *http.Request) {
      key := r.URL.Query().Get("key")
      var val string
      db.View(func(tx *bolt.Tx) error {
        b := tx.Bucket([]byte("state"))
        if b == nil { http.Error(w, "not found", 404); return nil }
        v := b.Get([]byte(key))
        if v == nil { http.Error(w, "not found", 404); return nil }
        val = string(v); return nil
      })
      w.Write([]byte(val))
    })
  }
  log.Fatal(http.ListenAndServe(":8080", nil))
}