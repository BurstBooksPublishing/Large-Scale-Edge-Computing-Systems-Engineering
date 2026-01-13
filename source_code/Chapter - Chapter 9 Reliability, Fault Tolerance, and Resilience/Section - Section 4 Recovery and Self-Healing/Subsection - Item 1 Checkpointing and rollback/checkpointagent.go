package main

import (
        "context"
        "log"
        "os"
        "os/exec"
        "time"

        minio "github.com/minio/minio-go/v7"
        "github.com/minio/minio-go/v7/pkg/credentials"
)

func main() {
        ctx, cancel := context.WithTimeout(context.Background(), 5*time.Minute)
        defer cancel()

        // 1) Quiesce application via local HTTP endpoint (app implements quiesce).
        if err := exec.CommandContext(ctx, "curl", "-sS", "http://127.0.0.1:8080/quiesce").Run(); err != nil {
                log.Fatalf("quiesce failed: %v", err)
        }

        // 2) Run CRIU dump for PID 1234 into /tmp/ckpt (ensure CRIU installed).
        if err := exec.CommandContext(ctx, "criu", "dump", "-t", "1234", "-D", "/tmp/ckpt", "--tcp-established", "--leave-running").Run(); err != nil {
                log.Fatalf("criu dump failed: %v", err)
        }

        // 3) Create tarball (atomic rename pattern).
        tarPath := "/tmp/ckpt.tar.gz"
        if err := exec.CommandContext(ctx, "tar", "-czf", tarPath, "-C", "/tmp", "ckpt").Run(); err != nil {
                log.Fatalf("tar failed: %v", err)
        }

        // 4) Upload to S3-compatible MinIO (endpoint and creds from env).
        endpoint := os.Getenv("S3_ENDPOINT")
        access := os.Getenv("S3_ACCESS")
        secret := os.Getenv("S3_SECRET")
        minioClient, err := minio.New(endpoint, &minio.Options{Creds: credentials.NewStaticV4(access, secret, ""), Secure: false})
        if err != nil {
                log.Fatalf("minio init: %v", err)
        }
        bucket := "edge-checkpoints"
        objName := "node1234/ckpt-" + time.Now().UTC().Format("20060102T150405") + ".tar.gz"
        if _, err := minioClient.FPutObject(ctx, bucket, objName, tarPath, minio.PutObjectOptions{}); err != nil {
                log.Fatalf("upload failed: %v", err)
        }
        // cleanup local artifacts
        _ = os.RemoveAll("/tmp/ckpt")
        _ = os.Remove(tarPath)
}