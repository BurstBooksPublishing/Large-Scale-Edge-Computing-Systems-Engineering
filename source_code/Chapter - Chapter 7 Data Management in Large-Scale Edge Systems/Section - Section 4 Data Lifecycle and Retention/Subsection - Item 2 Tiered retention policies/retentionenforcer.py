#!/usr/bin/env python3
# Minimal, production-ready TTL enforcer for RocksDB -> S3 (MinIO compatible).
import os, time, json, logging
import boto3, plyvel

# Config via env vars for containerized deployments.
DB_PATH = os.environ.get('DB_PATH','/var/lib/app/rocksdb')
S3_ENDPOINT = os.environ['S3_ENDPOINT']            # e.g., http://minio:9000
S3_BUCKET = os.environ.get('S3_BUCKET','edge-archive')
S3_REGION = os.environ.get('S3_REGION','us-east-1')
MAX_AGE = int(os.environ.get('MAX_AGE', 7*24*3600))  # seconds

logging.basicConfig(level=logging.INFO)
db = plyvel.DB(DB_PATH, create_if_missing=False)
s3 = boto3.client('s3',
    endpoint_url=S3_ENDPOINT,
    aws_access_key_id=os.environ['S3_ACCESS_KEY'],
    aws_secret_access_key=os.environ['S3_SECRET_KEY'],
    region_name=S3_REGION,
    config=boto3.session.Config(signature_version='s3v4'))

def key_metadata(raw_value):
    # Stored values are JSON with 'ts' and 'payload' fields.
    obj = json.loads(raw_value)
    return obj.get('ts'), obj.get('payload')

def upload_to_s3(key, ts, payload):
    # Compose object key as ISO timestamp plus original key for idempotency.
    obj_key = f"{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime(ts))}/{key}"
    s3.put_object(Bucket=S3_BUCKET, Key=obj_key, Body=payload,
                  Metadata={'source':'edge-node','ts':str(ts)})
    return obj_key

def enforce_once():
    now = int(time.time())
    batch = db.write_batch()
    moved = 0
    for k, v in db:
        try:
            ts, payload = key_metadata(v.decode('utf-8'))
            if ts is None: continue
            if now - int(ts) >= MAX_AGE:
                obj_key = upload_to_s3(k.decode('utf-8'), int(ts), payload.encode('utf-8'))
                # Verify then delete local entry.
                head = s3.head_object(Bucket=S3_BUCKET, Key=obj_key)
                if head.get('ResponseMetadata',{}).get('HTTPStatusCode') == 200:
                    batch.delete(k)
                    moved += 1
        except Exception as e:
            logging.exception("error processing key")
    batch.write()
    logging.info("moved %d entries to S3", moved)

if __name__ == '__main__':
    # Simple loop; a Kubernetes CronJob can run snapshot enforcement instead.
    while True:
        enforce_once()
        time.sleep(int(os.environ.get('ENFORCE_INTERVAL', 300)))