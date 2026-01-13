import asyncio, struct, zlib, math
# pack/unpack 32-bit unsigned integers
PACK = struct.Struct("!I").pack
UNPACK = struct.Struct("!I").unpack

BATCH_SIZE = 256          # number of ints per packet
CHUNK_BYTES = BATCH_SIZE * 4

async def send_chunk(writer: asyncio.StreamWriter, ints):
    # compress and send length-prefixed packet
    payload = b"".join(PACK(x) for x in ints)
    payload = zlib.compress(payload)           # reduce bandwidth
    writer.write(len(payload).to_bytes(4, "big") + payload)
    await writer.drain()

async def recv_chunk(reader: asyncio.StreamReader):
    # receive length-prefix and decompress
    hdr = await reader.readexactly(4)
    size = int.from_bytes(hdr, "big")
    payload = await reader.readexactly(size)
    data = zlib.decompress(payload)
    return [UNPACK(data[i:i+4])[0] for i in range(0, len(data), 4)]

async def tree_aggregate_send(host, port, data_iter):
    reader, writer = await asyncio.open_connection(host, port)
    batch = []
    for x in data_iter:
        batch.append(int(x) & 0xFFFFFFFF)
        if len(batch) >= BATCH_SIZE:
            await send_chunk(writer, batch)
            batch.clear()
    if batch:
        await send_chunk(writer, batch)
    writer.close()
    await writer.wait_closed()

async def tree_aggregate_receive(reader, writer, process_cb):
    # process inbound chunks, combine and forward upward
    try:
        while True:
            ints = await recv_chunk(reader)
            # process_cb combines shares locally; must be idempotent
            out_ints = process_cb(ints)
            # forward combined batches if writer provided
            if writer:
                # split into BATCH_SIZE chunks
                for i in range(0, len(out_ints), BATCH_SIZE):
                    await send_chunk(writer, out_ints[i:i+BATCH_SIZE])
    except (asyncio.IncompleteReadError, ConnectionResetError):
        pass
    finally:
        if writer:
            writer.close(); await writer.wait_closed()
        writer_transport = writer