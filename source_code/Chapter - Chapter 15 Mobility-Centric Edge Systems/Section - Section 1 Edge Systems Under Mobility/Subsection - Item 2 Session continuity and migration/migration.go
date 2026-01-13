package main

import (
        "context"
        "time"
        "io"
        "k8s.io/client-go/kubernetes"
        "k8s.io/client-go/rest"
        pb "example.com/sessionpb" // generated gRPC session protobuf
        "google.golang.org/grpc"
        metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
)

func migrateSession(ctx context.Context, sessionID string, state io.Reader, targetAddr string) error {
        // 1) Transfer state via gRPC stream with timeout.
        ctx, cancel := context.WithTimeout(ctx, 2*time.Minute)
        defer cancel()
        conn, err := grpc.DialContext(ctx, targetAddr, grpc.WithInsecure()) // TLS in prod
        if err != nil { return err }
        defer conn.Close()
        client := pb.NewSessionTransferClient(conn)
        stream, err := client.PushState(ctx)
        if err != nil { return err }
        buf := make([]byte, 64*1024)
        for {
                n, rerr := state.Read(buf)
                if n > 0 {
                        if err := stream.Send(&pb.StateChunk{SessionId: sessionID, Data: buf[:n]}); err != nil { return err }
                }
                if rerr == io.EOF { break }
                if rerr != nil { return rerr }
        }
        _, err = stream.CloseAndRecv()
        if err != nil { return err }

        // 2) Patch Kubernetes endpoint to point traffic to new node IP.
        cfg, err := rest.InClusterConfig()
        if err != nil { return err }
        clientset, err := kubernetes.NewForConfig(cfg)
        if err != nil { return err }
        // Replace endpoints for the session service (atomic update in real controller).
        _, err = clientset.CoreV1().Endpoints("edge-ns").Patch(ctx, "session-"+sessionID, 
                []byte(`[{"op":"replace","path":"/subsets","value":[{"addresses":[{"ip":"`+targetAddr+`"}],"ports":[{"port":443}]}]}]`),
                metav1.PatchOptions{})
        return err
}