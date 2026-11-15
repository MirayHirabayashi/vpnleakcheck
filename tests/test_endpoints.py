"""Tests for the endpoint config.

These check the rules every endpoint must follow. They read the config only
and never contact the services.
"""

from dataclasses import FrozenInstanceError
from urllib.parse import urlsplit

import pytest

from vpnleakcheck.endpoints import IPV4_ENDPOINTS, Endpoint


def test_endpoint_is_immutable() -> None:
    endpoint = Endpoint(name="example", url="https://ip.example.com")

    with pytest.raises(FrozenInstanceError):
        endpoint.url = "https://evil.example.com"


def test_at_least_two_ipv4_endpoints() -> None:
    # The spec requires two services so their answers can be compared.
    assert len(IPV4_ENDPOINTS) >= 2


def test_ipv4_endpoint_names_are_unique() -> None:
    names = [endpoint.name for endpoint in IPV4_ENDPOINTS]

    assert len(names) == len(set(names))


def test_ipv4_endpoints_use_different_hosts() -> None:
    # Two entries pointing at one host would not be independent services.
    hosts = [urlsplit(endpoint.url).hostname for endpoint in IPV4_ENDPOINTS]

    assert len(hosts) == len(set(hosts))


@pytest.mark.parametrize("endpoint", IPV4_ENDPOINTS, ids=lambda e: e.name)
def test_ipv4_endpoint_uses_https(endpoint: Endpoint) -> None:
    # Plain HTTP would let anyone on the Wi-Fi read or change the answer.
    parts = urlsplit(endpoint.url)

    assert parts.scheme == "https"
    assert parts.hostname
