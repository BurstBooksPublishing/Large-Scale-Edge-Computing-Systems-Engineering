package main

import (
        "crypto/tls"
        "encoding/json"
        "log"
        "net/http"
        "time"
)

// CapacityOffer represents an operator capacity announcement.
type CapacityOffer struct {
        OperatorID string  `json:"operator_id"`
        CPU        float64 `json:"cpu"` // CPU-seconds/s
        TS         int64   `json:"ts"`
}

// AllocationRequest asks for capacity reservation.
type AllocationRequest struct {
        WorkloadID string  `json:"workload_id"`
        Demand     float64 `json:"demand"`
        LatencyMS  float64 `json:"latency_ms"`
}

// Accepts offers; in production persist to DB and verify JWT scopes.
func announceHandler(w http.ResponseWriter, r *http.Request) {
        var offer CapacityOffer
        if err := json.NewDecoder(r.Body).Decode(&offer); err != nil {
                http.Error(w, "bad request", http.StatusBadRequest)
                return
        }
        offer.TS = time.Now().Unix()
        // storeOffer persists to operator catalog (omitted).
        log.Printf("Offer: %+v\n", offer)
        w.WriteHeader(http.StatusAccepted)
}

// Simple greedy allocator; replace with optimization solver for production.
func allocateHandler(w http.ResponseWriter, r *http.Request) {
        var req AllocationRequest
        if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
                http.Error(w, "bad request", http.StatusBadRequest)
                return
        }
        // choose operator by measured latency/capacity (logic omitted).
        resp := map[string]string{"assigned_operator": "operator-A", "note": "greedy-assignment"}
        _ = json.NewEncoder(w).Encode(resp)
}

func main() {
        mux := http.NewServeMux()
        mux.HandleFunc("/announce", announceHandler)
        mux.HandleFunc("/allocate", allocateHandler)

        // mTLS setup: load server certs and require client certs from trusted CA.
        cert, _ := tls.LoadX509KeyPair("server.crt", "server.key")
        tlsCfg := &tls.Config{
                Certificates: []tls.Certificate{cert},
                ClientAuth:   tls.RequireAndVerifyClientCert,
                MinVersion:   tls.VersionTLS12,
        }
        srv := &http.Server{Addr: ":8443", Handler: mux, TLSConfig: tlsCfg}
        log.Fatal(srv.ListenAndServeTLS("", "")) // certs provided via TLSConfig
}