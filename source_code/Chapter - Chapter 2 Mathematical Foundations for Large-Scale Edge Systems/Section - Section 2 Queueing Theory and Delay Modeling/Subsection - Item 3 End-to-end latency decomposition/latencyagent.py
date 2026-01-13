#!/usr/bin/env python3
"""
Run as server: python agent.py --mode server --port 8080
Run as client: python agent.py --mode client --server http://mec:8080
Requires: aiohttp
"""
import argparse, asyncio, json, time
from aiohttp import web, ClientSession

def now_ns():
    return time.monotonic_ns()  # monotonic to avoid NTP drift

async def handle_request(request):
    t_recv = now_ns()
    payload = await request.json()
    t_req_sent = payload.get('t_req_sent')  # client-monotonic if available
    # simulate remote processing (replace with real inference hook)
    t_proc_start = now_ns()
    await asyncio.sleep(0.02)  # 20 ms inference placeholder
    t_proc_end = now_ns()
    resp = {
        't_recv': t_recv,
        't_proc_start': t_proc_start,
        't_proc_end': t_proc_end,
        't_resp_sent': now_ns()
    }
    return web.json_response(resp)

async def run_server(port):
    app = web.Application()
    app.router.add_post('/infer', handle_request)
    runner = web.AppRunner(app); await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port); await site.start()
    print(f"Server listening on :{port}")
    while True: await asyncio.sleep(3600)

async def run_client(server_url, frames=10):
    async with ClientSession() as sess:
        for i in range(frames):
            t_req_sent = now_ns()
            data = {'frame_id': i, 't_req_sent': t_req_sent}
            async with sess.post(f"{server_url}/infer", json=data) as resp:
                t_resp_recv = now_ns()
                body = await resp.json()
            # compute decomposition using monotonic timestamps
            delta_net_up = body['t_recv'] - t_req_sent
            delta_server_proc = body['t_proc_end'] - body['t_proc_start']
            delta_net_down = t_resp_recv - body['t_resp_sent']
            e2e = t_resp_recv - t_req_sent
            print(json.dumps({
                'frame': i,
                'e2e_ms': e2e/1e6,
                'up_ms': delta_net_up/1e6,
                'server_proc_ms': delta_server_proc/1e6,
                'down_ms': delta_net_down/1e6
            }))
            await asyncio.sleep(0.05)  # pacing

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument('--mode', choices=('server','client'), required=True)
    p.add_argument('--port', type=int, default=8080)
    p.add_argument('--server', help='server URL for client mode')
    args = p.parse_args()
    if args.mode == 'server':
        asyncio.run(run_server(args.port))
    else:
        asyncio.run(run_client(args.server))