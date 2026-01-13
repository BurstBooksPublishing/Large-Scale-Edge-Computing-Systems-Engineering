#!/usr/bin/env python3
# Sign and push policy bundles to edge agents via HTTPS concurrently.
import asyncio, aiohttp, json
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature

# Load or generate ECDSA private key (P-256)
with open("signer_key.pem","rb") as f:
    private_key = serialization.load_pem_private_key(f.read(), password=None)

async def sign_bundle(bundle_bytes: bytes) -> str:
    # Create deterministic signature (DER) and base64 encode.
    sig = private_key.sign(bundle_bytes, ec.ECDSA(hashes.SHA256()))
    return sig.hex()

async def push_to_agent(session, url, bundle, sig, timeout=5):
    headers = {"Content-Type":"application/json","X-Bundle-Sig":sig}
    payload = {"manifest":{"version": bundle["version"]},"bundle":bundle["data"]}
    try:
        async with session.post(url, json=payload, headers=headers, timeout=timeout) as resp:
            return url, resp.status, await resp.text()
    except Exception as e:
        return url, "error", str(e)

async def main(agent_urls, bundle):
    bundle_bytes = json.dumps(bundle, sort_keys=True).encode("utf-8")
    sig = await sign_bundle(bundle_bytes)
    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(limit=100)) as session:
        tasks = [push_to_agent(session, u, bundle, sig) for u in agent_urls]
        for fut in asyncio.as_completed(tasks):
            url, status, body = await fut
            # Minimal inline audit logging
            print(url, status)
            if status != 200:
                # Implement exponential backoff retry or escalate to regional controller
                pass

# Example use
if __name__ == "__main__":
    agents = ["https://edge-agent-1.local/policy","https://edge-agent-2.local/policy"]
    bundle = {"version":"2025-12-29T12:00:00Z","data":{"rules":[{"id":"block-ssh","action":"deny","match":"tcp/22"}]}}
    asyncio.run(main(agents, bundle))