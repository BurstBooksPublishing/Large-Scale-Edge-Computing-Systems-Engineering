package sync

import (
    "context"
    "crypto/sha256"
    "database/sql"
    "encoding/json"
    "net/http"
    "time"
)

// SyncConfig holds operational parameters.
type SyncConfig struct {
    Peers       []string      // peer endpoints (HTTP or libp2p addresses)
    ChunkBytes  int64         // bytes per data chunk to request
    Interval    time.Duration // periodic sync interval
    HTTPClient  *http.Client  // transport with timeouts
    DB          *sql.DB       // local DB for headers/roots
}

// Header represents a compact block header.
type Header struct {
    Height    uint64 `json:"height"`
    PrevHash  []byte `json:"prev_hash"`
    RootHash  []byte `json:"root_hash"`
    Timestamp int64  `json:"timestamp"`
}

// RunSyncLoop starts the periodic sync worker.
func RunSyncLoop(ctx context.Context, cfg SyncConfig) {
    ticker := time.NewTicker(cfg.Interval)
    defer ticker.Stop()
    for {
        select {
        case <-ctx.Done():
            return
        case <-ticker.C:
            for _, peer := range cfg.Peers {
                // simple sequential peer probing; production may use parallelism and scoring
                if err := syncWithPeer(ctx, cfg, peer); err == nil {
                    break // stop after successful sync with highest-priority reachable peer
                }
            }
        }
    }
}

func syncWithPeer(ctx context.Context, cfg SyncConfig, peer string) error {
    // request latest header
    req, _ := http.NewRequestWithContext(ctx, "GET", peer+"/headers/latest", nil)
    resp, err := cfg.HTTPClient.Do(req)
    if err != nil {
        return err
    }
    defer resp.Body.Close()
    var hdr Header
    if err := json.NewDecoder(resp.Body).Decode(&hdr); err != nil {
        return err
    }
    // verify header chain with local prev hash (DB lookup omitted for brevity)
    if !verifyHeader(hdr, cfg.DB) {
        return ErrInvalidHeader
    }
    // request state in bandwidth-friendly chunks
    return fetchStateChunks(ctx, cfg, peer, hdr.Height)
}

func fetchStateChunks(ctx context.Context, cfg SyncConfig, peer string, height uint64) error {
    // paginate requests for application state; use HTTP range-like parameter 'chunk'
    for chunk := int64(0); ; chunk++ {
        url := peer + "/state/" + itoa(height) + "?chunk=" + itoa(chunk) + "&size=" + itoa64(cfg.ChunkBytes)
        req, _ := http.NewRequestWithContext(ctx, "GET", url, nil)
        resp, err := cfg.HTTPClient.Do(req)
        if err != nil {
            return err
        }
        if resp.StatusCode == http.StatusNoContent { // no more chunks
            resp.Body.Close()
            break
        }
        // write chunk to DB or temp store (omitted); compute incremental verification
        var chunkData []byte
        if err := json.NewDecoder(resp.Body).Decode(&chunkData); err != nil {
            resp.Body.Close()
            return err
        }
        resp.Body.Close()
        // cheap integrity check
        if !validateChunk(chunkData) {
            return ErrChunkCorrupt
        }
        // apply chunk to local state; transactionally persist (omitted)
    }
    return nil
}

func validateChunk(b []byte) bool {
    h := sha256.Sum256(b)
    _ = h // compare with expected proof in production
    return true
}