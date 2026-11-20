"""Tests for classifying IP owners with known_providers.json.

Pure logic, no network. Owners with made-up names use ASNs from the
documentation range 64496-64511, which no real network uses.
"""

import json
from pathlib import Path

import pytest

from vpnleakcheck.checks.ownership import (
    DEFAULT_PROVIDERS_FILE,
    classify,
    default_providers,
    load_providers,
)
from vpnleakcheck.result import Classification, Owner

DOC_ASN = 64500
SHIPPED = json.loads(DEFAULT_PROVIDERS_FILE.read_text(encoding="utf-8"))


# ------------------------------------------------------ shipped rules ------


def test_shipped_file_is_inside_the_package() -> None:
    # Read through importlib.resources, so this also works after pipx install.
    assert DEFAULT_PROVIDERS_FILE.is_file()


def test_shipped_file_loads() -> None:
    rules = default_providers()

    assert rules.asns
    assert set(rules.keywords) == {
        Classification.MOBILE,
        Classification.ISP_RESIDENTIAL,
        Classification.VPN_HOSTING,
    }


@pytest.mark.parametrize(
    "entry", SHIPPED["asns"], ids=lambda e: f"AS{e['asn']}-{e['class']}"
)
def test_every_listed_asn_gets_its_class(entry: dict) -> None:
    # The real RIPEstat holder name goes in too, so a keyword can never
    # override a listed ASN.
    owner = Owner(org=entry["name"], asn=entry["asn"])

    assert classify(owner) == Classification(entry["class"])


# ----------------------------------------------------------- keywords ------


@pytest.mark.parametrize(
    ("org", "expected"),
    [
        # One class matches.
        ("EXAMPLE-AS Example Hosting GmbH", Classification.VPN_HOSTING),
        ("Example Data Center LLC", Classification.VPN_HOSTING),
        ("EXAMPLE-VPS - Example Servers Ltd", Classification.VPN_HOSTING),
        ("Example Broadband Ltd", Classification.ISP_RESIDENTIAL),
        ("EXAMPLE-NET Example Telekom AG", Classification.ISP_RESIDENTIAL),
        ("EXAMPLE - Example Cable Communications, LLC", Classification.ISP_RESIDENTIAL),
        ("EXAMPLE-MOBILE-AS64500 - Example Mobile", Classification.MOBILE),
        ("EXAMPLE-MOBILITY - Example Enterprises", Classification.MOBILE),
        # Several classes match: the cautious one wins.
        ("Example Telecom Cloud Services", Classification.ISP_RESIDENTIAL),
        ("Example Wireless Broadband", Classification.MOBILE),
        ("Example Mobile Hosting", Classification.MOBILE),
        # Whole words only.
        ("CLOUDYNET Example Corp", Classification.UNKNOWN),
        ("EXAMPLE Observers Inc", Classification.UNKNOWN),
        ("Example Cablevision", Classification.UNKNOWN),
        # Nothing matches.
        ("ACME Acme Corporation", Classification.UNKNOWN),
        # public-dns is ASN-only, never from a name.
        ("EXAMPLE Public DNS", Classification.UNKNOWN),
    ],
)
def test_keyword_classification(org: str, expected: Classification) -> None:
    assert classify(Owner(org=org, asn=DOC_ASN)) == expected


def test_keywords_ignore_case() -> None:
    assert classify(Owner(org="example hosting")) == Classification.VPN_HOSTING
    assert classify(Owner(org="EXAMPLE HOSTING")) == Classification.VPN_HOSTING


def test_listed_asn_beats_keywords() -> None:
    # AS7922 is listed as an ISP; a hosting word in the name must not win.
    owner = Owner(org="Example Hosting", asn=7922)

    assert classify(owner) == Classification.ISP_RESIDENTIAL


def test_public_dns_by_asn() -> None:
    owner = Owner(org="GOOGLE - Google LLC", asn=15169, country="US")

    assert classify(owner) == Classification.PUBLIC_DNS


@pytest.mark.parametrize(
    "owner",
    [Owner(), Owner(country="NL"), Owner(asn=DOC_ASN), Owner(org="")],
    ids=["empty", "country-only", "unlisted-asn-only", "empty-org"],
)
def test_too_little_to_go_on_is_unknown(owner: Owner) -> None:
    assert classify(owner) == Classification.UNKNOWN


# ----------------------------------------------------- custom rules --------


def write_rules(tmp_path: Path, rules: object) -> Path:
    path = tmp_path / "known_providers.json"
    path.write_text(json.dumps(rules), encoding="utf-8")
    return path


def test_custom_rules_file(tmp_path: Path) -> None:
    rules = load_providers(
        write_rules(
            tmp_path,
            {
                "asns": [{"asn": DOC_ASN, "class": "mobile", "name": "x"}],
                "keywords": {"vpn/hosting": ["  gateway  "]},
            },
        )
    )

    assert classify(Owner(asn=DOC_ASN), rules) == Classification.MOBILE
    # Keywords are stripped of surrounding spaces.
    assert classify(Owner(org="Example Gateway"), rules) == Classification.VPN_HOSTING
    assert classify(Owner(org="Example Hosting"), rules) == Classification.UNKNOWN


@pytest.mark.parametrize(
    ("rules", "message"),
    [
        (["not", "an", "object"], "must be a JSON object"),
        ({"asns": [{"asn": "9009", "class": "vpn/hosting"}]}, "Bad ASN"),
        ({"asns": [{"asn": True, "class": "vpn/hosting"}]}, "Bad ASN"),
        ({"asns": [{"asn": 0, "class": "vpn/hosting"}]}, "Bad ASN"),
        ({"asns": ["AS9009"]}, "Bad ASN"),
        ({"asns": [{"asn": 9009, "class": "vpn"}]}, "unknown class"),
        ({"asns": [{"asn": 9009, "class": "unknown"}]}, "can't be assigned"),
        (
            {
                "asns": [
                    {"asn": 9009, "class": "vpn/hosting"},
                    {"asn": 9009, "class": "mobile"},
                ]
            },
            "more than once",
        ),
        ({"keywords": {"hosting": ["x"]}}, "Unknown keyword class"),
        ({"keywords": {"public-dns": ["dns"]}}, "can't have keywords"),
        ({"keywords": {"unknown": ["x"]}}, "can't have keywords"),
        ({"keywords": {"mobile": "mobile"}}, "non-empty strings"),
        ({"keywords": {"mobile": ["mobile", " "]}}, "non-empty strings"),
        ({"keywords": {"mobile": [3]}}, "non-empty strings"),
    ],
)
def test_broken_rules_file_fails_loudly(
    tmp_path: Path, rules: object, message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        load_providers(write_rules(tmp_path, rules))


def test_invalid_json_fails_loudly(tmp_path: Path) -> None:
    path = tmp_path / "known_providers.json"
    path.write_text('{"asns": [', encoding="utf-8")

    # json's decode error is a ValueError too.
    with pytest.raises(ValueError):
        load_providers(path)
