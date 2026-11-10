# Wi-Fi Leak Checker: Project Spec (Levels 1 & 2)

Nov 8, 2026 · @Miray

## Overview

`vpnleakcheck` is a Python command-line tool that tells a traveler, in one command, whether their VPN is actually protecting them on the current network. It checks the public IPv4 and IPv6 addresses, the DNS resolver in use, and whether any of them reveal the user's real ISP or location.

**Who it's for:** people who use a VPN on hotel, airport, and café Wi-Fi and want a quick, trustworthy "am I safe?" answer without opening several leak-test websites.

**Goals**

- One command, under 10 seconds, plain-English verdict.
- Level 1: detect whether the VPN is active, and whether IPv6 or DNS bypass it.
- Level 2: remember the user's real home network (a baseline) and flag any match on new networks; test whether traffic still flows when the VPN drops (kill-switch test); keep a local history.
- Clean, colorful terminal output and a `--json` mode for scripting.
- Works on macOS first, Linux second.

**Non-goals (for now)**

- Running our own authoritative DNS server for unique-subdomain leak tests (that is Level 3).
- WebRTC leak testing, which only applies inside a browser.
- Connecting to, configuring, or controlling any VPN.
- A GUI or menu bar app.

## How it works

Every check compares what the outside internet sees with what a working VPN should show. Four signals feed one verdict.

| Check | What it asks | How | Leak means |
| --- | --- | --- | --- |
| Public IPv4 | Which IPv4 address do websites see? | Query 2+ "what is my IP" APIs and compare | The address belongs to the local network or ISP, not the VPN |
| Public IPv6 | Do I have a working IPv6 route outside the tunnel? | Query an IPv6-only IP endpoint; a timeout means no IPv6 | An IPv6 address from the local ISP is reachable while the VPN only covers IPv4 |
| IP ownership | Who owns the visible IP? | Look up the IP's organization, ASN, and country | Owner is a consumer ISP, hotel, or mobile carrier instead of a hosting or VPN provider |
| DNS resolver | Which server is answering my DNS lookups? | A "who's asking" lookup such as `whoami.akamai.net`, which returns the resolver's IP; then look up that resolver's owner | Resolver belongs to the local ISP or hotel, not the VPN provider |

**Key concept: DNS leaks.** A VPN can encrypt traffic while DNS lookups still go to the hotel's or ISP's resolver, revealing every site visited. Common causes: split tunneling, IPv6 not routed through the VPN, and captive portals that trigger lookups before the VPN connects.

**Level 1 vs Level 2.** Level 1 judges each signal on its own ("this IP looks like a VPN"). Level 2 adds memory: it knows the user's real home ISP and IP, so it can say "this is *your* ISP, so the VPN is leaking" with much higher confidence.

## Level 1 requirements

Level 1 is a single `vpnleakcheck` command that runs all four checks and prints a verdict. No setup, no stored data.

**Command**

- `vpnleakcheck` runs every check and prints the report.
- `vpnleakcheck --json` prints the same results as JSON.
- `vpnleakcheck --timeout N` sets the per-request timeout in seconds (default 5).
- `vpnleakcheck --version` and `--help`.

**Functional requirements**

1. Detect active VPN interfaces locally (names like `utun*`, `wg*`, `tun*`, `ppp*`, `ipsec*`) and report which are up.
2. Fetch the public IPv4 from at least two independent services; warn if they disagree.
3. Attempt to fetch a public IPv6 address over an IPv6-only endpoint; treat a timeout as "no IPv6 route", which is good.
4. Look up organization, ASN, and country for each public IP.
5. Find the active DNS resolver with a "who's asking" lookup and look up its owner. Also list the system's configured resolvers (on macOS via `scutil --dns`).
6. Classify each IP and resolver owner as `vpn/hosting`, `isp/residential`, `mobile`, or `unknown`, using ASN and organization name keywords plus a small editable list in `data/known_providers.json`.
7. Combine the signals into one verdict (below) with a short plain-English reason for each finding.
8. Never crash on a failed request: mark that check `unavailable` and continue.

**Verdict rules (Level 1)**

| Verdict | When |
| --- | --- |
| PROTECTED | VPN interface up, IPv4 owner is vpn/hosting, no IPv6 route outside the tunnel, resolver is vpn/hosting or matches the VPN's network |
| LEAKING | VPN interface up, but IPv6 or the DNS resolver belongs to an ISP or mobile network |
| NOT PROTECTED | No VPN interface, or IPv4 owner is an ISP or mobile network |
| UNCERTAIN | Too many checks unavailable, or signals conflict |

## Level 2 requirements

Level 2 adds a saved baseline of the user's real network, a kill-switch test, and a local history, so verdicts say "this is *your* ISP" instead of guessing.

**New commands**

- `vpnleakcheck baseline` saves the real network fingerprint. Run at home **with the VPN off**; the tool asks for confirmation and refuses if a VPN interface is up (unless `--force`).
- `vpnleakcheck baseline --show` and `vpnleakcheck baseline --clear`.
- `vpnleakcheck` (default run) now compares results against the baseline.
- `vpnleakcheck killswitch` runs the kill-switch test.
- `vpnleakcheck history` lists past runs; `--last N` limits rows; `--export csv|json`.
- `vpnleakcheck watch --interval 30` re-runs checks every N seconds and alerts only when the verdict changes.

**Baseline**

1. Store: home public IPv4, IPv6 prefix (first 64 bits only), ISP ASN and organization, resolver IPs and their ASN, country, and the date saved.
2. On every run, flag any match: same ASN as the home ISP, same IPv4, same IPv6 prefix, or a home resolver in use. A match while a VPN interface is up = **LEAKING (matches your home network)**, the strongest finding.
3. Allow multiple named baselines, e.g. `--name home` and `--name phone-hotspot`.

**Kill-switch test**

Purpose: check whether traffic still leaves through the real network when the VPN drops.

1. Record the current public IP with the VPN on.
2. Ask the user to disconnect the VPN (the tool never controls the VPN itself), then press Enter.
3. Poll the public IP every second for 10 seconds.
4. Result: **PASS** if requests fail (traffic is blocked), **FAIL** if a non-VPN IP is returned, with the exposed IP and owner shown.
5. Remind the user to reconnect, and confirm once the VPN IP is back.

**History**

- Every run appends a record to a local SQLite database: timestamp, network name (Wi-Fi SSID if available), verdict, and each check's result.
- `history` shows a compact table, newest first, so the user can see which networks leaked on a trip.

**Level 2 verdict additions**

| Verdict | When |
| --- | --- |
| LEAKING (home match) | Any IP, prefix, ASN, or resolver matches a saved baseline while a VPN is active |
| PROTECTED (verified) | All Level 1 checks pass and nothing matches any baseline |

## Tech stack and project structure

Python 3.11+, packaged with `pyproject.toml` and installable with `pipx install` or `uv tool install`.

| Need | Choice | Why |
| --- | --- | --- |
| CLI framework | Typer | Subcommands and `--help` with little code |
| Terminal output | Rich | Colored tables, panels, spinners |
| HTTP requests | httpx | Timeouts, IPv4/IPv6 control, async if needed |
| DNS lookups | dnspython | Query `whoami.akamai.net` and read the answer |
| Network interfaces | psutil | List interfaces and their up/down state |
| Storage (Level 2) | sqlite3 (standard library) | History with no extra dependency |
| Config and baseline | JSON in `~/.config/vpnleakcheck/` | Easy to read and edit |
| Tests | pytest + respx | Mock HTTP responses, no network in tests |
| Lint and format | ruff | One fast tool |

```
vpnleakcheck/
├── pyproject.toml
├── README.md
├── src/vpnleakcheck/
│   ├── cli.py            # Typer app and subcommands
│   ├── checks/
│   │   ├── interfaces.py # local VPN interface detection
│   │   ├── public_ip.py  # IPv4 and IPv6 lookups
│   │   ├── ownership.py  # ASN, org, country, classification
│   │   └── dns.py        # resolver detection
│   ├── verdict.py        # combines results into a verdict
│   ├── baseline.py       # Level 2: save, load, compare
│   ├── killswitch.py     # Level 2: kill-switch test
│   ├── history.py        # Level 2: SQLite history
│   ├── report.py         # Rich output and JSON output
│   └── data/known_providers.json
└── tests/
```

Each check returns the same small result object (name, status, value, owner, classification, reason), so the verdict and report code never depend on how a check works.

## Output examples and exit codes

The report leads with the verdict, then one line per check, then what to do. Example values below are illustrative.

```
$ vpnleakcheck

  LEAKING: your DNS bypasses the VPN

  VPN interface   utun4 up                       ok
  Public IPv4     203.0.113.24 (Example VPN, NL) ok
  Public IPv6     none reachable                 ok
  DNS resolver    198.51.100.7 (Hotel ISP, US)   LEAK  matches home ISP

  Fix: turn on your VPN's DNS protection, or set DNS manually
  to your VPN provider's resolver, then run vpnleakcheck again.
```

```json
{
  "verdict": "LEAKING",
  "reasons": ["dns_resolver_isp", "baseline_match_asn"],
  "checks": {
    "vpn_interface": {"status": "ok", "value": "utun4"},
    "ipv4": {"status": "ok", "value": "203.0.113.24", "class": "vpn/hosting"},
    "ipv6": {"status": "ok", "value": null},
    "dns": {"status": "leak", "value": "198.51.100.7", "class": "isp/residential"}
  },
  "timestamp": "2026-11-08T07:30:00Z"
}
```

| Exit code | Meaning |
| --- | --- |
| 0 | PROTECTED |
| 1 | LEAKING or NOT PROTECTED |
| 2 | UNCERTAIN or offline |
| 3 | Usage or internal error |

## Edge cases, privacy and safety rules

The tool only inspects the user's own connection, stores everything locally, and never changes network settings.

**Edge cases to handle**

- **Captive portal not yet accepted:** IP lookups return a login page instead of an IP. Detect non-IP responses and report "Log in to this Wi-Fi first".
- **Offline:** all requests fail; verdict UNCERTAIN, exit code 2.
- **IP services disagree:** report both, lower confidence, prefer the majority.
- **Corporate or school networks** that force their own DNS: label the resolver owner clearly rather than assume a leak.
- **VPN providers on residential IPs** (some do this on purpose): never rely on classification alone; the baseline comparison is the stronger signal.
- **No Wi-Fi SSID available** (permissions or wired connection): store "unknown network".
- **IPv6 partially configured:** a link-local `fe80::` address is not a leak; only a globally reachable address counts.

**Privacy rules**

- Store data only in `~/.config/vpnleakcheck/` and `~/.local/share/vpnleakcheck/`; no telemetry, no accounts.
- Store only the first 64 bits of IPv6 addresses in the baseline.
- Use only public, no-key lookup services by default; make the endpoints configurable.
- `vpnleakcheck history --clear` deletes all history.

**Safety rules**

- Read-only: never edit DNS settings, routes, firewall rules, or VPN configuration.
- The kill-switch test asks the user to disconnect the VPN themselves.
- No root required for Level 1 or 2.

## Build milestones and testing plan

Build in seven small milestones; each ends with something runnable and tested.

- **M1 Skeleton:** `pyproject.toml`, Typer app, `vpnleakcheck --version`, ruff and pytest set up.
- **M2 IP checks:** public IPv4 from two services, IPv6 attempt, the shared result object.
- **M3 Ownership:** ASN, organization, country lookup and the classification rules.
- **M4 DNS and interfaces:** resolver detection and VPN interface detection.
- **M5 Verdict and report:** Level 1 verdict rules, Rich output, `--json`, exit codes. Level 1 done.
- **M6 Baseline and history:** `baseline` commands, comparison, SQLite history, `history` command.
- **M7 Kill switch, watch, release:** `killswitch`, `watch`, README with a demo GIF, publish to PyPI. Level 2 done.

Progress is tracked in `docs/PROGRESS.md`.

**Testing**

- Unit tests for every check with mocked HTTP and DNS responses; tests never touch the real network.
- Table-driven tests for `verdict.py` covering every row of the verdict tables above.
- Fixture files of real-looking API responses saved in `tests/fixtures/`.
- Manual test matrix on real networks: home with VPN off (baseline), home with VPN on, phone hotspot, a café or hotel network, VPN with DNS protection deliberately off.
