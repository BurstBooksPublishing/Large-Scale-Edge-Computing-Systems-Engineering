#!/usr/bin/env python3
"""
Monitor canary latency via Prometheus, rollback Deployment on sustained breach.
Assumes kubectl in PATH and KUBECONFIG set for target cluster.
"""
import subprocess, time, json, sys, urllib.request

PROM_QUERY = 'histogram_quantile(0.99, sum(rate(http_request_duration_seconds_bucket[1m])) by (le))'
PROM_API = 'http://prometheus:9090/api/v1/query'  # replace with local resolver
NAMESPACE = 'edge-canary'
DEPLOYMENT = 'edge-app'
LATENCY_THRESHOLD_MS = 200
WINDOWS = 3  # consecutive checks
SLEEP = 30

def query_prom(query):
    data = urllib.parse.urlencode({'query': query}).encode()
    with urllib.request.urlopen(PROM_API, data) as r:
        return json.load(r)

def kubectl_rollout_undo(namespace, deployment):
    subprocess.check_call(['kubectl','-n',namespace,'rollout','undo','deployment/'+deployment])

def kubectl_get_rollout_status(namespace, deployment, timeout='2m'):
    subprocess.check_call(['kubectl','-n',namespace,'rollout','status','deployment/'+deployment,'--timeout',timeout])

def main():
    breaches = 0
    while True:
        try:
            resp = query_prom(PROM_QUERY)
            val = float(resp['data']['result'][0]['value'][1]) * 1000.0  # seconds -> ms
        except Exception:
            val = float('inf')
        if val > LATENCY_THRESHOLD_MS:
            breaches += 1
        else:
            breaches = max(0, breaches-1)
        if breaches >= WINDOWS:
            try:
                kubectl_rollout_undo(NAMESPACE, DEPLOYMENT)  # atomic rollback
                kubectl_get_rollout_status(NAMESPACE, DEPLOYMENT)
                # record event to audit log and notify operator
                subprocess.check_call(['logger','-t','edge-rollback',f'Rolled back {DEPLOYMENT} in {NAMESPACE} due to latency {val:.1f}ms'])
            except subprocess.CalledProcessError as e:
                print('rollback failed', e, file=sys.stderr)
            breaches = 0
        time.sleep(SLEEP)

if __name__ == '__main__':
    main()