"""The shared result object that every check returns.

Verdict and report code read only these classes, so they never depend on how
a check gets its answer.
"""

from dataclasses import dataclass
from enum import StrEnum


class Status(StrEnum):
    """How a check turned out."""

    OK = "ok"
    LEAK = "leak"
    # The check ran and found something the user must act on that isn't a leak:
    # its sources gave conflicting answers, or a captive portal is in the way.
    WARNING = "warning"
    UNAVAILABLE = "unavailable"  # the check could not run (e.g. request failed)


class Classification(StrEnum):
    """What kind of network an IP address or resolver belongs to."""

    VPN_HOSTING = "vpn/hosting"
    ISP_RESIDENTIAL = "isp/residential"
    MOBILE = "mobile"
    UNKNOWN = "unknown"  # looked up, but the owner fits no known class


@dataclass(frozen=True)
class Owner:
    """Who owns an IP address. Any part the lookup didn't return is None."""

    org: str | None = None
    asn: int | None = None  # the number only: 64496, not "AS64496"
    country: str | None = None  # two-letter code, e.g. "NL"


@dataclass(frozen=True)
class CheckResult:
    """The outcome of one check.

    Only `name` and `status` are required. The other fields stay None when
    they don't apply: no IPv6 route means no `value`, and the interface check
    has no `owner` or `classification`.
    """

    name: str
    status: Status
    value: str | None = None
    owner: Owner | None = None
    classification: Classification | None = None
    reason: str = ""
