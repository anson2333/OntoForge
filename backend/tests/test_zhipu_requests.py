"""Zhipu coordination must also work across extraction threads/event loops."""
import asyncio
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import httpx
import pytest

from backend.services.llm import zhipu_requests as limiter


@pytest.fixture(autouse=True)
def no_cooldown(monkeypatch):
    monkeypatch.setattr(limiter, 'MIN_INTERVAL_SECONDS', 0)
    monkeypatch.setattr(limiter, '_next_request_at', 0)


def test_serializes_across_threads_and_provider_instances():
    active = 0
    peak = 0
    lock = threading.Lock()

    class Client:
        async def post(self, *args, **kwargs):
            nonlocal active, peak
            with lock:
                active += 1
                peak = max(peak, active)
            await asyncio.sleep(0.02)
            with lock:
                active -= 1
            return httpx.Response(200)

    def run(_):
        return asyncio.run(limiter.post_serialized(Client(), 'https://fixture.invalid')).status_code

    with ThreadPoolExecutor(max_workers=4) as pool:
        assert list(pool.map(run, range(4))) == [200] * 4
    assert peak == 1


@pytest.mark.asyncio
async def test_429_retries_are_bounded_and_respect_retry_after(monkeypatch):
    delays = []
    calls = []

    async def sleep(delay):
        delays.append(delay)

    class Client:
        async def post(self, *args, **kwargs):
            calls.append(1)
            return httpx.Response(429, headers={'Retry-After': '7'})

    monkeypatch.setattr(limiter.asyncio, 'sleep', sleep)
    response = await limiter.post_serialized(Client(), 'https://fixture.invalid')
    assert response.status_code == 429
    assert len(calls) == 4
    assert delays == [7, 7, 12]
    assert not limiter._gate.locked()


@pytest.mark.asyncio
async def test_auth_failure_is_not_retried_and_releases_gate():
    class Client:
        calls = 0

        async def post(self, *args, **kwargs):
            self.calls += 1
            return httpx.Response(401)

    client = Client()
    assert (await limiter.post_serialized(client, 'https://fixture.invalid')).status_code == 401
    assert client.calls == 1
    assert not limiter._gate.locked()


@pytest.mark.asyncio
async def test_cancellation_releases_gate():
    started = asyncio.Event()

    class Client:
        async def post(self, *args, **kwargs):
            started.set()
            await asyncio.Event().wait()

    task = asyncio.create_task(limiter.post_serialized(Client(), 'https://fixture.invalid'))
    await started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert not limiter._gate.locked()


def test_long_retry_after_is_not_shortened():
    assert limiter.retry_delay(httpx.Response(429, headers={'Retry-After': '120'}), 0) is None


@pytest.mark.asyncio
async def test_rate_limited_request_recovers(monkeypatch):
    async def sleep(_):
        pass

    class Client:
        calls = 0

        async def post(self, *args, **kwargs):
            self.calls += 1
            return httpx.Response(429 if self.calls == 1 else 200)

    monkeypatch.setattr(limiter.asyncio, 'sleep', sleep)
    client = Client()
    assert (await limiter.post_serialized(client, 'https://fixture.invalid')).status_code == 200
    assert client.calls == 2


@pytest.mark.asyncio
async def test_successful_requests_have_cooldown(monkeypatch):
    monkeypatch.setattr(limiter, 'MIN_INTERVAL_SECONDS', 0.02)

    class Client:
        async def post(self, *args, **kwargs):
            return httpx.Response(200)

    await limiter.post_serialized(Client(), 'https://fixture.invalid')
    started = time.monotonic()
    await limiter.post_serialized(Client(), 'https://fixture.invalid')
    assert time.monotonic() - started >= 0.015
