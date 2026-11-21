"""DNS resolver check: which server is really answering our DNS lookups?

We look up a "who's asking" name (see endpoints.py). Its authoritative server
replies with the address of whoever asked it: the recursive resolver that does
our lookups. If that resolver belongs to the hotel or the ISP instead of the
VPN, every site we visit is visible to them, even though the traffic itself is
encrypted. That is a DNS leak.

This check only finds the resolver's address. Who owns it, and whether that
is a leak, is decided later by the ownership lookup and the verdict, the same
as for the public IPs.

Platform note: dnspython reads its server list from /etc/resolv.conf and sends
plain DNS straight to it.
- macOS: /etc/resolv.conf is a summary of the main resolver in `scutil --dns`,
  which is usually what apps use. If a system-wide encrypted DNS profile is
  installed (e.g. the NextDNS or 1.1.1.1 apps), apps use that instead and this
  check sees the plain resolver: a false alarm, never a hidden leak.
- Linux with systemd-resolved: the file points at the local stub 127.0.0.53,
  which forwards the query, so the answer still shows the real resolver.
"""

from ipaddress import IPv4Address
from typing import Any, Protocol

import dns.asyncresolver
import dns.exception
import dns.resolver

from vpnleakcheck.endpoints import DNS_WHOAMI_NAME
from vpnleakcheck.result import CheckResult, Status

DNS_CHECK = "dns"


class AsyncResolver(Protocol):
    """What the check needs from a resolver. Tests pass a fake with this method."""

    async def resolve(self, qname: str, rdtype: str) -> Any: ...


def make_system_resolver(timeout: float) -> dns.asyncresolver.Resolver:
    """A resolver that uses this machine's DNS settings and gives up after `timeout`.

    If the system has no DNS configuration at all, this returns a resolver with
    no servers instead of raising, so the check reports `unavailable` rather
    than the tool crashing.
    """
    try:
        resolver = dns.asyncresolver.Resolver()
    except dns.resolver.NoResolverConfiguration:
        resolver = dns.asyncresolver.Resolver(configure=False)
    # `lifetime` is the total time for one lookup, across every server and retry.
    resolver.lifetime = timeout
    return resolver


async def check_dns(
    resolver: AsyncResolver, name: str = DNS_WHOAMI_NAME
) -> CheckResult:
    """Find the address of the resolver answering our DNS lookups.

    `ok`: found it; `value` is the resolver's public IPv4.
    `warning`: the answer was a private or made-up address, so the network is
    tampering with DNS (often a captive portal or a DNS filter).
    `unavailable`: the lookup failed, so we can't tell.

    The caller owns `resolver` (like the HTTP checks' client), so one timeout
    setting covers the whole run.
    """
    try:
        answer = await resolver.resolve(name, "A")
        # Akamai answers with one A record; if there were more, the first is
        # as good as any.
        address = IPv4Address(next(iter(answer)).address)
    except dns.resolver.NXDOMAIN:
        return _unavailable(
            f"The resolver says {name} doesn't exist; it may be filtering this lookup"
        )
    except dns.resolver.NoAnswer:
        return _unavailable(f"The resolver gave no address for {name}")
    except dns.resolver.LifetimeTimeout:
        return _unavailable(
            f"No DNS answer for {name} in time (offline, or DNS is blocked)"
        )
    except dns.resolver.NoNameservers:
        return _unavailable(
            "No DNS server answered (none configured, or all of them failed)"
        )
    except (
        dns.exception.DNSException,
        OSError,
        StopIteration,
        AttributeError,
        ValueError,
    ):
        # Anything else: another dnspython error, a socket error, an empty
        # answer (StopIteration), a record with no address (AttributeError),
        # or an address that isn't IPv4 (ValueError).
        return _unavailable(f"The DNS lookup for {name} failed")

    if not address.is_global:
        # The real server can only see a public address, so a private one
        # (10.x, 192.168.x, 100.64.x, 0.0.0.0, ...) was made up on the way.
        return CheckResult(
            name=DNS_CHECK,
            status=Status.WARNING,
            value=str(address),
            reason=(
                f"The network answered {name} with a private address "
                f"({address}), so it is intercepting DNS (often a captive "
                "portal or a DNS filter)"
            ),
        )

    return CheckResult(
        name=DNS_CHECK,
        status=Status.OK,
        value=str(address),
        reason=f"DNS lookups are answered by the resolver at {address}",
    )


def _unavailable(reason: str) -> CheckResult:
    return CheckResult(name=DNS_CHECK, status=Status.UNAVAILABLE, reason=reason)
