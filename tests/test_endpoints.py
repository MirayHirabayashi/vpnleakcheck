"""Tests for the endpoint config.

These check the rules every endpoint must follow. They read the config only
and never contact the services.
"""

import re
from dataclasses import FrozenInstanceError
from urllib.parse import urlsplit

import pytest

from vpnleakcheck.endpoints import (
    CAPTIVE_PORTAL_ENDPOINT,
    DNS_WHOAMI_NAME,
    IPV4_ENDPOINTS,
    IPV6_ENDPOINTS,
    OWNERSHIP_ASN_ENDPOINT,
    OWNERSHIP_COUNTRY_ENDPOINT,
    RIPESTAT_SOURCEAPP,
    Endpoint,
)

# Every list of services, so each rule below is checked against all of them.
ENDPOINT_LISTS = {"ipv4": IPV4_ENDPOINTS, "ipv6": IPV6_ENDPOINTS}
ALL_ENDPOINTS = [e for endpoints in ENDPOINT_LISTS.values() for e in endpoints]
# Both ownership lookups are calls to one service (RIPEstat), so they share a
# host on purpose and are kept out of the "different hosts" rule.
OWNERSHIP_ENDPOINTS = [OWNERSHIP_ASN_ENDPOINT, OWNERSHIP_COUNTRY_ENDPOINT]


def test_endpoint_is_immutable() -> None:
    endpoint = Endpoint(name="example", url="https://ip.example.com")

    with pytest.raises(FrozenInstanceError):
        endpoint.url = "https://evil.example.com"


@pytest.mark.parametrize("endpoints", ENDPOINT_LISTS.values(), ids=ENDPOINT_LISTS)
def test_at_least_two_endpoints(endpoints: tuple[Endpoint, ...]) -> None:
    # Two services so their answers can be compared. For IPv6 it also stops
    # one service's outage from looking like "no IPv6 route".
    assert len(endpoints) >= 2


@pytest.mark.parametrize("endpoints", ENDPOINT_LISTS.values(), ids=ENDPOINT_LISTS)
def test_endpoint_names_are_unique(endpoints: tuple[Endpoint, ...]) -> None:
    names = [endpoint.name for endpoint in endpoints]

    assert len(names) == len(set(names))


def test_endpoints_use_different_hosts() -> None:
    # Two entries pointing at one host would not be independent services, and
    # an IPv4 and an IPv6 entry must never share a host (one host can't be
    # both IPv4-only and IPv6-only).
    # The portal probe is included: it must not share a host with an IP service.
    every = [*ALL_ENDPOINTS, CAPTIVE_PORTAL_ENDPOINT]
    hosts = [urlsplit(endpoint.url).hostname for endpoint in every]

    assert len(hosts) == len(set(hosts))


@pytest.mark.parametrize(
    "endpoint", [*ALL_ENDPOINTS, *OWNERSHIP_ENDPOINTS], ids=lambda e: e.url
)
def test_endpoint_uses_https(endpoint: Endpoint) -> None:
    # Plain HTTP would let anyone on the Wi-Fi read or change the answer.
    parts = urlsplit(endpoint.url)

    assert parts.scheme == "https"
    assert parts.hostname


def test_captive_portal_probe_uses_plain_http() -> None:
    # The one exception to the HTTPS rule: a portal can only show itself by
    # rewriting a request it can read. Over HTTPS the probe would just fail.
    parts = urlsplit(CAPTIVE_PORTAL_ENDPOINT.url)

    assert parts.scheme == "http"
    assert parts.hostname


def test_ownership_service_is_not_an_ip_service() -> None:
    # The ownership service must be run apart from the "what is my IP"
    # services, so one operator never both reports our IP and judges it.
    ip_hosts = {urlsplit(e.url).hostname for e in ALL_ENDPOINTS}
    ip_hosts.add(urlsplit(CAPTIVE_PORTAL_ENDPOINT.url).hostname)

    for endpoint in OWNERSHIP_ENDPOINTS:
        assert urlsplit(endpoint.url).hostname not in ip_hosts


@pytest.mark.parametrize("endpoint", OWNERSHIP_ENDPOINTS, ids=lambda e: e.url)
def test_ownership_url_has_no_query(endpoint: Endpoint) -> None:
    # The check adds `resource` and `sourceapp` itself; a query baked into
    # the URL could clash with them.
    assert urlsplit(endpoint.url).query == ""


def test_ripestat_sourceapp_format() -> None:
    # RIPEstat's rule: letters, digits, hyphens and underscores, no spaces.
    assert re.fullmatch(r"[A-Za-z0-9_-]+", RIPESTAT_SOURCEAPP)


def test_dns_whoami_name_is_a_bare_hostname() -> None:
    # A DNS name, not a URL: no scheme, no path, no trailing dot.
    assert re.fullmatch(r"[a-z0-9-]+(\.[a-z0-9-]+)+", DNS_WHOAMI_NAME)
