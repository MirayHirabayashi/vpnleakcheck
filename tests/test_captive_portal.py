"""Tests for the captive-portal check.

Each test fakes what the probe URL returns: the real probe's empty 204, or one
of the ways a portal intercepts it. respx fakes every response; nothing goes
online.
"""

import asyncio
from pathlib import Path

import httpx
import pytest
import respx

from vpnleakcheck.checks.captive_portal import check_captive_portal
from vpnleakcheck.endpoints import CAPTIVE_PORTAL_ENDPOINT
from vpnleakcheck.result import CheckResult, Status

FIXTURES = Path(__file__).parent / "fixtures"
PROBE_URL = CAPTIVE_PORTAL_ENDPOINT.url
LOGIN_PAGE = "http://192.168.1.1/login?redirect=generate_204"


def run_check(follow_redirects: bool = False) -> CheckResult:
    """Run the async check from a normal (sync) test function."""

    async def go() -> CheckResult:
        async with httpx.AsyncClient(follow_redirects=follow_redirects) as client:
            return await check_captive_portal(client)

    return asyncio.run(go())


@respx.mock
def test_no_portal() -> None:
    respx.get(PROBE_URL).respond(204)

    result = run_check()

    assert result.name == "captive_portal"
    assert result.status == Status.OK
    assert result.value is None


@respx.mock
def test_empty_200_also_means_no_portal() -> None:
    # Firefox's rule: an empty 200 passes too.
    respx.get(PROBE_URL).respond(200)

    assert run_check().status == Status.OK


@pytest.mark.parametrize("code", [301, 302, 303, 307, 308])
@respx.mock
def test_redirect_to_login_page(code: int) -> None:
    respx.get(PROBE_URL).respond(code, headers={"Location": LOGIN_PAGE})

    result = run_check()

    assert result.status == Status.WARNING
    assert result.value == LOGIN_PAGE
    assert "Log in to this Wi-Fi first" in result.reason


@respx.mock
def test_redirect_is_seen_even_if_the_client_follows_redirects() -> None:
    # If the check followed the redirect, it would land on the login page
    # (a 200 with a body) and lose the login URL. It must stop at the 302.
    respx.get(PROBE_URL).respond(302, headers={"Location": LOGIN_PAGE})
    respx.get(LOGIN_PAGE).respond(200, text="<html>login</html>")

    result = run_check(follow_redirects=True)

    assert result.status == Status.WARNING
    assert result.value == LOGIN_PAGE


@respx.mock
def test_login_page_served_in_place_of_the_probe() -> None:
    # Some portals don't redirect: they answer every URL with their own page.
    login_html = (FIXTURES / "captive_portal_login.html").read_text()
    respx.get(PROBE_URL).respond(200, html=login_html)

    result = run_check()

    assert result.status == Status.WARNING
    assert result.value is None  # no redirect, so no login URL to report
    assert "Log in to this Wi-Fi first" in result.reason


@respx.mock
def test_network_authentication_required() -> None:
    respx.get(PROBE_URL).respond(511)

    assert run_check().status == Status.WARNING


@pytest.mark.parametrize(
    "error",
    [
        httpx.ConnectError("Network is unreachable"),
        httpx.ConnectTimeout("timed out"),
        httpx.ReadTimeout("timed out"),
    ],
    ids=["connect_error", "connect_timeout", "read_timeout"],
)
@respx.mock
def test_probe_unreachable(error: Exception) -> None:
    # Offline, or a network that drops everything: we can't tell, so we don't
    # claim a portal.
    respx.get(PROBE_URL).mock(side_effect=error)

    result = run_check()

    assert result.status == Status.UNAVAILABLE
    assert "firefox" in result.reason


@pytest.mark.parametrize("code", [403, 404, 500, 503])
@respx.mock
def test_probe_error_status_is_not_proof_of_a_portal(code: int) -> None:
    respx.get(PROBE_URL).respond(code)

    result = run_check()

    assert result.status == Status.UNAVAILABLE
    assert str(code) in result.reason
