"""Public IP checks: which address do websites see when we connect?

Each service is asked at the same time (asyncio.gather), so the whole check
takes as long as the slowest service, not the sum of all of them.
"""

import asyncio
from collections import Counter
from ipaddress import IPv4Address

import httpx

from vpnleakcheck.endpoints import IPV4_ENDPOINTS, Endpoint
from vpnleakcheck.result import CheckResult, Status

IPV4_CHECK = "ipv4"


async def _ask_ipv4(
    client: httpx.AsyncClient, endpoint: Endpoint
) -> IPv4Address | None:
    """Ask one service for our IPv4 address. None means it gave no usable answer."""
    try:
        response = await client.get(endpoint.url)
        response.raise_for_status()
        # Some services end the body with a newline, so strip before parsing.
        return IPv4Address(response.text.strip())
    except (httpx.HTTPError, ValueError):
        # HTTPError: timeout, no connection, TLS failure, or a 4xx/5xx status.
        # ValueError: the body isn't an IPv4 address (e.g. a login page).
        return None


async def check_ipv4(
    client: httpx.AsyncClient,
    endpoints: tuple[Endpoint, ...] = IPV4_ENDPOINTS,
) -> CheckResult:
    """Ask every IPv4 service for our public address and compare the answers.

    The caller owns `client`, so one client (and one timeout setting) can be
    shared by every check in a run.
    """
    replies = await asyncio.gather(*(_ask_ipv4(client, e) for e in endpoints))

    answered = {
        endpoint.name: ip
        for endpoint, ip in zip(endpoints, replies, strict=True)
        if ip is not None
    }
    silent = [endpoint.name for endpoint in endpoints if endpoint.name not in answered]

    if not answered:
        return CheckResult(
            name=IPV4_CHECK,
            status=Status.UNAVAILABLE,
            reason="No IPv4 service answered (offline, or the network blocks them)",
        )

    # Majority wins. On a tie, Counter keeps first-seen order, so the service
    # listed first in endpoints.py wins.
    counts = Counter(answered.values())
    best_ip, _ = counts.most_common(1)[0]

    if len(counts) > 1:
        seen = ", ".join(f"{name} saw {ip}" for name, ip in answered.items())
        status = Status.WARNING
        reason = f"IPv4 services disagree: {seen}"
    else:
        status = Status.OK
        reason = f"Confirmed by {', '.join(answered)}"

    if silent:
        reason += f"; no answer from {', '.join(silent)}"

    return CheckResult(
        name=IPV4_CHECK, status=status, value=str(best_ip), reason=reason
    )
