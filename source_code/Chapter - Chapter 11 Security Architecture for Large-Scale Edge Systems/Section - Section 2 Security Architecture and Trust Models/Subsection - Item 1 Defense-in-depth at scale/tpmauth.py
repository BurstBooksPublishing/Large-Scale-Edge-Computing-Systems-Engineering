#!/usr/bin/env python3
# Minimal production-ready helper: create a TPM quote, package PCRs, and POST for verification.
import subprocess, json, sys, requests, logging
logging.basicConfig(level=logging.INFO)

VERIFIER_URL = "https://attest.example.org/verify"  # secure verifier endpoint
NONCE_BYTES = 20

def run(cmd):
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    return proc.stdout

def get_nonce(n=NONCE_BYTES):
    return run(["/usr/bin/head", "-c", str(n), "/dev/urandom"]).hex()

def create_quote(pcrs="0,1,2"):
    nonce = get_nonce()
    # create a quote; output is TPM binary. Use SHA256 and PCR list as needed.
    run(["/usr/bin/tpm2_pcrread", "-o", "pcrs.out"])
    run(["/usr/bin/tpm2_quote", "-C", "0x81010001", "-l", "sha256:"+pcrs,
         "-q", nonce, "-m", "quote.out", "-s", "sig.out"])
    pcrs_json = run(["/usr/bin/tpm2_pcrread", "--output=json"]).decode()
    sig = run(["/usr/bin/xxd", "-p", "sig.out"]).decode()
    with open("quote.out", "rb") as f:
        quote_b64 = f.read().hex()
    return {"nonce": nonce, "pcrs": json.loads(pcrs_json), "quote": quote_b64, "sig": sig}

def post_attestation(payload):
    resp = requests.post(VERIFIER_URL, json=payload, timeout=10, verify="/etc/ssl/certs/ca.pem")
    resp.raise_for_status()
    return resp.json()

def main():
    try:
        att = create_quote()
        logging.info("Posting attestation to verifier")
        result = post_attestation(att)
        logging.info("Verifier response: %s", result)
    except subprocess.CalledProcessError as e:
        logging.error("TPM tool failed: %s", e.stderr.decode())
        sys.exit(2)
    except requests.RequestException as e:
        logging.error("Network error: %s", e)
        sys.exit(3)

if __name__ == "__main__":
    main()