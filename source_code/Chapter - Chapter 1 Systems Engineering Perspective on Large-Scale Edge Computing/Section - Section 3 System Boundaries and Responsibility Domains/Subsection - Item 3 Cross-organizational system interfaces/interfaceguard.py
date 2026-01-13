#!/usr/bin/env python3
import ssl, asyncio, jwt, time
from aiohttp import web
from prometheus_client import Counter, Histogram, start_http_server

# Metrics
REQ_COUNT = Counter('crossorg_requests_total', 'Total requests', ['service'])
LATENCY = Histogram('crossorg_request_latency_seconds', 'Request latency', ['service'])

# JWT public key (PEM) loaded securely; do not hardcode in production
JWT_PUBKEY = open('/etc/keys/jwt_pub.pem').read()

async def handle(request):
    start = time.time()
    # mTLS identity is enforced by server SSL context; map cert to caller identity here.
    auth = request.headers.get('Authorization', '')
    if not auth.startswith('Bearer '):
        raise web.HTTPUnauthorized()
    token = auth.split(None, 1)[1]
    try:
        payload = jwt.decode(token, JWT_PUBKEY, algorithms=['RS256'], audience='edge-analytics')
    except Exception:
        raise web.HTTPUnauthorized()
    # Minimal contract validation: required field and SLO tag
    if 'slo_id' not in payload:
        raise web.HTTPBadRequest()
    # Business logic placeholder; keep fast to meet SLOs
    await asyncio.sleep(0)  # non-blocking placeholder
    LATENCY.labels(service='analytics').observe(time.time()-start)
    REQ_COUNT.labels(service='analytics').inc()
    return web.json_response({'status':'ok','caller':payload.get('sub')})

def create_ssl_context():
    ctx = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    ctx.load_cert_chain('/etc/ssl/server.crt','/etc/ssl/server.key')
    ctx.load_verify_locations('/etc/ssl/ca.crt')  # trust chain for mTLS
    ctx.verify_mode = ssl.CERT_REQUIRED
    return ctx

if __name__ == '__main__':
    start_http_server(9100)  # Prometheus scrape endpoint
    app = web.Application()
    app.add_routes([web.get('/health', handle)])
    web.run_app(app, host='0.0.0.0', port=8443, ssl_context=create_ssl_context())