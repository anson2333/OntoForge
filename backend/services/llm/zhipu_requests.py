"""Process-wide serialization for Zhipu's low-concurrency endpoints.

Extraction can run in separate threads/event loops, so an asyncio.Lock alone
would not protect simultaneous PDF imports and connection probes.
"""
import asyncio
import logging
import math
import threading
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

_gate = threading.Lock()
_next_request_at = 0.0
MIN_INTERVAL_SECONDS = 1.0
MAX_RETRIES = 3
MAX_RETRY_WAIT_SECONDS = 60.0


def retry_delay(response, attempt):
    """Honor Retry-After; stop rather than retry early for a long cooldown."""
    value = response.headers.get('Retry-After')
    delay = 3.0 * (2 ** attempt)
    if value:
        try:
            requested = float(value)
        except ValueError:
            try:
                requested = (parsedate_to_datetime(value) - datetime.now(timezone.utc)).total_seconds()
            except (TypeError, ValueError, OverflowError):
                requested = 0.0
        if math.isfinite(requested):
            delay = max(delay, requested)
    return delay if delay <= MAX_RETRY_WAIT_SECONDS else None


async def post_serialized(client, url, **kwargs):
    """Keep one Zhipu request active, including bounded 429 retries and cooldown."""
    global _next_request_at
    while not _gate.acquire(blocking=False):
        await asyncio.sleep(0.05)
    try:
        delay = _next_request_at - time.monotonic()
        if delay > 0:
            await asyncio.sleep(delay)
        for attempt in range(MAX_RETRIES + 1):
            response = await client.post(url, **kwargs)
            if response.status_code != 429 or attempt == MAX_RETRIES:
                return response
            delay = retry_delay(response, attempt)
            if delay is None:
                return response
            await response.aclose()
            logging.info('Zhipu rate limit: waiting %.1fs before retry %s/%s', delay, attempt + 1, MAX_RETRIES)
            await asyncio.sleep(delay)
        raise AssertionError('unreachable')
    finally:
        _next_request_at = time.monotonic() + MIN_INTERVAL_SECONDS
        _gate.release()
