"""Every external service vpnleakcheck talks to, in one place.

Checks import their endpoints from here and never hard-code a URL, so this
file is the complete answer to "who does this tool contact?".

Before adding a service, confirm it is free, needs no API key, and allows
automated use. Record where and when you checked in a comment.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Endpoint:
    """One external service: a short name for reports, and the URL to call."""

    name: str
    url: str


# "What is my IP" services that answer over IPv4 only: their hostnames have an
# A record and no AAAA record, so the request cannot leave over IPv6. Each one
# replies with the caller's address as plain text. Some services of this kind
# add a trailing newline, so always strip the body before using it.
#
# The two are run by different operators on different networks, so a single
# outage cannot take out both.
IPV4_ENDPOINTS: tuple[Endpoint, ...] = (
    # Verified 2026-11-15, https://www.ipify.org: free, no key, "use it
    # without limit". Served through Cloudflare.
    Endpoint(name="ipify", url="https://api.ipify.org"),
    # Verified 2026-11-15, https://api.ident.me: free, no key, "use this
    # service for anything"; email first above 500 requests per second.
    # Hosted at Hetzner and run by one person, so expect occasional downtime.
    Endpoint(name="ident.me", url="https://4.ident.me"),
)

# The IPv6-only siblings of the services above: AAAA record, no A record, so
# the request can only leave over IPv6. If this machine has no IPv6 route to
# the internet, the connection fails, and for this check that is the good
# outcome. Same operators and terms as above.
IPV6_ENDPOINTS: tuple[Endpoint, ...] = (
    # Verified 2026-11-17: AAAA only (2607:f2d8:1:3c::4), no A record.
    Endpoint(name="ipify", url="https://api6.ipify.org"),
    # Verified 2026-11-17: AAAA only (2a01:4f9:c012:8091::1), no A record.
    Endpoint(name="ident.me", url="https://6.ident.me"),
)

# IP ownership: who announces an address on the internet (ASN and holder) and
# where it is used (country). Both come from RIPEstat, run by the RIPE NCC, a
# non-profit registry. Its routing data covers the whole internet, not only
# RIPE's own region (Europe and the Middle East).
#
# Verified 2026-11-19, https://stat.ripe.net/docs/data_api and the terms at
# https://www.ripe.net/about-us/legal/ripestat-service-terms-and-conditions/:
# free, no key, IPv4 and IPv6. No request cap, but register above about 1000
# requests a day and send at most 8 at once from one IP. Clients should name
# themselves with `sourceapp`.
# Terms, Art. 3.3: commercial use (paid services or products) needs written
# permission from stat@ripe.net, and the data may not be redistributed. A free
# tool that looks up the user's own IP live is fine; selling it is not.
#
# Neither URL carries a query string. The check adds `resource=<ip>` and
# `sourceapp=RIPESTAT_SOURCEAPP` as request parameters.
RIPESTAT_SOURCEAPP = "vpnleakcheck"

# ASN and holder (organisation) of the routed block containing the address.
OWNERSHIP_ASN_ENDPOINT = Endpoint(
    name="ripestat",
    url="https://stat.ripe.net/data/prefix-overview/data.json",
)
# Country where the address is used (MaxMind GeoLite data), not just where
# the block was registered.
OWNERSHIP_COUNTRY_ENDPOINT = Endpoint(
    name="ripestat",
    url="https://stat.ripe.net/data/maxmind-geo-lite/data.json",
)

# Captive-portal probe. With no portal it answers an empty 204. A portal
# (hotel or airport login page) intercepts the request and answers with a
# redirect, a 511, or its own page instead.
#
# Plain HTTP on purpose, the only endpoint here that is: a portal can rewrite
# an HTTP request and show itself, but it can only break an HTTPS one, which
# tells us nothing. The request carries no data, so there is nothing to read.
#
# Verified 2026-11-19: Firefox's current `captivedetect.canonicalURL`, per
# https://firefox-source-docs.mozilla.org/networking/captive_portals.html.
# Domain registered to Mozilla Corporation, served by Fastly, A and AAAA
# records. No key; no published terms for other clients, but it is openly
# documented and every Firefox install calls it. The older
# detectportal.firefox.com/success.txt still answers but is no longer the
# documented default, so it isn't used.
CAPTIVE_PORTAL_ENDPOINT = Endpoint(
    name="firefox", url="http://firefox-portal-detection.com/generate_204"
)
