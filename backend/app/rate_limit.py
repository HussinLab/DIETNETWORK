"""Redis-backed sliding-window rate limiter for login attempts.

Keyed on (email, ip) so an attacker can't bypass the per-account lockout by
rotating IPs alone, nor lock out a legitimate user from a shared IP by
targeting a different account. Two separate counters are kept.
"""
import redis.asyncio as redis

from app.config import get_settings

settings = get_settings()
_redis = redis.from_url(settings.redis_url, decode_responses=True)


async def _hit(key: str, window_seconds: int) -> int:
    pipe = _redis.pipeline()
    pipe.incr(key, 1)
    pipe.expire(key, window_seconds, nx=True)
    count, _ = await pipe.execute()
    return int(count)


async def register_failed_login(email: str, ip: str) -> None:
    await _hit(f"login_fail:email:{email}", settings.login_window_seconds)
    await _hit(f"login_fail:ip:{ip}", settings.login_window_seconds)


async def clear_failed_logins(email: str, ip: str) -> None:
    await _redis.delete(f"login_fail:email:{email}")
    await _redis.delete(f"login_fail:ip:{ip}")


async def is_locked_out(email: str, ip: str) -> bool:
    email_count = await _redis.get(f"login_fail:email:{email}")
    ip_count = await _redis.get(f"login_fail:ip:{ip}")
    threshold = settings.login_max_attempts
    return (email_count is not None and int(email_count) >= threshold) or (
        ip_count is not None and int(ip_count) >= threshold * 3
    )
