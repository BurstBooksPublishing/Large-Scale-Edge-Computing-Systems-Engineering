package main

import (
        "context"
        "crypto/tls"
        "net/http"
        "time"

        // SPIFFE v2 workload API client
        "github.com/spiffe/go-spiffe/v2/workloadapi"
        // OPA Rego evaluation
        "github.com/open-policy-agent/opa/rego"
)

func main() {
        ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
        defer cancel()

        // Create X.509 source from Workload API (SPIFFE/SPIRE agent on host)
        src, err := workloadapi.NewX509Source(ctx)
        if err != nil {
                panic(err) // replace with retry/backoff in production
        }
        defer src.Close()

        // TLS config uses the automatic SVID for client certs
        tlsCfg := &tls.Config{
                MinVersion: tls.VersionTLS13,
                GetClientCertificate: src.GetClientCertificate, // uses current SVID
        }

        httpClient := &http.Client{
                Timeout: 2 * time.Second,
                Transport: &http.Transport{
                        TLSClientConfig: tlsCfg,
                },
        }

        // Prepare OPA rego query (policy compiled into bundle or loaded at runtime)
        r := rego.New(
                rego.Query("data.edge.allow"),
                rego.Module("policy.rego", `package edge
                        default allow = false
                        allow { input.method == "POST" ; input.role == "maint" }`),
        )

        // Example request context from telemetry and identity
        input := map[string]interface{}{
                "method": "POST",
                "role":   "maint",
                "source": "spiffe://example.org/workload/myapp",
        }

        // Evaluate policy locally
        ctx2, cancel2 := context.WithTimeout(context.Background(), 100*time.Millisecond)
        defer cancel2()
        rs, err := r.Eval(ctx2, rego.EvalInput(input))
        if err != nil || len(rs) == 0 {
                // deny by default; log and audit
                return
        }
        allow, ok := rs[0].Expressions[0].Value.(bool)
        if !ok || !allow {
                // denied: audit and respond
                return
        }

        // Authorized: perform mTLS call to control plane
        req, _ := http.NewRequest("POST", "https://controlplane.local/action", nil)
        resp, err := httpClient.Do(req)
        if err != nil {
                // handle network failure with retry/backoff and circuit breaker
                return
        }
        resp.Body.Close()
}