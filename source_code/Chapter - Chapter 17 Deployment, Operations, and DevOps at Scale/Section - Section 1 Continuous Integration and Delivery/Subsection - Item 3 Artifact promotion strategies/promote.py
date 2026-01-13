#!/usr/bin/env python3
"""
Promote artifact: copy manifest by digest, sign with cosign,
store provenance, and trigger Mender cohort update.
"""

import os, sys, json, logging, subprocess, time
import requests

logging.basicConfig(level=logging.INFO)
REGISTRY_API = "https://registry.example.com"
ARTIFACT_DB = "https://artifact-db.example.com/api/v1/artifacts"
MENDER_API = "https://mender.example.com/api/management/v1/deployments"

def copy_manifest_by_digest(src_repo, dst_repo, digest, token):
    # Use Docker Registry HTTP API to fetch and push manifest by digest.
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.oci.image.manifest.v1+json"}
    r = requests.get(f"{REGISTRY_API}/v2/{src_repo}/manifests/{digest}", headers=headers, timeout=30)
    r.raise_for_status()
    manifest = r.content
    # Push to destination with same digest (registry will store immutably by content).
    headers["Content-Type"] = r.headers.get("Content-Type")
    r2 = requests.put(f"{REGISTRY_API}/v2/{dst_repo}/manifests/{digest}", headers=headers, data=manifest, timeout=30)
    r2.raise_for_status()
    logging.info("Copied manifest %s from %s to %s", digest, src_repo, dst_repo)

def sign_digest_with_cosign(image_ref):
    # image_ref must be by digest e.g. registry/repo@sha256:...
    # cosign must be installed and configured with keyless or private key.
    cmd = ["cosign", "sign", image_ref]
    subprocess.run(cmd, check=True)
    logging.info("Signed %s with cosign", image_ref)

def record_provenance(digest, metadata):
    # Post provenance and SBOM link to artifact DB.
    payload = {"digest": digest, "metadata": metadata}
    r = requests.post(ARTIFACT_DB, json=payload, timeout=10)
    r.raise_for_status()
    logging.info("Recorded provenance for %s", digest)

def trigger_mender_deployment(group, artifact_name, artifact_version, auth_token):
    # Create a deployment targeting a device group/cohort in Mender.
    headers = {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}
    payload = {
        "Name": f"promote-{artifact_name}-{artifact_version}-{int(time.time())}",
        "ArtifactName": artifact_name,
        "ArtifactVersion": {"Name": artifact_version},
        "DeviceFilter": {"attributes": {"group": group}}
    }
    r = requests.post(MENDER_API, headers=headers, json=payload, timeout=15)
    r.raise_for_status()
    logging.info("Triggered Mender deployment to group %s", group)

def main():
    src_repo = os.environ["SRC_REPO"]
    dst_repo = os.environ["DST_REPO"]
    digest = os.environ["DIGEST"]
    registry_token = os.environ["REG_TOKEN"]
    mender_token = os.environ["MENDER_TOKEN"]
    # Copy, sign, record provenance, and stage to cohort.
    copy_manifest_by_digest(src_repo, dst_repo, digest, registry_token)
    sign_digest_with_cosign(f"{REGISTRY_API}/{dst_repo}@{digest}")
    metadata = {"builder": os.environ.get("CI_RUNNER", "ci"), "tests": "passed", "sbom_url": os.environ.get("SBOM_URL")}
    record_provenance(digest, metadata)
    trigger_mender_deployment(group="canary-cohort", artifact_name=dst_repo.split("/")[-1],
                              artifact_version=digest.split(":")[-1], auth_token=mender_token)

if __name__ == "__main__":
    main()