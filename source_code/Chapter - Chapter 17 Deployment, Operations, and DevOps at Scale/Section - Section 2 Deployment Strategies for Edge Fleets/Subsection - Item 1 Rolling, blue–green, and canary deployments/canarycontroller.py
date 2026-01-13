#!/usr/bin/env python3
# Requires: pip install kubernetes requests
import time, math, sys, requests
from kubernetes import client, config

# Config: cluster context or in-cluster
config.load_kube_config()  # or load_incluster_config()
apps = client.AppsV1Api()
core = client.CoreV1Api()

NAMESPACE = "default"
DEPLOYMENT = "edge-service"
CANARY_LABEL = "canary-rollout=true"
BATCH_SIZE = 5
TEST_DURATION = 60   # seconds observation per batch
PROMETHEUS_URL = "http://prometheus:9090/api/v1/query"
METRIC_QUERY = 'avg_over_time(http_requests_success_ratio[1m])'  # example
METRIC_THRESHOLD = 0.99

def nodes_matching_label(label):
    items = core.list_node(label_selector=label).items
    return [n.metadata.name for n in items]

def set_node_affinity(pod_template, node_names):
    # set nodeName-based affinity to schedule pods on selected nodes
    pod_template.spec.node_selector = {"kubernetes.io/hostname": node_names[0]}  # simple; production use node affinity
    return pod_template

def promote_batch(node_subset):
    # patch deployment with nodeSelector or create per-node DaemonSet variant
    # This example assumes a per-node deployment variant exists; adapt as needed.
    # Scale up a canary deployment targeted to node_subset...
    pass  # platform-specific implementation

def query_prometheus(query):
    r = requests.get(PROMETHEUS_URL, params={"query": query}, timeout=10)
    r.raise_for_status()
    data = r.json()
    if data["status"] != "success": return None
    return float(data["data"]["result"][0]["value"][1]) if data["data"]["result"] else None

def wait_for_readiness(deployment, timeout=120):
    end = time.time()+timeout
    while time.time()
\subsection{Item 2:  Progressive delivery and feature gating}
Building on rolling, blue–green, and canary patterns, progressive delivery and feature gating add fine-grained control and metric-driven automation to limit blast radius across heterogeneous edge fleets. These techniques shift decisions from binary deployment events to instrumented, continuous evaluation of features on selected devices or cohorts.

Concept: progressive delivery uses feature flags and staged rollouts to decouple code deployment from feature activation. Feature gating evaluates functionality at runtime and can be toggled remotely. In edge contexts this must account for intermittent connectivity, constrained SoCs (for example NVIDIA Jetson, Raspberry Pi, or ARM Cortex-M running Zephyr), and orchestration stacks such as K3s, KubeEdge, AWS IoT Greengrass, or Azure IoT Edge. Key properties:
- Local evaluation: flags cached and evaluated on-device to maintain operation under network loss.
- Signed flag updates: use TPM or secure element for authenticity.
- Cohorts: group devices by hardware, geography, or operational risk (e.g., industrial PLCs vs. cameras).

Theory: reliable progressive delivery requires statistically-sound decision rules to promote or roll back a feature. For a metric with means mu_c and mu_t and variances sigma_c^2 and sigma_t^2, the sample size n per cohort for a two-sided z-test at significance alpha and power 1-beta approximates
\begin{equation}[H]\label{eq:sample_size}
n \approx \frac{\left(Z_{1-\alpha/2}+Z_{1-\beta}\right)^2\left(\sigma_c^2+\sigma_t^2\right)}{\Delta^2},
\end{equation}
where $\Delta=|\mu_t-\mu_c|$ is the minimum detectable effect. For latency-sensitive edge functions, set $\Delta$ to the maximum acceptable increase in tail latency. Use sequential testing (e.g., Sequential Probability Ratio Test) to reduce exposure time while preserving error bounds. Combine these tests with safety gates: anomaly detectors on throughput, CPU, memory, and error-rate, each with strict thresholds that trigger immediate rollback or feature disable.

Example: staged ML model replacement on a fleet of smart cameras. Strategy:
1. Select a small cohort of Jetson devices in one region with similar network conditions.
2. Deploy model artifact to those devices via artifact promotion and enable feature flag that switches inference runtime to the new model.
3. Monitor object-detection mAP, 99th-percentile latency, GPU utilization, and false-positive rate from device telemetry pushed to Prometheus remote write.
4. Apply equation (1) to determine required sample size for detecting a 5% degradation in mAP with 95% confidence and 80% power.
5. If tests pass, expand cohort exponentially (5%, 20%, 50%, 100%) while continuing safety gating.

Application: operational controller implementation. The following production-ready Python orchestrator toggles a feature flag group via Unleash and evaluates Prometheus metrics to decide staged promotion. It uses the Kubernetes API only to label candidate nodes; it runs as a resilient control-plane microservice (suitable for K3s or KubeEdge control nodes). Replace endpoints, credentials, and metric names for your fleet.

\begin{lstlisting}[language=Python,caption={Progressive delivery controller: Unleash + Prometheus + Kubernetes labeling},label={lst:prog_ctrl}]
#!/usr/bin/env python3
# Minimal, production-quality orchestrator skeleton (async, retries, auth)
import asyncio, time, os, statistics
from kubernetes import client, config
import aiohttp

UNLEASH_API = os.environ['UNLEASH_API']        # e.g., https://unleash.example/api
UNLEASH_TOKEN = os.environ['UNLEASH_TOKEN']
PROM_API = os.environ['PROM_API']              # e.g., http://prometheus:9090/api/v1/query_range
K8S_LABEL_KEY = "progressive.canary"
METRIC = os.environ.get('TARGET_METRIC', 'edge_inference_latency_seconds')
SAMPLE_WINDOW = '5m'

# init k8s client
config.load_incluster_config()
v1 = client.CoreV1Api()

async def set_unleash_flag(feature_name, enabled, strategy=None):
    url = f"{UNLEASH_API}/admin/features/{feature_name}"
    headers = {'Authorization': UNLEASH_TOKEN, 'Content-Type': 'application/json'}
    payload = {'enabled': enabled}
    if strategy: payload['strategies'] = strategy
    async with aiohttp.ClientSession() as s:
        async with s.patch(url, json=payload, headers=headers, timeout=30) as r:
            r.raise_for_status()
            return await r.json()

async def query_prom(query):
    params = {'query': query, 'start': str(int(time.time())-600), 'end': str(int(time.time())), 'step': '15s'}
    async with aiohttp.ClientSession() as s:
        async with s.get(PROM_API, params=params, timeout=30) as r:
            r.raise_for_status()
            data = await r.json()
            return data['data']['result']

def label_nodes(node_names):
    for name in node_names:
        body = {'metadata': {'labels': {K8S_LABEL_KEY: 'true'}}}
        v1.patch_node(name, body)  # raises on failure

def unlable_nodes(node_names):
    for name in node_names:
        body = {'metadata': {'labels': {K8S_LABEL_KEY: None}}}
        v1.patch_node(name, body)

def extract_metric_series(prom_result):
    vals = []
    for res in prom_result:
        for v in res['values']:
            vals.append(float(v[1]))
    return vals

async def evaluate_and_promote(feature, control_query, treatment_query, min_effect=0.05):
    ctl = await query_prom(control_query)
    trt = await query_prom(treatment_query)
    x = extract_metric_series(ctl); y = extract_metric_series(trt)
    if not x or not y: return False
    mu_c, mu_t = statistics.mean(x), statistics.mean(y)
    sigma_c, sigma_t = statistics.pstdev(x), statistics.pstdev(y)
    # simple decision: reject if treatment worse than control beyond min_effect
    if (mu_t - mu_c)/mu_c > min_effect:  # metric increased > min_effect -> fail
        await set_unleash_flag(feature, False)  # disable immediately
        return False
    return True

async def rollout(feature, node_batches):
    # node_batches: list of lists; incremental cohorts
    for batch in node_batches:
        label_nodes(batch)
        await set_unleash_flag(feature, True, strategy=[{'name': 'default'}])  # enable for labeled nodes
        await asyncio.sleep(30)  # wait for telemetry to arrive
        control_q = f'{METRIC}{{{K8S_LABEL_KEY}!~"true"}}'
        treat_q = f'{METRIC}{{{K8S_LABEL_KEY}="true"}}'
        ok = await evaluate_and_promote(feature, control_q, treat_q)
        if not ok:
            unlable_nodes(batch); return False
    return True

# run loop (example)
if __name__ == "__main__":
    feature = "new-model-v2"
    # define cohorts (node names discovered via API in real system)
    cohorts = [["node-a"], ["node-b","node-c"], ["node-d","node-e","node-f"]]
    asyncio.run(rollout(feature, cohorts))