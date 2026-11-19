"""Captive-portal check: is a Wi-Fi login page standing between us and the internet?

Hotel and airport networks often hold every request until you accept their
terms. Behind such a portal the IP checks fail in confusing ways (TLS errors,
timeouts), so this check tells the user what is really going on: "log in to
this Wi-Fi first".

It asks a plain-HTTP probe that normally answers with an empty 204. The rules
are the ones Firefox uses (see endpoints.py).
"""

import httpx

from vpnleakcheck.endpoints import CAPTIVE_PORTAL_ENDPOINT, Endpoint
from vpnleakcheck.result import CheckResult, Status

CAPTIVE_PORTAL_CHECK = "captive_portal"

# 511 Network Authentication Required: the status code made for portals.
NETWORK_AUTH_REQUIRED = 511

LOG_IN_FIRST = "Log in to this Wi-Fi first, then run vpnleakcheck again"


async def check_captive_portal(
    client: httpx.AsyncClient,
    endpoint: Endpoint = CAPTIVE_PORTAL_ENDPOINT,
) -> CheckResult:
    """Find out whether a captive portal intercepts our web traffic.

    `ok`: the probe answered as expected, no portal.
    `warning`: a portal answered instead. `value` is its login page when known.
    `unavailable`: the probe couldn't be reached, so we can't tell.
    """
    try:
        # Never follow redirects, even if the caller's client does: the
        # redirect itself is the evidence we are looking for.
        response = await client.get(endpoint.url, follow_redirects=False)
    except httpx.HTTPError:
        # No connection, timeout, ...: offline, or the network drops everything.
        return CheckResult(
            name=CAPTIVE_PORTAL_CHECK,
            status=Status.UNAVAILABLE,
            reason=f"Couldn't reach the {endpoint.name} portal probe",
        )

    code = response.status_code

    # The expected answer: an empty 204 (Firefox also accepts an empty 200).
    if code in (200, 204) and not response.content:
        return CheckResult(
            name=CAPTIVE_PORTAL_CHECK,
            status=Status.OK,
            reason="No captive portal: the probe answered as expected",
        )

    if response.is_redirect:
        # The usual portal trick: send us to its login page. Report where.
        login_page = response.headers.get("location")
        return CheckResult(
            name=CAPTIVE_PORTAL_CHECK,
            status=Status.WARNING,
            value=login_page,
            reason=f"The network redirects web requests to a login page. "
            f"{LOG_IN_FIRST}",
        )

    if code == NETWORK_AUTH_REQUIRED or response.is_success:
        # 511, or a 2xx with a body: the portal served its own page in place
        # of the probe's answer.
        return CheckResult(
            name=CAPTIVE_PORTAL_CHECK,
            status=Status.WARNING,
            reason=f"The network replaced the probe's answer with its own page. "
            f"{LOG_IN_FIRST}",
        )

    # Any other status (4xx, 5xx): something is wrong with the probe, which is
    # not proof of a portal.
    return CheckResult(
        name=CAPTIVE_PORTAL_CHECK,
        status=Status.UNAVAILABLE,
        reason=f"The {endpoint.name} portal probe answered with HTTP {code}",
    )
