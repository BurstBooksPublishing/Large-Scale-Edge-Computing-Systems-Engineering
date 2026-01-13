package main

import (
        "context"
        "crypto/tls"
        "encoding/json"
        "net/http"
        "sync"
        "time"
)

// simple TTL cache entry
type cacheEntry struct {
        decision bool
        expiry   time.Time
}

type PEP struct {
        opaURL      string
        pdpURL      string
        httpClient  *http.Client
        cache       map[string]cacheEntry
        cacheMutex  sync.RWMutex
        cacheTTL    time.Duration
        evalTimeout time.Duration
}

func NewPEP(opaURL, pdpURL string, clientCert tls.Certificate) *PEP {
        tlsCfg := &tls.Config{Certificates: []tls.Certificate{clientCert}}
        return &PEP{
                opaURL: opaURL, pdpURL: pdpURL,
                httpClient: &http.Client{Timeout: 5 * time.Second, Transport: &http.Transport{TLSClientConfig: tlsCfg}},
                cache:      make(map[string]cacheEntry),
                cacheTTL:   30 * time.Second,
                evalTimeout: 200 * time.Millisecond,
        }
}

// Evaluate checks cache, then local OPA, then remote PDP.
func (p *PEP) Evaluate(ctx context.Context, input map[string]interface{}) (bool, error) {
        keyBytes, _ := json.Marshal(input)
        key := string(keyBytes)

        // check cache
        p.cacheMutex.RLock()
        if e, ok := p.cache[key]; ok && time.Now().Before(e.expiry) {
                p.cacheMutex.RUnlock()
                return e.decision, nil
        }
        p.cacheMutex.RUnlock()

        // local OPA eval
        ctxLocal, cancel := context.WithTimeout(ctx, p.evalTimeout)
        defer cancel()
        decision, err := p.queryOPA(ctxLocal, input)
        if err == nil {
                p.storeCache(key, decision)
                return decision, nil
        }

        // remote PDP fallback with longer timeout
        ctxRemote, cancel2 := context.WithTimeout(ctx, 2*p.evalTimeout)
        defer cancel2()
        decision, err = p.queryPDP(ctxRemote, input)
        if err != nil {
                return false, err
        }
        p.storeCache(key, decision)
        return decision, nil
}

func (p *PEP) storeCache(key string, decision bool) {
        p.cacheMutex.Lock()
        p.cache[key] = cacheEntry{decision: decision, expiry: time.Now().Add(p.cacheTTL)}
        p.cacheMutex.Unlock()
}

func (p *PEP) queryOPA(ctx context.Context, input map[string]interface{}) (bool, error) {
        reqBody := map[string]interface{}{"input": input}
        b, _ := json.Marshal(reqBody)
        req, _ := http.NewRequestWithContext(ctx, "POST", p.opaURL+"/v1/data/edge/allow", 
                bytes.NewReader(b))
        req.Header.Set("Content-Type", "application/json")
        resp, err := p.httpClient.Do(req)
        if err != nil { return false, err }
        defer resp.Body.Close()
        var out struct{ Result bool `json:"result"` }
        if err := json.NewDecoder(resp.Body).Decode(&out); err != nil { return false, err }
        return out.Result, nil
}

func (p *PEP) queryPDP(ctx context.Context, input map[string]interface{}) (bool, error) {
        // similar to queryOPA but different path, omitted for brevity
        return false, nil
}