import time


def with_retry(fn, attempts=3, delay=15, backoff=2, label="operation"):
    """Call fn() with retries; retries on any exception with exponential backoff."""
    current_delay = delay
    for attempt in range(1, attempts + 1):
        try:
            return fn()
        except Exception as exc:
            print(f"[retry] {label} failed on attempt {attempt}/{attempts}: {exc}", flush=True)
            if attempt == attempts:
                raise
            time.sleep(current_delay)
            current_delay *= backoff
