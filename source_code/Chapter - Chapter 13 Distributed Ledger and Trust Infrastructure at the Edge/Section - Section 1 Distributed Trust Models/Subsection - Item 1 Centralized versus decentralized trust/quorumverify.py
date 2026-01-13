import asyncio
import time
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from cryptography.hazmat.primitives import serialization

# Load public keys of validators (PEM list) -- production: secure storage/TPM
validator_pems = ["validator1.pem","validator2.pem","validator3.pem","validator4.pem","validator5.pem","validator6.pem","validator7.pem"]
validators = [Ed25519PublicKey.from_public_bytes(open(p,'rb').read()) for p in validator_pems]

async def contact_validator(idx, payload, sig):
    # Simulated network call to validator idx; replace with aiohttp/grpc call.
    await asyncio.sleep(0.02 + 0.005*idx)  # variable RTT
    try:
        validators[idx].verify(sig, payload)  # raises on failure
        return True
    except Exception:
        return False

async def collect_votes(payload, sig, q):
    tasks = [asyncio.create_task(contact_validator(i,payload,sig)) for i in range(len(validators))]
    votes = []
    for coro in asyncio.as_completed(tasks):
        ok = await coro
        votes.append(ok)
        # Early exit optimization: enough positives or impossible to reach quorum
        if votes.count(True) >= q:
            for t in tasks:
                if not t.done():
                    t.cancel()
            return True, time.time()
        if len(votes) - votes.count(True) > len(validators) - q:
            return False, time.time()
    return votes.count(True) >= q, time.time()

def measure_quorum(payload, sig, q):
    start = time.time()
    ok, ts = asyncio.run(collect_votes(payload, sig, q))
    return ok, (ts - start)

# Example usage (payload and sig from validators)
# ok, latency = measure_quorum(b"msg", b"\x00...signature...", q=5)
# print("quorum ok:", ok, "latency s:", latency)