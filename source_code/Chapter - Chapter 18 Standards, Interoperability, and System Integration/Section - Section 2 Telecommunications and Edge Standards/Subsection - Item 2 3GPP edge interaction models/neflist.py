import asyncio, httpx, json, os

NEF_ENDPOINT = "https://nef.op.example.com:443/nnef/v1"  # operator NEF base
MTLS_CERT = ("/etc/ssl/client.crt", "/etc/ssl/client.key")  # mTLS client cert and key
JWT_TOKEN = os.environ.get("AF_JWT")  # AF JWT from operator AAA

async def request_qos_and_steer(session_id: str, qos_profile: dict, target_upf: str):
    # AF intent payload per operator/NEF API; keys follow NEF AF interface schema.
    payload = {
        "afId": "edge-orchestrator-123",
        "sessionId": session_id,
        "intent": {
            "type": "trafficSteering",
            "parameters": {
                "targetUpf": target_upf,
                "qos": qos_profile
            }
        }
    }
    headers = {
        "Authorization": f"Bearer {JWT_TOKEN}",
        "Content-Type": "application/json"
    }
    # HTTP/2 with operator mTLS; timeout and retries per deployment policy.
    r = await session.post(f"{NEF_ENDPOINT}/intents", json=payload, headers=headers, timeout=10.0)
    r.raise_for_status()
    return r.json()

async def main():
    async with httpx.AsyncClient(http2=True, cert=MTLS_CERT, verify="/etc/ssl/ca.pem") as client:
        qos = {"5qi": 5, "gbr_ul_kbps": 5000, "gbr_dl_kbps": 5000}
        resp = await request_qos_and_steer("pdu-abc-001", qos, "upf-edge-01")
        print("NEF response:", json.dumps(resp, indent=2))

if __name__ == "__main__":
    asyncio.run(main())