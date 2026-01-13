import secrets
from typing import List, Tuple

Prime = 2**127 - 1  # large prime modulus for GF(p)

def _eval_poly(coeffs: List[int], x: int, p: int=Prime) -> int:
    # Horner's rule for polynomial evaluation mod p.
    res = 0
    for a in reversed(coeffs):
        res = (res * x + a) % p
    return res

def share_secret(secret: int, t: int, n: int, p: int=Prime) -> List[Tuple[int,int]]:
    if not (1 <= t <= n):
        raise ValueError("require 1 <= t <= n")
    secret %= p
    coeffs = [secret] + [secrets.randbelow(p) for _ in range(t-1)]  # random polynomial
    shares = [(i+1, _eval_poly(coeffs, i+1, p)) for i in range(n)]
    return shares

def _mod_inv(a: int, p: int=Prime) -> int:
    # Modular inverse using Python 3.8+ pow with negative exponent.
    return pow(a, -1, p)

def reconstruct(shares: List[Tuple[int,int]], p: int=Prime) -> int:
    # Lagrange interpolation at x=0
    if len(shares) == 0:
        raise ValueError("need at least one share")
    secret = 0
    for i, (xi, yi) in enumerate(shares):
        num = 1
        den = 1
        for j, (xj, _) in enumerate(shares):
            if i == j:
                continue
            num = (num * xj) % p
            den = (den * (xj - xi)) % p
        lag = num * _mod_inv(den, p) % p
        secret = (secret + yi * lag) % p
    return secret

# Example usage (run-time code): generate shares and reconstruct.
# s = 42
# shares = share_secret(s, t=3, n=5)
# s_rec = reconstruct(shares[:3])