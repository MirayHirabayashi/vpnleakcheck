"""IP ownership: whose network does an address belong to, and where is it used?

This is a helper, not a check of its own. The IPv4, IPv6 and DNS checks find
an address; `lookup_owner` then says who owns it, and a later step puts that
`Owner` on their results. Classification ("vpn/hosting", "isp/residential",
...) is decided from the owner in a separate step.

The data comes from RIPEstat in two requests sent at the same time: one for
the ASN and holder of the routed block, one for the country.
"""

import asyncio
import re
from ipaddress import ip_address
from typing import Any

import httpx

from vpnleakcheck.endpoints import (
    OWNERSHIP_ASN_ENDPOINT,
    OWNERSHIP_COUNTRY_ENDPOINT,
    RIPESTAT_SOURCEAPP,
    Endpoint,
)
from vpnleakcheck.result import Owner

_COUNTRY_CODE = re.compile(r"[A-Z]{2}")


async def _ask_ripestat(
    client: httpx.AsyncClient, endpoint: Endpoint, ip: str
) -> dict[str, Any] | None:
    """Call one RIPEstat endpoint and return its `data` object, or None."""
    try:
        response = await client.get(
            endpoint.url, params={"resource": ip, "sourceapp": RIPESTAT_SOURCEAPP}
        )
        response.raise_for_status()
        body = response.json()
    except (httpx.HTTPError, ValueError):
        # HTTPError: timeout, no connection, TLS failure, or a 4xx/5xx status.
        # ValueError: the body isn't JSON (json's error is a ValueError).
        return None

    # A 200 can still carry an error, so RIPEstat's own status must say "ok".
    if not isinstance(body, dict) or body.get("status") != "ok":
        return None
    data = body.get("data")
    return data if isinstance(data, dict) else None


def _parse_asn(data: dict[str, Any]) -> tuple[int | None, str | None]:
    """Read (asn, holder) from a prefix-overview `data` object.

    `asns` is a list. It is empty when nobody announces the block, and in
    rare cases holds several networks; then the first one listed wins.
    The holder is kept exactly as sent (e.g. "HETZNER-AS Hetzner Online GmbH"),
    because its format differs between registries and can't be cleaned
    reliably.
    """
    try:
        first = data["asns"][0]
        asn, holder = first.get("asn"), first.get("holder")
    except (KeyError, IndexError, TypeError, AttributeError):
        return None, None

    # bool is a subclass of int in Python, so rule it out explicitly.
    if not isinstance(asn, int) or isinstance(asn, bool) or asn <= 0:
        asn = None
    if not isinstance(holder, str) or not holder.strip():
        holder = None
    else:
        holder = holder.strip()
    return asn, holder


def _parse_country(data: dict[str, Any]) -> str | None:
    """Read the two-letter country from a maxmind-geo-lite `data` object.

    An unknown location is not an error: it comes as an empty
    `located_resources` list, or as country "?" (seen for anycast addresses
    such as 1.1.1.1, which are served from many countries at once).
    """
    try:
        country = data["located_resources"][0]["locations"][0]["country"]
    except (KeyError, IndexError, TypeError):
        return None
    if isinstance(country, str) and _COUNTRY_CODE.fullmatch(country):
        return country
    return None


async def lookup_owner(client: httpx.AsyncClient, ip: str) -> Owner | None:
    """Find who owns `ip` (ASN and holder) and which country it is used in.

    Partial answers are kept: if only one request succeeds, the fields it
    couldn't fill are None. Returns None if nothing at all was learned.

    Private, loopback, link-local and documentation addresses are never sent:
    they mean nothing on the internet, and sending them would only leak
    details of the local network.
    """
    try:
        address = ip_address(ip)
    except ValueError:
        return None
    if not address.is_global:
        return None

    asn_data, country_data = await asyncio.gather(
        _ask_ripestat(client, OWNERSHIP_ASN_ENDPOINT, str(address)),
        _ask_ripestat(client, OWNERSHIP_COUNTRY_ENDPOINT, str(address)),
    )

    asn, org = _parse_asn(asn_data) if asn_data else (None, None)
    country = _parse_country(country_data) if country_data else None

    if asn is None and org is None and country is None:
        return None
    return Owner(org=org, asn=asn, country=country)
