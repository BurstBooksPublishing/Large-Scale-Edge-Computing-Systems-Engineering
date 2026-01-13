package main

import (
  "encoding/json"
  "log"
  "net/http"
  "sync"
)

type GCounter struct {
  mu sync.Mutex
  // vector indexed by node id string
  V map[string]uint64
}

func NewGCounter() *GCounter { return &GCounter{V: make(map[string]uint64)} }

// increment local counter
func (g *GCounter) Inc(node string, delta uint64) {
  g.mu.Lock(); defer g.mu.Unlock()
  g.V[node] += delta
}

// merge applies elementwise max from remote
func (g *GCounter) Merge(remote map[string]uint64) {
  g.mu.Lock(); defer g.mu.Unlock()
  for k, rv := range remote {
    if lv, ok := g.V[k]; !ok || rv > lv {
      g.V[k] = rv
    }
  }
}

// value returns global sum
func (g *GCounter) Value() uint64 {
  g.mu.Lock(); defer g.mu.Unlock()
  var s uint64
  for _, v := range g.V { s += v }
  return s
}

func main() {
  g := NewGCounter()
  // HTTP handlers for terse demo; production should use TLS and auth
  http.HandleFunc("/inc", func(w http.ResponseWriter, r *http.Request) {
    var req struct{ Node string; Delta uint64 }
    json.NewDecoder(r.Body).Decode(&req) // validate in production
    g.Inc(req.Node, req.Delta)
    w.WriteHeader(http.StatusNoContent)
  })
  http.HandleFunc("/merge", func(w http.ResponseWriter, r *http.Request) {
    var remote map[string]uint64
    json.NewDecoder(r.Body).Decode(&remote)
    g.Merge(remote)
    w.WriteHeader(http.StatusNoContent)
  })
  http.HandleFunc("/value", func(w http.ResponseWriter, r *http.Request) {
    json.NewEncoder(w).Encode(map[string]uint64{"value": g.Value()})
  })
  log.Fatal(http.ListenAndServe(":8080", nil))
}