"""Tests for the endpoint config.

These check the rules every endpoint must follow. They read the config only
and never contact the services.
"""

from dataclasses import FrozenInstanceError
from urllib.parse import urlsplit

import pytest

from vpnleakcheck.endpoints import IPV4_ENDPOINTS, IPV6_ENDPOINTS, Endpoint

# Every list of services, so each rule below is checked against all of them.
ENDPOINT_LISTS = {"ipv4": IPV4_ENDPOINTS, "ipv6": IPV6_ENDPOINTS}
ALL_ENDPOINTS = [e for endpoints in ENDPOINT_LISTS.values() for e in endpoints]


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
    hosts = [urlsplit(endpoint.url).hostname for endpoint in ALL_ENDPOINTS]

    assert len(hosts) == len(set(hosts))


@pytest.mark.parametrize("endpoint", ALL_ENDPOINTS, ids=lambda e: e.url)
def test_endpoint_uses_https(endpoint: Endpoint) -> None:
    # Plain HTTP would let anyone on the Wi-Fi read or change the answer.
    parts = urlsplit(endpoint.url)

    assert parts.scheme == "https"
    assert parts.hostname
