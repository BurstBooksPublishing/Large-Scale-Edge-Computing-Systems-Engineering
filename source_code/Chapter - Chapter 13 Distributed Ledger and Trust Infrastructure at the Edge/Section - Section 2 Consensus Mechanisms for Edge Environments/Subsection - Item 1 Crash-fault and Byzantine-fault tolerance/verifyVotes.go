package consensus

import (
        "crypto/ed25519"
        "errors"
)

// Vote represents a signed approval for a proposal.
type Vote struct {
        ValidatorID string // unique validator identifier
        Signature   []byte // ed25519 signature over ProposalID
        ProposalID  []byte
        PubKey      ed25519.PublicKey
}

// VerifyVotes verifies signatures, deduplicates validators,
// and checks quorum for crash (mode="crash") or byz (mode="byz").
// Returns nil if quorum reached and all signatures valid.
func VerifyVotes(votes []Vote, n int, mode string) error {
        if n <= 0 {
                return errors.New("invalid cluster size")
        }
        seen := make(map[string]struct{})
        validCount := 0
        for _, v := range votes {
                if _, ok := seen[v.ValidatorID]; ok {
                        continue // duplicate vote ignored
                }
                // verify signature; production: protect against malleable inputs
                if len(v.Signature) != ed25519.SignatureSize || len(v.PubKey) != ed25519.PublicKeySize {
                        continue
                }
                if !ed25519.Verify(v.PubKey, v.ProposalID, v.Signature) {
                        continue
                }
                seen[v.ValidatorID] = struct{}{}
                validCount++
        }
        // quorum thresholds
        switch mode {
        case "crash":
                q := n/2 + 1
                if validCount >= q {
                        return nil
                }
                return errors.New("insufficient crash quorum")
        case "byz":
                // require n >= 3f+1; compute f = floor((n-1)/3)
                f := (n - 1) / 3
                q := 2*f + 1
                if validCount >= q {
                        return nil
                }
                return errors.New("insufficient byzantine quorum")
        default:
                return errors.New("unknown quorum mode")
        }
}