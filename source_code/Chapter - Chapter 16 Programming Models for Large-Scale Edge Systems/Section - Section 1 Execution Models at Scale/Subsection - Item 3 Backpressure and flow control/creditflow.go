package main

import (
        "context"
        "encoding/binary"
        "errors"
        "io"
        "net"
        "sync/atomic"
        "time"
)

const (
        // Use small frames for constrained links; increase for high-bandwidth links.
        maxFrame = 1 << 16
)

// control message types
const (
        msgTypeData   = 1
        msgTypeCredits = 2
)

// framed write: [type(1)][len(2)][payload]
func writeFrame(w io.Writer, t byte, payload []byte) error {
        if len(payload) > maxFrame { return errors.New("frame too large") }
        var hdr [3]byte
        hdr[0] = t
        binary.BigEndian.PutUint16(hdr[1:], uint16(len(payload)))
        if _, err := w.Write(hdr[:]); err != nil { return err }
        _, err := w.Write(payload)
        return err
}

// producer sends data only when credits > 0
type Producer struct {
        conn    net.Conn
        credits int64 // atomic
}

func NewProducer(conn net.Conn) *Producer { return &Producer{conn: conn} }

func (p *Producer) Start(ctx context.Context, dataCh <-chan []byte) error {
        // reader for control frames (credits)
        go func() {
                for {
                        select {
                        case <-ctx.Done():
                                return
                        default:
                        }
                        var hdr [3]byte
                        if _, err := io.ReadFull(p.conn, hdr[:]); err != nil { return }
                        t := hdr[0]
                        n := int(binary.BigEndian.Uint16(hdr[1:]))
                        buf := make([]byte, n)
                        if _, err := io.ReadFull(p.conn, buf); err != nil { return }
                        if t == msgTypeCredits {
                                // credits are uint32 encoded
                                if len(buf) >= 4 {
                                        c := int64(binary.BigEndian.Uint32(buf))
                                        atomic.AddInt64(&p.credits, c)
                                }
                        }
                }
        }()
        // sender loop
        for {
                select {
                case <-ctx.Done():
                        return ctx.Err()
                case d := <-dataCh:
                        // wait for credit
                        for atomic.LoadInt64(&p.credits) <= 0 {
                                select {
                                case <-ctx.Done():
                                        return ctx.Err()
                                case <-time.After(10 * time.Millisecond):
                                }
                        }
                        atomic.AddInt64(&p.credits, -1)
                        if err := writeFrame(p.conn, msgTypeData, d); err != nil { return err }
                }
        }
}

// consumer grants credits based on thread pool capacity
type Consumer struct {
        conn       net.Conn
        threadPool chan struct{}
}

func NewConsumer(conn net.Conn, poolSize int) *Consumer {
        return &Consumer{conn: conn, threadPool: make(chan struct{}, poolSize)}
}

func (c *Consumer) Start(ctx context.Context) error {
        // periodic credit grant equals free slots
        go func() {
                t := time.NewTicker(50 * time.Millisecond)
                defer t.Stop()
                for {
                        select {
                        case <-ctx.Done():
                                return
                        case <-t.C:
                                free := cap(c.threadPool) - len(c.threadPool)
                                if free > 0 {
                                        var b [4]byte
                                        binary.BigEndian.PutUint32(b[:], uint32(free))
                                        _ = writeFrame(c.conn, msgTypeCredits, b[:]) // ignore error for brevity
                                }
                        }
                }
        }()
        // reader loop
        for {
                select {
                case <-ctx.Done():
                        return ctx.Err()
                default:
                }
                var hdr [3]byte
                if _, err := io.ReadFull(c.conn, hdr[:]); err != nil { return err }
                t := hdr[0]
                n := int(binary.BigEndian.Uint16(hdr[1:]))
                buf := make([]byte, n)
                if _, err := io.ReadFull(c.conn, buf); err != nil { return err }
                if t == msgTypeData {
                        // limit concurrency via threadPool
                        c.threadPool <- struct{}{}
                        go func(payload []byte) {
                                defer func(){ <-c.threadPool }()
                                // process payload (decode, enqueue to pipeline, etc.)
                                _ = payload // placeholder
                        }(buf)
                }
        }
}