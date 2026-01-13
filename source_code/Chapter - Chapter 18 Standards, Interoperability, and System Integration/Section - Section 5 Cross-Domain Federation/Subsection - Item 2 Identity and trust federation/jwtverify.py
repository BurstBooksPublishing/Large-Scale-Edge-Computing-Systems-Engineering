import time, requests
from cachetools import TTLCache
from jose import jwt, jwk, JWTError

# TTL cache for remote JWKS, keyed by issuer URL
jwks_cache = TTLCache(maxsize=16, ttl=300)

def fetch_jwks(issuer_url):
    # Fetch and cache JWKS document from OIDC issuer discovery endpoint.
    if issuer_url in jwks_cache:
        return jwks_cache[issuer_url]
    resp = requests.get(f"{issuer_url}/.well-known/openid-configuration", timeout=2.0)
    resp.raise_for_status()
    jwks_uri = resp.json()['jwks_uri']
    jwks = requests.get(jwks_uri, timeout=2.0).json()
    jwks_cache[issuer_url] = jwks
    return jwks

def verify_id_token(token, issuer_url, audience):
    # Validate signature, issuer, audience, expiry. Raises on failure.
    jwks = fetch_jwks(issuer_url)
    headers = jwt.get_unverified_header(token)
    kid = headers.get('kid')
    key = next((k for k in jwks['keys'] if k.get('kid') == kid), None)
    if key is None:
        # Refresh cache once then retry
        jwks_cache.pop(issuer_url, None)
        jwks = fetch_jwks(issuer_url)
        key = next((k for k in jwks['keys'] if k.get('kid') == kid), None)
        if key is None:
            raise JWTError("No matching JWK")
    public_key = jwk.construct(key)
    # Perform verification and claim checks
    claims = jwt.decode(token, public_key.to_pem().decode(), algorithms=[headers.get('alg')], audience=audience, issuer=issuer_url)
    return claims

# Example usage in gateway flow
# claims = verify_id_token(id_token, "https://accounts.example-operator.net", "edge-gateway")