# migration_agent.py
import asyncio, aiohttp, hashlib, os

CHUNK = 64*1024

async def sha256_file(path):
    h = hashlib.sha256()
    with open(path,'rb') as f:
        while True:
            b = f.read(CHUNK)
            if not b: break
            h.update(b)
    return h.hexdigest()

async def upload_state(session, url, path):
    # compute checksum first (cheap for small working sets)
    checksum = await sha256_file(path)
    async with session.post(url, params={'sha256':checksum}) as resp:
        if resp.status!=200:
            raise RuntimeError(f"init failed: {resp.status}")
        # stream file in chunks
        with open(path,'rb') as f:
            async for chunk in iter(lambda: f.read(CHUNK), b''):
                await resp.content.write(chunk)  # HTTP chunked body
        result = await resp.json()
        if result.get('sha256')!=checksum:
            raise RuntimeError("checksum mismatch after upload")
    return True

async def apply_state_atomic(tmp_path, target_path):
    # atomic rename to avoid partial-state reads
    os.replace(tmp_path, target_path)

async def migrate(local_path, target_url):
    tls = aiohttp.TCPConnector(ssl=True)
    async with aiohttp.ClientSession(connector=tls) as sess:
        await upload_state(sess, target_url, local_path)
        # post-transfer command to finalize on target
        async with sess.post(f"{target_url}/finalize") as r:
            if r.status!=200:
                raise RuntimeError("finalize failed")

if __name__=='__main__':
    # run from orchestrator when migration condition met
    asyncio.run(migrate('/var/lib/app/state.dump','https://mec-node.example/migrate'))