package main

import (
        "crypto/tls"
        "crypto/x509"
        "io/ioutil"
        "log"
        "net/http"
        "strings"
        "time"
)

// loadCertPool loads CAs used to verify client certs (e.g., SPIRE CA).
func loadCertPool(caFile string) *x509.CertPool {
        pool := x509.NewCertPool()
        data, err := ioutil.ReadFile(caFile)
        if err != nil { log.Fatalf("read CA: %v", err) }
        if !pool.AppendCertsFromPEM(data) { log.Fatalf("append CA failed") }
        return pool
}

// verifySpiffeID enforces client identity belongs to expected trust domain.
func verifySpiffeID(rawCerts [][]byte, verifiedChains [][]*x509.Certificate) error {
        // Simple check: client cert SAN URI must start with "spiffe://factory/sensors/"
        if len(verifiedChains) == 0 || len(verifiedChains[0]) == 0 {
                return tls.Alert(tls.AlertBadCertificate) // fail if chain missing
        }
        cert := verifiedChains[0][0]
        for _, uri := range cert.URIs {
                if strings.HasPrefix(uri.String(), "spiffe://factory/sensors/") {
                        // Optionally call TPM-attestation validation here.
                        return nil
                }
        }
        return tls.Alert(tls.AlertAccessDenied)
}

func main() {
        caPool := loadCertPool("/etc/ssl/ca/spire-ca.pem")
        cert, err := tls.LoadX509KeyPair("/etc/ssl/server-cert.pem", "/etc/ssl/server-key.pem")
        if err != nil { log.Fatalf("load server cert: %v", err) }

        tlsCfg := &tls.Config{
                Certificates:             []tls.Certificate{cert},
                ClientCAs:                caPool,
                ClientAuth:               tls.RequireAndVerifyClientCert,
                MinVersion:               tls.VersionTLS12,
                VerifyPeerCertificate:    verifySpiffeID, // enforce trust boundary identity
                PreferServerCipherSuites: true,
        }

        srv := &http.Server{
                Addr:         ":8443",
                TLSConfig:    tlsCfg,
                ReadTimeout:  5 * time.Second,
                WriteTimeout: 10 * time.Second,
        }

        http.HandleFunc("/telemetry", func(w http.ResponseWriter, r *http.Request) {
                // Application-level validation and rate limiting here.
                w.WriteHeader(204)
        })

        log.Println("edge gateway: accepting only sensor domain clients")
        log.Fatal(srv.ListenAndServeTLS("", "")) // TLS handled by tlsCfg
}