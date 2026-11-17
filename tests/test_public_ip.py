"""Tests for the public IPv4 check.

respx replaces httpx's network layer, so every response here is fake. Any
request to a URL that isn't mocked fails the test instead of going online.
"""

import asyncio
from pathlib import Path

import httpx
import pytest
import respx

from vpnleakcheck.checks.public_ip import check_ipv4
from vpnleakcheck.endpoints import IPV4_ENDPOINTS, Endpoint
from vpnleakcheck.result import CheckResult, Status

FIXTURES = Path(__file__).parent / "fixtures"
IPIFY, IDENT_ME = IPV4_ENDPOINTS


def fixture(name: str) -> str:
    return (FIXTURES / name).read_text()


def run_check(endpoints: tuple[Endpoint, ...] = IPV4_ENDPOINTS) -> CheckResult:
    """Run the async check from a normal (sync) test function."""

    async def go() -> CheckResult:
        async with httpx.AsyncClient() as client:
            return await check_ipv4(client, endpoints)

    return asyncio.run(go())


@respx.mock
def test_both_services_agree() -> None:
    # The ident.me fixture ends in a newline; the check must strip it.
    respx.get(IPIFY.url).respond(text=fixture("ipv4_ipify.txt"))
    respx.get(IDENT_ME.url).respond(text=fixture("ipv4_identme.txt"))

    result = run_check()

    assert result.name == "ipv4"
    assert result.status is Status.OK
    assert result.value == "203.0.113.24"
    assert result.reason == "Confirmed by ipify, ident.me"


@respx.mock
def test_services_disagree_gives_a_warning() -> None:
    respx.get(IPIFY.url).respond(text="203.0.113.24")
    respx.get(IDENT_ME.url).respond(text="198.51.100.7")

    result = run_check()

    assert result.status is Status.WARNING
    # No majority with two services, so the first one listed wins.
    assert result.value == "203.0.113.24"
    assert "ipify saw 203.0.113.24" in result.reason
    assert "ident.me saw 198.51.100.7" in result.reason


@respx.mock
def test_majority_wins_when_services_disagree() -> None:
    third = Endpoint(name="third", url="https://third.example.com")
    respx.get(IPIFY.url).respond(text="198.51.100.7")
    respx.get(IDENT_ME.url).respond(text="203.0.113.24")
    respx.get(third.url).respond(text="203.0.113.24")

    result = run_check((IPIFY, IDENT_ME, third))

    assert result.status is Status.WARNING
    assert result.value == "203.0.113.24"


@pytest.mark.parametrize(
    "failure",
    [
        httpx.ConnectTimeout("timed out"),
        httpx.ConnectError("no route to host"),
        httpx.Response(503, text="Service Unavailable"),
    ],
    ids=["timeout", "connect-error", "http-503"],
)
@respx.mock
def test_one_service_fails(failure: Exception | httpx.Response) -> None:
    respx.get(IPIFY.url).respond(text="203.0.113.24")
    if isinstance(failure, httpx.Response):
        respx.get(IDENT_ME.url).mock(return_value=failure)
    else:
        respx.get(IDENT_ME.url).mock(side_effect=failure)

    result = run_check()

    assert result.status is Status.OK
    assert result.value == "203.0.113.24"
    assert result.reason == "Confirmed by ipify; no answer from ident.me"


@pytest.mark.parametrize(
    "body",
    ["<html><title>Hotel Wi-Fi login</title></html>", "", "2001:db8::1", "999.1.1.1"],
    ids=["login-page", "empty", "ipv6-address", "out-of-range"],
)
@respx.mock
def test_body_that_is_not_an_ipv4_address_counts_as_no_answer(body: str) -> None:
    respx.get(IPIFY.url).respond(text=body)
    respx.get(IDENT_ME.url).respond(text="203.0.113.24")

    result = run_check()

    assert result.status is Status.OK
    assert result.value == "203.0.113.24"
    assert "no answer from ipify" in result.reason


@respx.mock
def test_all_services_fail_is_unavailable_not_a_crash() -> None:
    respx.get(IPIFY.url).mock(side_effect=httpx.ConnectError("offline"))
    respx.get(IDENT_ME.url).mock(side_effect=httpx.ReadTimeout("timed out"))

    result = run_check()

    assert result.status is Status.UNAVAILABLE
    assert result.value is None
    assert "No IPv4 service answered" in result.reason
