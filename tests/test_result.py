"""Tests for the shared result object."""

import json
from dataclasses import FrozenInstanceError, asdict

import pytest

from vpnleakcheck.result import CheckResult, Classification, Owner, Status


def test_only_name_and_status_are_required() -> None:
    result = CheckResult(name="ipv6", status=Status.OK)

    assert result.value is None
    assert result.owner is None
    assert result.classification is None
    assert result.reason == ""


def test_result_holds_all_six_fields() -> None:
    owner = Owner(org="Example VPN", asn=64496, country="NL")

    result = CheckResult(
        name="ipv4",
        status=Status.OK,
        value="203.0.113.24",
        owner=owner,
        classification=Classification.VPN_HOSTING,
        reason="Address belongs to a hosting provider",
    )

    assert result.name == "ipv4"
    assert result.value == "203.0.113.24"
    assert result.owner.asn == 64496
    assert result.classification is Classification.VPN_HOSTING


def test_result_cannot_be_changed_after_creation() -> None:
    result = CheckResult(name="ipv4", status=Status.OK)

    with pytest.raises(FrozenInstanceError):
        result.status = Status.LEAK  # type: ignore[misc]


def test_results_with_the_same_fields_are_equal() -> None:
    first = CheckResult(name="dns", status=Status.LEAK, value="198.51.100.7")
    second = CheckResult(name="dns", status=Status.LEAK, value="198.51.100.7")

    assert first == second


def test_status_and_classification_are_plain_strings() -> None:
    assert Status.UNAVAILABLE == "unavailable"
    assert Classification.ISP_RESIDENTIAL == "isp/residential"
    assert f"{Status.LEAK}" == "leak"


def test_unknown_status_string_is_rejected() -> None:
    with pytest.raises(ValueError):
        Status("unavailible")


def test_result_converts_to_json() -> None:
    result = CheckResult(
        name="dns",
        status=Status.LEAK,
        value="198.51.100.7",
        owner=Owner(org="Hotel ISP", asn=64511, country="US"),
        classification=Classification.ISP_RESIDENTIAL,
        reason="Resolver belongs to an ISP",
    )

    data = json.loads(json.dumps(asdict(result)))

    assert data == {
        "name": "dns",
        "status": "leak",
        "value": "198.51.100.7",
        "owner": {"org": "Hotel ISP", "asn": 64511, "country": "US"},
        "classification": "isp/residential",
        "reason": "Resolver belongs to an ISP",
    }
