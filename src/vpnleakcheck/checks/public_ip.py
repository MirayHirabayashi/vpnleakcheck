"""Public IP checks: which address do websites see when we connect?

Each service is asked at the same time (asyncio.gather), so the whole check
takes as long as the slowest service, not the sum of all of them.
"""

import asyncio
from collections import Counter
from collections.abc import Mapping
from enum import Enum
from ipaddress import IPv4Address, IPv6Address

import httpx

from vpnleakcheck.endpoints import IPV4_ENDPOINTS, IPV6_ENDPOINTS, Endpoint
from vpnleakcheck.result import CheckResult, Status

IPV4_CHECK = "ipv4"
IPV6_CHECK = "ipv6"


def _compare(
    answered: Mapping[str, IPv4Address | IPv6Address], silent: list[str], label: str
) -> tuple[str, Status, str]:
    """Pick the majority address and explain it. `answered` must not be empty.

    Returns (address, status, reason). On a tie, Counter keeps first-seen
    order, so the service listed first in endpoints.py wins.
    """
    counts = Counter(answered.values())
    best_ip, _ = counts.most_common(1)[0]

    if len(counts) > 1:
        seen = ", ".join(f"{name} saw {ip}" for name, ip in answered.items())
        status = Status.WARNING
        reason = f"{label} services disagree: {seen}"
    else:
        status = Status.OK
        reason = f"Confirmed by {', '.join(answered)}"

    if silent:
        reason += f"; no answer from {', '.join(silent)}"

    return str(best_ip), status, reason


# ---------------------------------------------------------------- IPv4 ------


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

    value, status, reason = _compare(answered, silent, "IPv4")
    return CheckResult(name=IPV4_CHECK, status=status, value=value, reason=reason)


# ---------------------------------------------------------------- IPv6 ------


class _NoAddress(Enum):
    """Why an IPv6 service gave us no address. The difference matters here."""

    # We never connected: no IPv6 route out of this machine. Safe.
    NO_ROUTE = "no_route"
    # We connected over IPv6 (so a route exists) but got no usable address:
    # an error status, a slow reply, or a body that isn't a global IPv6.
    BAD_ANSWER = "bad_answer"


async def _ask_ipv6(
    client: httpx.AsyncClient, endpoint: Endpoint
) -> IPv6Address | _NoAddress:
    """Ask one IPv6-only service for our IPv6 address."""
    try:
        response = await client.get(endpoint.url)
        response.raise_for_status()
        address = IPv6Address(response.text.strip())
    except (httpx.ConnectError, httpx.ConnectTimeout):
        # ConnectError: "network unreachable" (no IPv6 route at all), or the
        # name didn't resolve. ConnectTimeout: IPv6 is half set up and the
        # packets go nowhere. Either way nothing reached the internet.
        # Known gap: httpx also reports a failed TLS handshake as ConnectError,
        # even though TCP got through. Rare enough to accept for now.
        return _NoAddress.NO_ROUTE
    except (httpx.HTTPError, ValueError):
        # Connected, then something went wrong: 4xx/5xx, read timeout, or a
        # body that isn't an IPv6 address.
        return _NoAddress.BAD_ANSWER

    # Only a globally routable address counts. Link-local fe80::, loopback,
    # unique-local fc00::/7 and documentation 2001:db8:: never identify us on
    # the internet, so a service returning one is giving a bad answer.
    if not address.is_global:
        return _NoAddress.BAD_ANSWER
    return address


async def check_ipv6(
    client: httpx.AsyncClient,
    endpoints: tuple[Endpoint, ...] = IPV6_ENDPOINTS,
) -> CheckResult:
    """Find out whether this machine can reach the internet over IPv6.

    Failure is the good outcome: if no service can be reached, nothing can leak
    over IPv6. An address found here is reported as `ok` with the address as
    `value`; whether it belongs to the VPN or the local ISP is decided later by
    the ownership lookup and the verdict, not here.
    """
    replies = await asyncio.gather(*(_ask_ipv6(client, e) for e in endpoints))
    by_name = {e.name: reply for e, reply in zip(endpoints, replies, strict=True)}

    answered = {name: ip for name, ip in by_name.items() if isinstance(ip, IPv6Address)}
    silent = [name for name in by_name if name not in answered]

    if answered:
        # One real address from any service proves an IPv6 route exists.
        value, status, reason = _compare(answered, silent, "IPv6")
        return CheckResult(name=IPV6_CHECK, status=status, value=value, reason=reason)

    reached = [name for name, r in by_name.items() if r is _NoAddress.BAD_ANSWER]
    if reached:
        # We got through over IPv6 but learned no address. A route exists, so
        # we can't call this safe.
        return CheckResult(
            name=IPV6_CHECK,
            status=Status.UNAVAILABLE,
            reason=(
                f"Reached {', '.join(reached)} over IPv6 but got no usable "
                "address, so an IPv6 route exists but couldn't be checked"
            ),
        )

    return CheckResult(
        name=IPV6_CHECK,
        status=Status.OK,
        reason="No IPv6 route to the internet, so nothing can leak over IPv6",
    )
