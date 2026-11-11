"""Redis-backed sliding-window semaphore capping concurrent result
downloads (see DEPLOYMENT.md / config.max_concurrent_downloads) so
simultaneous zip-builds don't overrun the single-VM deploy's disk
headroom. A ZSET rather than a bare INCR/DECR counter: a request that
crashes mid-download (before its `finally`/BackgroundTask runs) can't leak
a slot forever -- the stale member just ages out of the window on the next
acquire attempt, no separate cleanup task needed.
"""
import time
import uuid

import redis.asyncio as redis

from app.config import get_settings

settings = get_settings()
_redis = redis.from_url(settings.redis_url, decode_responses=True)

_KEY = "dietnet:download_slots"

# Atomic in one round trip: drop members older than the TTL, then admit the
# new one only if that leaves room. Must be a single script, not separate
# ZREMRANGEBYSCORE/ZCARD/ZADD calls, or two concurrent requests could both
# pass the ZCARD check before either ZADDs (the exact race a semaphore
# exists to prevent).
_ACQUIRE_SCRIPT = """
redis.call('ZREMRANGEBYSCORE', KEYS[1], '-inf', ARGV[1])
if redis.call('ZCARD', KEYS[1]) < tonumber(ARGV[2]) then
    redis.call('ZADD', KEYS[1], ARGV[3], ARGV[4])
    return 1
else
    return 0
end
"""


async def acquire_download_slot() -> str | None:
    """Returns a slot id on success, or None if the cap is already full."""
    member = str(uuid.uuid4())
    now = time.time()
    cutoff = now - settings.download_slot_ttl_seconds
    acquired = await _redis.eval(
        _ACQUIRE_SCRIPT, 1, _KEY, cutoff, settings.max_concurrent_downloads, now, member
    )
    return member if acquired else None


async def release_download_slot(member: str) -> None:
    await _redis.zrem(_KEY, member)
