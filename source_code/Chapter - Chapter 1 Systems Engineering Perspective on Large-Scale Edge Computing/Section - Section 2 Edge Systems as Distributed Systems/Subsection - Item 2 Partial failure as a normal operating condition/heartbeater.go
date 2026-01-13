package heartbeat

import (
        "context"
        "net"
        "sync"
        "time"
)

// Detector implements an adaptive heartbeat detector.
type Detector struct {
        addr       *net.UDPAddr
        conn       *net.UDPConn
        mu         sync.Mutex
        last       time.Time
        ewmaRTT    time.Duration
        alpha      float64
        timeoutMul float64
        cbOpen     bool
}

// NewDetector creates a detector bound to multicast/peer addr.
func NewDetector(addr string) (*Detector, error) {
        a, err := net.ResolveUDPAddr("udp", addr)
        if err != nil { return nil, err }
        c, err := net.ListenUDP("udp", nil)
        if err != nil { return nil, err }
        return &Detector{
                addr:       a,
                conn:       c,
                ewmaRTT:    200 * time.Millisecond, // initial guess
                alpha:      0.2,                    // EWMA weight
                timeoutMul: 4.0,                    // multiplier for timeout
        }, nil
}

// StartHeartbeat sends periodic heartbeats; caller cancels ctx to stop.
func (d *Detector) StartHeartbeat(ctx context.Context, interval time.Duration) {
        t := time.NewTicker(interval)
        go func() {
                for {
                        select {
                        case <-t.C:
                                d.sendHeartbeat()
                        case <-ctx.Done():
                                t.Stop()
                                return
                        }
                }
        }()
}

// sendHeartbeat transmits a packet and updates RTT on response.
func (d *Detector) sendHeartbeat() {
        send := []byte("hb")
        start := time.Now()
        d.conn.WriteToUDP(send, d.addr) // best-effort
        // non-blocking read with short deadline
        d.conn.SetReadDeadline(time.Now().Add(500 * time.Millisecond))
        buf := make([]byte, 16)
        _, _, err := d.conn.ReadFromUDP(buf)
        rtt := time.Since(start)
        d.mu.Lock()
        defer d.mu.Unlock()
        if err == nil {
                // update EWMA RTT
                d.ewmaRTT = time.Duration(d.alpha*float64(rtt) + (1-d.alpha)*float64(d.ewmaRTT))
                d.last = time.Now()
                d.cbOpen = false
        } else {
                // missed heartbeat: evaluate timeout
                if time.Since(d.last) > time.Duration(d.timeoutMul*float64(d.ewmaRTT)) {
                        d.cbOpen = true // circuit breaker: treat peer as failed
                }
        }
}

// IsAvailable returns false when circuit breaker marks peer failed.
func (d *Detector) IsAvailable() bool {
        d.mu.Lock()
        defer d.mu.Unlock()
        return !d.cbOpen
}