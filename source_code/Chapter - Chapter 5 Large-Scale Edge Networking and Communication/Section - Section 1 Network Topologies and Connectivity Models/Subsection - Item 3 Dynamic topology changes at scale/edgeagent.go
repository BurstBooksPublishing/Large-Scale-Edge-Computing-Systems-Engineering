package main

import (
  "context"
  "encoding/json"
  "net"
  "time"
  "google.golang.org/grpc"
  pb "example.com/edge/proto" // controller gRPC proto
)

// config knobs
const (
  BeaconInterval = 200 * time.Millisecond
  BatchInterval  = 500 * time.Millisecond
  MaxBatchSize   = 100
  UDPPort        = "9999"
)

type Beacon struct {
  ID        string    `json:"id"`
  Seq       uint64    `json:"seq"`
  Timestamp time.Time `json:"ts"`
}

func sendBeacon(id string, seq uint64, conn *net.UDPConn) {
  b := Beacon{ID: id, Seq: seq, Timestamp: time.Now()}
  data, _ := json.Marshal(b)
  conn.Write(data) // ignore transient errors; local repair tolerated
}

func listenNeighbors(conn *net.UDPConn, out chan<- Beacon) {
  buf := make([]byte, 512)
  for {
    n, _, err := conn.ReadFromUDP(buf)
    if err != nil { continue }
    var b Beacon
    if json.Unmarshal(buf[:n], &b) == nil {
      out <- b
    }
  }
}

func reportLoop(ctx context.Context, client pb.ControllerClient, in <-chan Beacon) {
  ticker := time.NewTicker(BatchInterval)
  defer ticker.Stop()
  batch := make([]*pb.BeaconEvent, 0, MaxBatchSize)
  for {
    select {
    case <-ctx.Done():
      return
    case b := <-in:
      batch = append(batch, &pb.BeaconEvent{Id: b.ID, Seq: b.Seq, Ts: b.Timestamp.UnixNano()})
      if len(batch) >= MaxBatchSize {
        client.Report(context.Background(), &pb.Batch{Events: batch})
        batch = batch[:0]
      }
    case <-ticker.C:
      if len(batch) > 0 {
        client.Report(context.Background(), &pb.Batch{Events: batch})
        batch = batch[:0]
      }
    }
  }
}

func main() {
  id := "edge-node-123" // use hardware-backed identity in production
  addr, _ := net.ResolveUDPAddr("udp4", "224.0.0.1:"+UDPPort)
  laddr, _ := net.ResolveUDPAddr("udp4", ":"+UDPPort)
  conn, _ := net.ListenMulticastUDP("udp4", nil, addr)
  conn.SetReadBuffer(1024)
  grpcConn, _ := grpc.Dial("controller:50051", grpc.WithInsecure())
  client := pb.NewControllerClient(grpcConn)
  neighborCh := make(chan Beacon, 1024)
  ctx, cancel := context.WithCancel(context.Background())
  defer cancel()
  go listenNeighbors(conn, neighborCh)
  go reportLoop(ctx, client, neighborCh)
  seq := uint64(0)
  // beacon loop
  for range time.Tick(BeaconInterval) {
    seq++
    sendBeacon(id, seq, conn)
  }
}