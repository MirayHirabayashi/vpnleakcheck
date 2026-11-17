"""Tests for the public IPv6 check.

For IPv6, failing to connect is the good outcome (no route, nothing to leak),
so most tests here are about telling "never connected" apart from "connected
but got a bad answer". respx fakes every response; nothing goes online.
"""

import asyncio
from pathlib import Path

import httpx
import pytest
import respx

from vpnleakcheck.checks.public_ip import check_ipv6
from vpnleakcheck.endpoints import IPV6_ENDPOINTS, Endpoint
from vpnleakcheck.result import CheckResult, Status

FIXTURES = Path(__file__).parent / "fixtures"
IPIFY, IDENT_ME = IPV6_ENDPOINTS
# A made-up but globally routable address. 2001:db8:: (the documentation
# prefix) can't be used: it isn't global, so the check would reject it.
HOME_IPV6 = "2a02:8109:b6c0:1d00::42"


def fixture(name: str) -> str:
    return (FIXTURES / name).read_text()


def run_check(endpoints: tuple[Endpoint, ...] = IPV6_ENDPOINTS) -> CheckResult:
    """Run the async check from a normal (sync) test function."""

    async def go() -> CheckResult:
        async with httpx.AsyncClient() as client:
            return await check_ipv6(client, endpoints)

    return asyncio.run(go())


def mock(endpoint: Endpoint, outcome: str | Exception | httpx.Response) -> None:
    """Make `endpoint` return a body, raise an error, or return a response."""
    route = respx.get(endpoint.url)
    if isinstance(outcome, str):
        route.respond(text=outcome)
    elif isinstance(outcome, httpx.Response):
        route.mock(return_value=outcome)
    else:
        route.mock(side_effect=outcome)


@respx.mock
def test_both_services_see_an_address() -> None:
    # The ident.me fixture ends in a newline; the check must strip it.
    mock(IPIFY, fixture("ipv6_ipify.txt"))
    mock(IDENT_ME, fixture("ipv6_identme.txt"))

    result = run_check()

    assert result.name == "ipv6"
    # ok, not leak: whether this address is the VPN's or the ISP's is decided
    # later, by the ownership lookup and the verdict.
    assert result.status is Status.OK
    assert result.value == HOME_IPV6
    assert result.reason == "Confirmed by ipify, ident.me"


@pytest.mark.parametrize(
    "failure",
    [
        httpx.ConnectError("[Errno 51] Network is unreachable"),
        httpx.ConnectTimeout("timed out"),
    ],
    ids=["unreachable", "connect-timeout"],
)
@respx.mock
def test_no_connection_means_no_ipv6_route(failure: Exception) -> None:
    mock(IPIFY, failure)
    mock(IDENT_ME, failure)

    result = run_check()

    assert result.status is Status.OK
    assert result.value is None
    assert "No IPv6 route" in result.reason


@respx.mock
def test_one_address_is_enough_to_prove_a_route() -> None:
    # If only one service is down, the other one's answer still counts.
    # This is why there are two services: one outage must not read as "safe".
    mock(IPIFY, httpx.ConnectTimeout("timed out"))
    mock(IDENT_ME, HOME_IPV6)

    result = run_check()

    assert result.status is Status.OK
    assert result.value == HOME_IPV6
    assert result.reason == "Confirmed by ident.me; no answer from ipify"


@pytest.mark.parametrize(
    "outcome",
    [
        httpx.Response(503, text="Service Unavailable"),
        httpx.ReadTimeout("connected, but no reply"),
        "<html><title>Hotel Wi-Fi login</title></html>",
        "fe80::1c2b:3aff:fe4d:5e6f",  # link-local: only valid on this Wi-Fi
        "fd12:3456:789a::1",  # unique-local: a private address
        "203.0.113.24",  # an IPv4 address from an IPv6-only service
    ],
    ids=["http-503", "read-timeout", "login-page", "link-local", "ula", "ipv4"],
)
@respx.mock
def test_connected_but_no_usable_address_is_unavailable(
    outcome: str | Exception | httpx.Response,
) -> None:
    # Getting any reply means packets made it out over IPv6, so a route
    # exists. We can't call that safe, and we have no address to judge.
    mock(IPIFY, outcome)
    mock(IDENT_ME, httpx.ConnectTimeout("timed out"))

    result = run_check()

    assert result.status is Status.UNAVAILABLE
    assert result.value is None
    assert "Reached ipify over IPv6" in result.reason


@respx.mock
def test_link_local_answer_is_ignored_when_the_other_service_answers() -> None:
    mock(IPIFY, "fe80::1")
    mock(IDENT_ME, HOME_IPV6)

    result = run_check()

    assert result.status is Status.OK
    assert result.value == HOME_IPV6


@respx.mock
def test_services_disagree_gives_a_warning() -> None:
    other = "2a01:4f8:c0c:1234::1"
    mock(IPIFY, HOME_IPV6)
    mock(IDENT_ME, other)

    result = run_check()

    assert result.status is Status.WARNING
    # No majority with two services, so the first one listed wins.
    assert result.value == HOME_IPV6
    assert f"ipify saw {HOME_IPV6}" in result.reason
    assert f"ident.me saw {other}" in result.reason
