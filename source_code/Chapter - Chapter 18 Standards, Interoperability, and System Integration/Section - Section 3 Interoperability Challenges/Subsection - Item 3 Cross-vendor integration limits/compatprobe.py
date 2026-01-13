#!/usr/bin/env python3
# Production-ready async probe: concurrent API probes, schema validation, TLS checks.
import asyncio, ssl, logging
from typing import Dict, Any, List
import aiohttp, jsonschema

logging.basicConfig(level=logging.INFO)
SEM = asyncio.Semaphore(50)  # concurrency limit

async def check_tls(host: str, port: int = 443) -> Dict[str, Any]:
    ctx = ssl.create_default_context()
    ctx.check_hostname = True
    ctx.verify_mode = ssl.CERT_REQUIRED
    loop = asyncio.get_event_loop()
    try:
        # open connection and inspect negotiated proto/cipher
        reader, writer = await asyncio.open_connection(host, port, ssl=ctx)
        sslobj = writer.get_extra_info('ssl_object')
        info = {'cipher': sslobj.cipher(), 'version': sslobj.version()}
        writer.close()
        await writer.wait_closed()
        return {'ok': True, 'tls': info}
    except Exception as e:
        return {'ok': False, 'error': str(e)}

async def probe_api(endpoint: str, schema: Dict[str, Any], headers: Dict[str, str] = None) -> Dict[str, Any]:
    async with SEM:
        try:
            async with aiohttp.ClientSession() as sess:
                async with sess.get(endpoint, headers=headers or {}, timeout=10) as resp:
                    body = await resp.json(content_type=None)
                    jsonschema.validate(instance=body, schema=schema)  # raises on failure
                    return {'endpoint': endpoint, 'status': resp.status, 'valid': True}
        except jsonschema.ValidationError as ve:
            return {'endpoint': endpoint, 'valid': False, 'schema_error': str(ve)}
        except Exception as e:
            return {'endpoint': endpoint, 'error': str(e)}

async def run_checks(targets: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    tasks = []
    for t in targets:
        tasks.append(probe_api(t['url'], t['schema'], t.get('headers')))
        tasks.append(check_tls(t['host'], t.get('port', 443)))
    return await asyncio.gather(*tasks)

# Example invocation (populate targets from CI/test inventory)
if __name__ == '__main__':
    import json
    targets = [
        {'url': 'https://edge-vendor-a.example/api/status', 'schema': {"type":"object","properties":{"uptime":{"type":"number"}}}, 'host': 'edge-vendor-a.example'},
        {'url': 'https://edge-vendor-b.example/api/status', 'schema': {"type":"object","properties":{"uptime":{"type":"number"}}}, 'host': 'edge-vendor-b.example'}
    ]
    results = asyncio.run(run_checks(targets))
    print(json.dumps(results, indent=2))