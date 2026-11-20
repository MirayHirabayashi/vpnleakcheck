"""IP ownership: whose network does an address belong to, and where is it used?

This is a helper, not a check of its own. The IPv4, IPv6 and DNS checks find
an address; `lookup_owner` then says who owns it, `classify` says what kind of
network that is ("vpn/hosting", "isp/residential", ...), and a later step puts
both on their results.

The data comes from RIPEstat in two requests sent at the same time: one for
the ASN and holder of the routed block, one for the country.
"""

import asyncio
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from functools import cache
from importlib.resources import files
from importlib.resources.abc import Traversable
from ipaddress import ip_address
from pathlib import Path
from typing import Any

import httpx

from vpnleakcheck.endpoints import (
    OWNERSHIP_ASN_ENDPOINT,
    OWNERSHIP_COUNTRY_ENDPOINT,
    RIPESTAT_SOURCEAPP,
    Endpoint,
)
from vpnleakcheck.result import Classification, Owner

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


# ------------------------------------------------------- classification ----

# When an owner's name matches keywords of several classes, the first class
# listed here wins. Calling an ISP "hosting" would hide a leak, while calling a
# VPN server an ISP only causes a false alarm, so the cautious classes come
# first. This order is a safety rule, so it lives in code, not in the data file.
# public-dns is not here: it is assigned by exact ASN only.
KEYWORD_PRECEDENCE = (
    Classification.MOBILE,
    Classification.ISP_RESIDENTIAL,
    Classification.VPN_HOSTING,
)

DEFAULT_PROVIDERS_FILE = files("vpnleakcheck") / "data" / "known_providers.json"


@dataclass(frozen=True)
class Providers:
    """Classification rules loaded from a known_providers.json file."""

    asns: Mapping[int, Classification]
    # One compiled pattern per class, matching any of its keywords as a whole
    # word, ignoring case.
    keywords: Mapping[Classification, re.Pattern[str]]


def _keyword_pattern(words: list[str]) -> re.Pattern[str]:
    # \b is a word boundary, so "mobile" matches "T-MOBILE-AS21928" but
    # "cloud" doesn't match "CLOUDFLARENET".
    alternatives = "|".join(re.escape(word) for word in words)
    return re.compile(rf"\b(?:{alternatives})\b", re.IGNORECASE)


def load_providers(source: Traversable | Path) -> Providers:
    """Read and check a known_providers.json file.

    Raises ValueError with a readable message if the file is broken, so a bad
    edit fails loudly instead of silently classifying everything as unknown.
    """
    raw = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("known_providers.json must be a JSON object")

    asns: dict[int, Classification] = {}
    for entry in raw.get("asns", []):
        asn = entry.get("asn") if isinstance(entry, dict) else None
        if not isinstance(asn, int) or isinstance(asn, bool) or asn <= 0:
            raise ValueError(f"Bad ASN entry: {entry!r}")
        try:
            cls = Classification(entry.get("class"))
        except ValueError:
            raise ValueError(f"AS{asn}: unknown class {entry.get('class')!r}") from None
        if cls is Classification.UNKNOWN:
            raise ValueError(f"AS{asn}: 'unknown' can't be assigned, leave it out")
        if asn in asns:
            raise ValueError(f"AS{asn} is listed more than once")
        asns[asn] = cls

    keywords: dict[Classification, re.Pattern[str]] = {}
    for name, words in raw.get("keywords", {}).items():
        try:
            cls = Classification(name)
        except ValueError:
            raise ValueError(f"Unknown keyword class {name!r}") from None
        if cls not in KEYWORD_PRECEDENCE:
            raise ValueError(f"Class {name!r} can't have keywords")
        if not isinstance(words, list) or not all(
            isinstance(word, str) and word.strip() for word in words
        ):
            raise ValueError(f"Keywords for {name!r} must be non-empty strings")
        if words:
            keywords[cls] = _keyword_pattern([word.strip() for word in words])

    return Providers(asns=asns, keywords=keywords)


@cache
def default_providers() -> Providers:
    """The rules shipped with vpnleakcheck, read once per run."""
    return load_providers(DEFAULT_PROVIDERS_FILE)


def classify(owner: Owner, providers: Providers | None = None) -> Classification:
    """Say what kind of network `owner` is.

    An exact ASN match wins. Otherwise the holder name is searched for
    keywords in KEYWORD_PRECEDENCE order. No match is UNKNOWN: looked up, but
    fits no class. (A failed lookup has no Owner at all, so it never gets here.)
    """
    rules = providers or default_providers()

    if owner.asn is not None and owner.asn in rules.asns:
        return rules.asns[owner.asn]

    if owner.org:
        for cls in KEYWORD_PRECEDENCE:
            pattern = rules.keywords.get(cls)
            if pattern is not None and pattern.search(owner.org):
                return cls

    return Classification.UNKNOWN
