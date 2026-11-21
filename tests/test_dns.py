"""Tests for the DNS resolver check.

A fake resolver stands in for dnspython's: it either returns DNS records or
raises the error a real lookup would. Nothing goes online.
"""

import asyncio
from pathlib import Path

import dns.asyncresolver
import dns.resolver
import dns.rrset
import pytest

from vpnleakcheck.checks.dns import check_dns, make_system_resolver
from vpnleakcheck.endpoints import DNS_WHOAMI_NAME
from vpnleakcheck.result import CheckResult, Status

FIXTURES = Path(__file__).parent / "fixtures"


def rrset(*addresses: str) -> dns.rrset.RRset:
    """A set of A records for the who's-asking name, as a real answer holds."""
    return dns.rrset.from_text(DNS_WHOAMI_NAME + ".", 15, "IN", "A", *addresses)


def fixture_answer() -> dns.rrset.RRset:
    """The fixture is one answer line as dig prints it: name, TTL, class, type, IP."""
    line = (FIXTURES / "dns_whoami_akamai.txt").read_text()
    name, ttl, rdclass, rdtype, address = line.split()
    return dns.rrset.from_text(name, int(ttl), rdclass, rdtype, address)


class FakeResolver:
    """Answers every lookup with `answer`, or raises it if it is an exception."""

    def __init__(self, answer: object) -> None:
        self.answer = answer
        self.asked: list[tuple[str, str]] = []

    async def resolve(self, qname: str, rdtype: str) -> object:
        self.asked.append((qname, rdtype))
        if isinstance(self.answer, BaseException):
            raise self.answer
        return self.answer


def run_check(resolver: FakeResolver) -> CheckResult:
    return asyncio.run(check_dns(resolver))


def test_resolver_found() -> None:
    resolver = FakeResolver(fixture_answer())

    result = run_check(resolver)

    assert result.name == "dns"
    assert result.status == Status.OK
    assert result.value == "8.8.8.8"
    # Owner and class are added later, by the ownership lookup.
    assert result.owner is None
    assert result.classification is None


def test_asks_for_the_whoami_a_record() -> None:
    resolver = FakeResolver(rrset("8.8.8.8"))

    run_check(resolver)

    # A only: Akamai answers AAAA with NXDOMAIN.
    assert resolver.asked == [("whoami.akamai.net", "A")]


def test_several_records_first_wins() -> None:
    result = run_check(FakeResolver(rrset("8.8.8.8", "9.9.9.9")))

    assert result.status == Status.OK
    assert result.value == "8.8.8.8"


@pytest.mark.parametrize(
    "address",
    ["10.0.0.1", "192.168.1.1", "172.16.0.53", "100.64.0.1", "127.0.0.1", "0.0.0.0"],
)
def test_private_answer_means_dns_is_intercepted(address: str) -> None:
    # Akamai can only ever see a public address, so a private one was made up
    # by the network (captive portal, DNS filter, ...).
    result = run_check(FakeResolver(rrset(address)))

    assert result.status == Status.WARNING
    assert result.value == address
    assert "intercepting DNS" in result.reason


@pytest.mark.parametrize(
    ("error", "words"),
    [
        (dns.resolver.NXDOMAIN(), "doesn't exist"),
        (dns.resolver.NoAnswer(), "no address"),
        (dns.resolver.LifetimeTimeout(timeout=5.0, errors=[]), "in time"),
        (dns.resolver.NoNameservers(), "No DNS server"),
        (dns.resolver.NoRootSOA(), "failed"),  # any other dnspython error
        (OSError("Network is unreachable"), "failed"),
    ],
    ids=["nxdomain", "no-answer", "timeout", "no-nameservers", "other", "oserror"],
)
def test_failed_lookup_is_unavailable(error: Exception, words: str) -> None:
    result = run_check(FakeResolver(error))

    assert result.status == Status.UNAVAILABLE
    assert result.value is None
    assert words in result.reason


@pytest.mark.parametrize(
    "answer", [[], ["not an address object"]], ids=["empty", "junk"]
)
def test_unusable_answer_is_unavailable(answer: list[object]) -> None:
    assert run_check(FakeResolver(answer)).status == Status.UNAVAILABLE


def test_system_resolver_uses_timeout() -> None:
    # Reads the local DNS config file only; sends no query.
    assert make_system_resolver(timeout=2.5).lifetime == 2.5


def test_no_system_dns_config_gives_empty_resolver(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real = dns.asyncresolver.Resolver

    def no_config(configure: bool = True) -> object:
        if configure:
            raise dns.resolver.NoResolverConfiguration
        return real(configure=False)

    monkeypatch.setattr(dns.asyncresolver, "Resolver", no_config)

    resolver = make_system_resolver(timeout=1.0)

    # No servers to ask, so a real lookup fails fast with NoNameservers,
    # which the check turns into `unavailable` instead of a crash.
    assert resolver.nameservers == []
    result = asyncio.run(check_dns(resolver))
    assert result.status == Status.UNAVAILABLE
    assert "No DNS server" in result.reason
