# Production-ready JWT validator with JWKS caching and backoff.
import time, requests, jwt, threading
from jwt import PyJWKClient

JWKS_URL = "https://auth.example.com/.well-known/jwks.json"
CACHE_TTL = 300  # seconds
LOCK = threading.Lock()

class JWKSCache:
    def __init__(self, url=JWKS_URL, ttl=CACHE_TTL):
        self.url = url
        self.ttl = ttl
        self.jwks_client = None
        self.expiry = 0

    def _fetch(self):
        # network fetch with basic retry
        for _ in range(3):
            resp = requests.get(self.url, timeout=2.0)
            if resp.ok:
                return resp.text
            time.sleep(0.5)
        raise RuntimeError("JWKS fetch failed")

    def get_client(self):
        with LOCK:
            now = time.time()
            if self.jwks_client and now < self.expiry:
                return self.jwks_client
            self._update()
            return self.jwks_client

    def _update(self):
        jwks = self._fetch()  # may raise
        # PyJWKClient accepts the URL; we keep simple by recreating
        self.jwks_client = PyJWKClient(self.url)
        self.expiry = time.time() + self.ttl

jwks_cache = JWKSCache()

def validate_jwt(token, audience, issuer):
    jwks_client = jwks_cache.get_client()
    signing_key = jwks_client.get_signing_key_from_jwt(token).key
    # verify signature, expiry, aud, iss; raises on failure
    payload = jwt.decode(token, signing_key, algorithms=["RS256"],
                         audience=audience, issuer=issuer)
    return payload

# Example usage in edge request handler:
# try:
#     claims = validate_jwt(auth_header_token, audience="edge:telemetry", issuer="https://auth.example.com")
# except Exception as e:
#     deny_request()