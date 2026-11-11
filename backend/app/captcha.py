"""Server-side verification of Cloudflare Turnstile tokens.

CAPTCHA is defense-in-depth, not the sole bot control -- it is combined
with server-side login rate limiting (see app/rate_limit.py). Swap
turnstile_verify_url / secret for hCaptcha's endpoint if preferred; the
request/response shape is compatible.
"""
import httpx

from app.config import get_settings

settings = get_settings()


async def verify_captcha(token: str, remote_ip: str | None = None) -> bool:
    if not settings.captcha_enabled:
        return True
    if not token:
        return False
    if not settings.turnstile_secret_key:
        # Misconfiguration: fail closed rather than silently accepting all comers.
        return False

    data = {"secret": settings.turnstile_secret_key, "response": token}
    if remote_ip:
        data["remoteip"] = remote_ip

    async with httpx.AsyncClient(timeout=10) as client:
        try:
            resp = await client.post(settings.turnstile_verify_url, data=data)
            resp.raise_for_status()
            body = resp.json()
        except httpx.HTTPError:
            return False

    return bool(body.get("success"))
