#!/usr/bin/env python3
# production-ready: use OS secure storage or PKCS#11 for private key material
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
import requests

EST_ENROLL_URL = "https://provisioning.example.com/.well-known/est/simpleenroll"
CA_BUNDLE = "/etc/ssl/certs/provisionroot.pem"  # pinned CA bundle
BOOTSTRAP_AUTH = ("bootstrap_id", "bootstrap_secret")  # replace with secure bootstrap method

# generate ephemeral ECDSA key (prefer hardware-backed)
key = ec.generate_private_key(ec.SECP256R1())
csr = x509.CertificateSigningRequestBuilder().subject_name(
    x509.Name([
        x509.NameAttribute(x509.oid.NameOID.COMMON_NAME, "device-serial-1234"),
    ])
).sign(key, hashes.SHA256())

csr_pem = csr.public_bytes(serialization.Encoding.PEM)

# perform HTTPS POST per EST simple enroll (content-type application/pkcs10)
resp = requests.post(
    EST_ENROLL_URL,
    data=csr_pem,
    auth=BOOTSTRAP_AUTH,            # in BRSKI, use voucher or TLS-MFG cert instead
    headers={"Content-Type": "application/pkcs10"},
    verify=CA_BUNDLE,               # enforce pinned CA
    timeout=30
)
resp.raise_for_status()
cert_pem = resp.content

# persist certificate and key securely (example uses local filesystem)
with open("/var/lib/device/cert.pem", "wb") as f:
    f.write(cert_pem)
with open("/var/lib/device/key.pem", "wb") as f:
    f.write(key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.BestAvailableEncryption(b"change_me")
    ))
# production: store key encrypted or in secure element; set file permissions strictly