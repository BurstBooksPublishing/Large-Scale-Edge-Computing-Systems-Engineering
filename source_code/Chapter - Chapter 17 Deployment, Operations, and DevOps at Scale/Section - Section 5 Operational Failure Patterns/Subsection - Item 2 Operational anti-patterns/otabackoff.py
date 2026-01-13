import time, random, threading, requests

# Token-bucket limiter class (thread-safe)
class TokenBucket:
    def __init__(self, rate, burst):
        self.rate = rate          # tokens per second
        self.capacity = burst
        self.tokens = burst
        self.lock = threading.Lock()
        self.last = time.monotonic()
    def consume(self, tokens=1.0):
        with self.lock:
            now = time.monotonic()
            self.tokens = min(self.capacity, self.tokens + (now - self.last) * self.rate)
            self.last = now
            if self.tokens >= tokens:
                self.tokens -= tokens
                return True
            return False

# Circuit breaker simple state
class CircuitBreaker:
    def __init__(self, fail_threshold=5, reset_timeout=30):
        self.fail_threshold = fail_threshold
        self.reset_timeout = reset_timeout
        self.fail_count = 0
        self.open_until = 0
    def record_success(self):
        self.fail_count = 0
    def record_failure(self):
        self.fail_count += 1
        if self.fail_count >= self.fail_threshold:
            self.open_until = time.monotonic() + self.reset_timeout
    def allow(self):
        if time.monotonic() < self.open_until:
            return False
        return True

# Fetch with exponential backoff + full jitter
def fetch_with_backoff(url, session=None, max_attempts=6, base=0.5, max_backoff=30):
    if session is None:
        session = requests.Session()
    for attempt in range(1, max_attempts + 1):
        try:
            resp = session.get(url, timeout=10)
            resp.raise_for_status()
            return resp.content
        except requests.RequestException:
            # Exponential backoff with full jitter
            exp = min(max_backoff, base * (2 ** (attempt - 1)))
            sleep = random.uniform(0, exp)
            time.sleep(sleep)
    raise RuntimeError("max attempts reached")

# Operational loop using limiter and circuit breaker
limiter = TokenBucket(rate=1.0, burst=5)   # control attempts per second
circuit = CircuitBreaker(fail_threshold=3, reset_timeout=60)

def ota_poll(url):
    if not circuit.allow():
        # fail-fast and schedule later, avoiding retries that could harm central services
        return
    if not limiter.consume():
        return
    try:
        data = fetch_with_backoff(url)
        circuit.record_success()
        # apply update atomically, then restart services via systemd
    except Exception:
        circuit.record_failure()

# Example use: scheduled run every 30s, driven by system scheduler