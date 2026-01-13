from cryptography.hazmat.primitives.asymmetric import x25519
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes
import os, struct

Q = 2**32  # modulus for quantized gradients
D = 1024   # vector dimension (example)

# persistent identity keypair (provisioned securely)
priv = x25519.X25519PrivateKey.generate()
pub = priv.public_key().public_bytes()

def shared_mask(peer_pub_bytes, seed_nonce):
    # derive shared secret via X25519
    peer_pub = x25519.X25519PublicKey.from_public_bytes(peer_pub_bytes)
    shared = priv.exchange(peer_pub)
    # expand to D 32-bit words using HKDF
    hk = HKDF(algorithm=hashes.SHA256(), length=4*D, salt=None, info=seed_nonce)
    stream = hk.derive(shared)
    # convert to list of uint32 mask words
    return [struct.unpack_from(">I", stream, i*4)[0] % Q for i in range(D)]

# Example: compute local mask given list of peer public keys
def compute_local_mask(peer_public_list, my_nonce, peer_nonces):
    # peer_nonces is aligned list, ensuring deterministic +/- sign
    total = [0]*D
    for peer_pub, peer_nonce in zip(peer_public_list, peer_nonces):
        r = shared_mask(peer_pub, my_nonce + peer_nonce)  # deterministic seed
        # sign rule: only add r when my_pub > peer_pub lexicographically
        if pub > peer_pub:
            # add r
            for i in range(D):
                total[i] = (total[i] + r[i]) % Q
        else:
            # subtract r
            for i in range(D):
                total[i] = (total[i] - r[i]) % Q
    return total

# compute masked gradient to send
def mask_and_serialize(gradient, local_mask):
    masked = [ (g + m) % Q for g,m in zip(gradient, local_mask) ]
    # serialize compactly (big-endian uint32)
    return b''.join(struct.pack(">I", v) for v in masked)