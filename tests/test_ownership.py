"""Tests for the IP ownership lookup.

Every RIPEstat response here is fake (respx), built from real responses saved
in tests/fixtures/ripestat_*.json on 2026-11-19.
"""

import asyncio
import json
from pathlib import Path
from typing import Any

import httpx
import pytest
import respx

from vpnleakcheck.checks.ownership import lookup_owner
from vpnleakcheck.endpoints import (
    OWNERSHIP_ASN_ENDPOINT,
    OWNERSHIP_COUNTRY_ENDPOINT,
    RIPESTAT_SOURCEAPP,
)
from vpnleakcheck.result import Owner

FIXTURES = Path(__file__).parent / "fixtures"
ASN_URL = OWNERSHIP_ASN_ENDPOINT.url
COUNTRY_URL = OWNERSHIP_COUNTRY_ENDPOINT.url

# Real global addresses matching the fixtures (Google Public DNS). The
# documentation ranges (203.0.113.0/24, 2001:db8::/32) can't be used: the
# lookup refuses non-global addresses before sending anything.
IPV4 = "8.8.8.8"
IPV6 = "2001:4860:4860::8888"
GOOGLE = Owner(org="GOOGLE - Google LLC", asn=15169, country="US")


def fixture(name: str) -> dict[str, Any]:
    return json.loads((FIXTURES / name).read_text())


def with_data(name: str, **changes: Any) -> dict[str, Any]:
    """A fixture with some keys of its `data` object replaced."""
    body = fixture(name)
    body["data"].update(changes)
    return body


def run_lookup(ip: str) -> Owner | None:
    """Run the async lookup from a normal (sync) test function."""

    async def go() -> Owner | None:
        async with httpx.AsyncClient() as client:
            return await lookup_owner(client, ip)

    return asyncio.run(go())


# ------------------------------------------------------------ success ------


@respx.mock
def test_ipv4_owner() -> None:
    respx.get(ASN_URL).respond(json=fixture("ripestat_prefix_overview_ipv4.json"))
    respx.get(COUNTRY_URL).respond(json=fixture("ripestat_geo_ipv4.json"))

    assert run_lookup(IPV4) == GOOGLE


@respx.mock
def test_ipv6_owner() -> None:
    respx.get(ASN_URL).respond(json=fixture("ripestat_prefix_overview_ipv6.json"))
    respx.get(COUNTRY_URL).respond(json=fixture("ripestat_geo_ipv6.json"))

    assert run_lookup(IPV6) == GOOGLE


@respx.mock
def test_sends_resource_and_sourceapp() -> None:
    asn_route = respx.get(ASN_URL).respond(
        json=fixture("ripestat_prefix_overview_ipv4.json")
    )
    country_route = respx.get(COUNTRY_URL).respond(
        json=fixture("ripestat_geo_ipv4.json")
    )

    run_lookup(IPV4)

    for route in (asn_route, country_route):
        params = route.calls.last.request.url.params
        assert params["resource"] == IPV4
        assert params["sourceapp"] == RIPESTAT_SOURCEAPP


@respx.mock
def test_first_asn_wins_when_several_announce() -> None:
    respx.get(ASN_URL).respond(
        json=with_data(
            "ripestat_prefix_overview_ipv4.json",
            asns=[
                {"asn": 15169, "holder": "GOOGLE - Google LLC"},
                {"asn": 64500, "holder": "OTHER - Other Network"},
            ],
        )
    )
    respx.get(COUNTRY_URL).respond(json=fixture("ripestat_geo_ipv4.json"))

    assert run_lookup(IPV4) == GOOGLE


@respx.mock
def test_holder_is_kept_raw() -> None:
    # RIPE-registered holders have no " - "; the string is stored unchanged.
    respx.get(ASN_URL).respond(
        json=with_data(
            "ripestat_prefix_overview_ipv4.json",
            asns=[{"asn": 24940, "holder": "HETZNER-AS Hetzner Online GmbH"}],
        )
    )
    respx.get(COUNTRY_URL).respond(json=fixture("ripestat_geo_ipv4.json"))

    owner = run_lookup(IPV4)

    assert owner is not None
    assert owner.org == "HETZNER-AS Hetzner Online GmbH"


# ---------------------------------------------------- partial answers ------


@respx.mock
def test_unknown_country_keeps_asn() -> None:
    respx.get(ASN_URL).respond(json=fixture("ripestat_prefix_overview_ipv4.json"))
    respx.get(COUNTRY_URL).respond(json=fixture("ripestat_geo_unknown.json"))

    assert run_lookup(IPV4) == Owner(org="GOOGLE - Google LLC", asn=15169)


@respx.mock
def test_failed_asn_call_keeps_country() -> None:
    respx.get(ASN_URL).mock(side_effect=httpx.ConnectTimeout("timed out"))
    respx.get(COUNTRY_URL).respond(json=fixture("ripestat_geo_ipv4.json"))

    assert run_lookup(IPV4) == Owner(country="US")


@respx.mock
def test_unannounced_and_unknown_gives_none() -> None:
    # Nobody announces the block and its location is unknown: nothing learned.
    respx.get(ASN_URL).respond(
        json=fixture("ripestat_prefix_overview_unannounced.json")
    )
    respx.get(COUNTRY_URL).respond(json=fixture("ripestat_geo_unknown.json"))

    assert run_lookup(IPV4) is None


# ----------------------------------------------------------- failures ------


@pytest.mark.parametrize(
    "response",
    [
        httpx.ConnectError("no route"),
        httpx.ConnectTimeout("timed out"),
        httpx.ReadTimeout("too slow"),
        httpx.Response(500),
        httpx.Response(429, json={"status": "error"}),
        httpx.Response(200, text="<html>Log in to Hotel Wi-Fi</html>"),
        httpx.Response(200, json={"status": "error", "status_code": 400}),
        httpx.Response(200, json=["not", "an", "object"]),
        httpx.Response(200, json={"status": "ok", "data": None}),
    ],
    ids=[
        "connect-error",
        "connect-timeout",
        "read-timeout",
        "500",
        "429",
        "html-body",
        "ripestat-error",
        "json-list",
        "no-data",
    ],
)
@respx.mock
def test_both_calls_failing_gives_none(response: Exception | httpx.Response) -> None:
    for url in (ASN_URL, COUNTRY_URL):
        if isinstance(response, Exception):
            respx.get(url).mock(side_effect=response)
        else:
            respx.get(url).mock(return_value=response)

    assert run_lookup(IPV4) is None


@pytest.mark.parametrize(
    "asns",
    [
        [{"asn": "15169", "holder": ""}],  # ASN as a string, empty holder
        [{"asn": True, "holder": None}],  # bool is an int in Python
        [{"asn": 0, "holder": "   "}],
        ["not-an-object"],
        "not-a-list",
    ],
)
@respx.mock
def test_unexpected_asn_shapes_are_ignored(asns: Any) -> None:
    respx.get(ASN_URL).respond(
        json=with_data("ripestat_prefix_overview_ipv4.json", asns=asns)
    )
    respx.get(COUNTRY_URL).respond(json=fixture("ripestat_geo_ipv4.json"))

    # The bad ASN answer is dropped; the good country answer survives.
    assert run_lookup(IPV4) == Owner(country="US")


# "?" is what RIPEstat really sends for anycast addresses such as 1.1.1.1.
@pytest.mark.parametrize("country", ["?", "", "us", "USA", "??", None, 840])
@respx.mock
def test_unexpected_country_is_ignored(country: Any) -> None:
    geo = fixture("ripestat_geo_ipv4.json")
    geo["data"]["located_resources"][0]["locations"][0]["country"] = country
    respx.get(ASN_URL).respond(json=fixture("ripestat_prefix_overview_ipv4.json"))
    respx.get(COUNTRY_URL).respond(json=geo)

    assert run_lookup(IPV4) == Owner(org="GOOGLE - Google LLC", asn=15169)


# ------------------------------------------------ never sent anywhere ------


@pytest.mark.parametrize(
    "ip",
    [
        "192.168.1.10",  # home router network
        "10.8.0.2",  # common VPN-internal address
        "100.64.0.1",  # carrier-grade NAT
        "127.0.0.1",
        "fe80::1",  # link-local
        "fd00::1",  # unique-local
        "192.0.2.1",  # documentation
        "2001:db8::1",  # documentation
        "not an ip",
        "",
    ],
)
@respx.mock
def test_non_global_address_is_never_sent(ip: str) -> None:
    # No routes are mocked, so any request would fail the test; the call
    # count makes that explicit.
    assert run_lookup(ip) is None
    assert respx.calls.call_count == 0
