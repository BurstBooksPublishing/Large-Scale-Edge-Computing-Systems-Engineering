package main

import (
        "bufio"
        "context"
        "fmt"
        "log"
        "math"
        "math/rand"
        "net"
        "net/http"
        "strconv"
        "strings"
        "time"

        "github.com/prometheus/client_golang/prometheus"
        "github.com/prometheus/client_golang/prometheus/promhttp"
)

var (
        heartbeatRTT = prometheus.NewGauge(prometheus.GaugeOpts{
                Name: "edge_heartbeat_rtt_seconds",
                Help: "Smoothed RTT for heartbeats.",
        })
        heartbeatState = prometheus.NewGauge(prometheus.GaugeOpts{
                Name: "edge_heartbeat_state",
                Help: "1=healthy,0=unreachable",
        })
)

func init() {
        prometheus.MustRegister(heartbeatRTT, heartbeatState)
}

type RTTState struct {
        SRTT    float64
        RTTVAR  float64
        initialized bool
}

// update implements Eq. (1) with alpha=1/8,beta=1/4.
func (r *RTTState) update(sample float64) {
        const alpha = 1.0 / 8.0
        const beta = 1.0 / 4.0
        if !r.initialized {
                r.SRTT = sample
                r.RTTVAR = sample / 2
                r.initialized = true
                return
        }
        r.RTTVAR = (1-beta)*r.RTTVAR + beta*math.Abs(r.SRTT-sample)
        r.SRTT = (1-alpha)*r.SRTT + alpha*sample
}

// rto follows Eq. (2) with K=4 and a minimum guard.
func (r *RTTState) rto() time.Duration {
        if !r.initialized {
                return 2 * time.Second
        }
        K := 4.0
        min := 100 * time.Millisecond
        val := r.SRTT + K*r.RTTVAR
        if val < min.Seconds() {
                val = min.Seconds()
        }
        return time.Duration(val * float64(time.Second))
}

func sender(ctx context.Context, addr string, id string) {
        conn, err := net.Dial("udp", addr)
        if err != nil {
                log.Fatalf("dial: %v", err)
        }
        defer conn.Close()
        seq := uint64(0)
        rtt := &RTTState{}
        backoffFactor := 1.0
        for {
                select {
                case <-ctx.Done():
                        return
                default:
                }
                seq++
                now := time.Now().UnixNano()
                msg := fmt.Sprintf("%s;%d;%d", id, seq, now)
                start := time.Now()
                // add jitter to avoid synchronization storms
                sleep := time.Duration(500*math.Pow(0.9, backoffFactor)) * time.Millisecond
                jitter := time.Duration(rand.Int63n(200)) * time.Millisecond
                time.Sleep(sleep + jitter)
                conn.SetWriteDeadline(time.Now().Add(500 * time.Millisecond))
                _, err := conn.Write([]byte(msg + "\n"))
                if err != nil {
                        log.Printf("send error: %v", err)
                        backoffFactor = math.Min(backoffFactor*1.5, 6.0)
                        heartbeatState.Set(0)
                        continue
                }
                // wait for echo with adaptive timeout
                conn.SetReadDeadline(time.Now().Add(rtt.rto()))
                reply := make([]byte, 256)
                n, err := conn.Read(reply)
                if err != nil {
                        log.Printf("no echo: %v", err)
                        backoffFactor = math.Min(backoffFactor*1.5, 6.0)
                        heartbeatState.Set(0)
                        continue
                }
                latency := time.Since(start).Seconds()
                rtt.update(latency)
                heartbeatRTT.Set(rtt.SRTT)
                heartbeatState.Set(1)
                backoffFactor = 1.0
                // minimal processing of reply for correctness
                _ = strings.TrimSpace(string(reply[:n]))
        }
}

func listener(ctx context.Context, bind string) {
        pc, err := net.ListenPacket("udp", bind)
        if err != nil {
                log.Fatalf("listen: %v", err)
        }
        defer pc.Close()
        buf := make([]byte, 512)
        for {
                select {
                case <-ctx.Done():
                        return
                default:
                }
                n, addr, err := pc.ReadFrom(buf)
                if err != nil {
                        continue
                }
                // echo back immediately to measure RTT
                line := strings.TrimSpace(string(buf[:n]))
                _ = line
                pc.WriteTo([]byte(line+"\n"), addr) // best-effort echo
        }
}

func main() {
        ctx, cancel := context.WithCancel(context.Background())
        defer cancel()
        go listener(ctx, ":9000")
        go sender(ctx, "127.0.0.1:9000", "node-42")
        // metrics endpoint for scraping by Prometheus or Fleet manager
        http.Handle("/metrics", promhttp.Handler())
        log.Fatal(http.ListenAndServe(":9100", nil))
}