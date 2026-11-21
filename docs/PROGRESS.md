# Progress

Updated at the end of every step. A new session starts by reading this file.

**Current milestone:** M4 DNS and interfaces
**Current step:** M4.2 (not started)

## Milestones

Each milestone is split into small steps. One step = one small change I can read, run, and understand before moving on.

### M1 Skeleton
- [x] M1.1 `pyproject.toml` with uv: project metadata, Python 3.11+, src layout, `vpnleakcheck` entry point
- [x] M1.2 Minimal Typer app in `cli.py` with `--version` and `--help`
- [x] M1.3 ruff config + first pytest test (`--version` prints the version)
- [x] M1.4 README "Development" section + GitHub Actions CI (ruff and pytest on Python 3.11 and 3.13). `.gitignore`, README stub and LICENSE already existed

### M2 IP checks
- [x] M2.1 Shared result object (name, status, value, owner, classification, reason)
- [x] M2.2 Endpoint config file; pick and verify two free, no-key IPv4 services
- [x] M2.3 IPv4 lookup from two services + disagreement warning, with respx tests
- [x] M2.4 IPv6-only lookup; timeout = "no IPv6 route"; ignore `fe80::`
- [x] M2.5 Captive-portal detection (dedicated plain-HTTP probe, not the IP services' bodies)

### M3 Ownership
- [x] M3.1 Pick and verify an ownership API (ASN, org, country)
- [x] M3.2 Ownership lookup with mocked tests
- [x] M3.3 `data/known_providers.json` + keyword classification rules

### M4 DNS and interfaces
- [x] M4.1 `whoami.akamai.net` resolver lookup with dnspython
- [ ] M4.2 Configured resolvers (`scutil --dns` on macOS, `/etc/resolv.conf` / resolvectl on Linux)
- [ ] M4.3 VPN interface detection with psutil (watch for macOS system `utun` interfaces)

### M5 Verdict and report (Level 1 done)
- [ ] M5.1 `verdict.py` + table-driven tests for every verdict row
- [ ] M5.2 Rich report
- [ ] M5.3 `--json` output and exit codes
- [ ] M5.4 Manual test on real networks
- [ ] M5.5 User config overrides in `~/.config/vpnleakcheck/`: endpoints and `known_providers.json`, merged over the built-in defaults; a broken file gives a warning, never a crash

### M6 Baseline and history
- [ ] M6.1 `baseline` save / show / clear, named baselines, VPN-up refusal
- [ ] M6.2 Baseline comparison in the default run
- [ ] M6.3 SQLite history + `history` command, `--last`, `--export`, `--clear`

### M7 Kill switch, watch, release (Level 2 done)
- [ ] M7.1 `killswitch` test
- [ ] M7.2 `watch --interval`
- [ ] M7.3 README with demo GIF
- [ ] M7.4 Publish to PyPI

## Decisions

Record each choice and why, one line each, so later sessions don't reopen them.

- Name everything `vpnleakcheck`: PyPI distribution, import package (`src/vpnleakcheck/`), and CLI command. `leakcheck` is already taken on PyPI (checked 2026-11-10), and one name everywhere matches the GitHub repo and README.
- Build backend: `uv_build` (pinned `>=0.11.21,<0.12`). Zero config for the src layout and one fewer tool to learn; bump the range when uv moves to 0.12.
- Add each dependency in the step that first uses it (`uv add`), not all up front, so every library's purpose is clear when it arrives.
- Version lives only in `pyproject.toml` (`0.1.0`); code reads it with `importlib.metadata` instead of a second hard-coded copy.
- Entry point is `vpnleakcheck.cli:app`, where `app` is the `typer.Typer()` object (it is callable).
- The default run lives in an `@app.callback(invoke_without_command=True)` function, not an `@app.command()`, so bare `vpnleakcheck` runs the checks and subcommands (`baseline`, `history`, ...) can be added later without restructuring.
- `--version` is an eager option with a callback, so it prints and exits before any other argument is parsed.
- Shell completion options are hidden (`add_completion=False`) to keep `--help` short; revisit at M7 if wanted.
- Development Python is 3.13 (`.python-version`); `requires-python` stays `>=3.11`. `uv.lock` is committed.
- ruff and pytest are dev dependencies in `[dependency-groups] dev` (`uv add --dev`), so users who install the tool never get them. Their config lives in `pyproject.toml`, no extra config files.
- ruff rules: `E`, `W`, `F`, `I`, `UP`, `B`, `SIM`; line length 88 (the default). Wider than ruff's default `E`/`F` but still low-noise; add more only when a rule would have caught a real problem.
- CLI tests call the app in-process with Typer's `CliRunner` (no subprocess). The version test compares against `importlib.metadata`, not a hard-coded `0.1.0`, so a version bump doesn't break it.
- The test `CliRunner` sets `TERM=dumb` so Rich prints plain text. Typer forces coloured output when `GITHUB_ACTIONS` is set, and the ANSI codes split `--version` in two, which broke the `--help` test on CI only. `NO_COLOR` doesn't help (it keeps bold).
- M1.4 repurposed: `.gitignore`, README and LICENSE already existed, so the step became a README "Development" section plus CI. GitHub Actions is free for public repos.
- CI (`.github/workflows/ci.yml`) runs on pushes to `main` and on pull requests, on `ubuntu-latest`, with a matrix of Python 3.11 (oldest supported) and 3.13 (development). Steps: `uv sync --locked`, `ruff check`, `ruff format --check`, `pytest`. CI never uses `--fix`.
- Actions are pinned to full commit SHAs (with the version in a comment), as the uv docs do, so a moved tag can't change what runs. Update the SHA and the comment together.
- CI runs on Linux only for now. Add a `macos-latest` job at M4, when platform-specific code (`scutil --dns`, `utun`) arrives.
- The shared result object is `CheckResult` in `src/vpnleakcheck/result.py`: a frozen dataclass (standard library, immutable once a check returns it, `dataclasses.asdict()` feeds `--json`). Only `name` and `status` are required; `value`, `owner` and `classification` default to `None` and `reason` to `""`.
- `Status` (`ok`, `leak`, `unavailable`) and `Classification` (`vpn/hosting`, `isp/residential`, `mobile`, `unknown`) are `StrEnum`s: a typo fails at once, and members are real strings so they serialise to JSON unchanged. Add a `warning` status in M2.3 only if "services disagree" needs it.
- `classification=None` means "doesn't apply to this check" (e.g. interfaces); `Classification.UNKNOWN` means "looked up, but fits no class".
- `owner` is a frozen `Owner` dataclass (`org`, `asn`, `country`), not a string, so the M6 baseline can compare ASNs without parsing. `asn` is an `int` (64496, not "AS64496"); `country` is a two-letter code.
- All external endpoints live in `src/vpnleakcheck/endpoints.py`: a Python module with a frozen `Endpoint` dataclass (`name`, `url`) and an `IPV4_ENDPOINTS` tuple. No parsing code, a typo fails at import, and comments record where and when each service was verified. Checks import from it and never hard-code a URL.
- IPv4 services: ipify (`https://api.ipify.org`) and ident.me (`https://4.ident.me`), verified 2026-11-15. Both are free, need no key, and state in writing that any use is allowed (ident.me asks for an email above 500 requests/s). Both hostnames have no AAAA record, so the request can only leave over IPv4, and both have IPv6-only siblings (`api6.ipify.org`, `6.ident.me`) for M2.4.
- Rejected icanhazip as the second service: it and ipify both sit behind Cloudflare (AS13335), so they aren't independent. ident.me is on Hetzner. Rejected `checkip.amazonaws.com`: no published terms and no IPv6-only sibling. Either can be a fallback if ident.me (run by one person) proves unreliable.
- Responses are bare `text/plain` addresses, but some services add a trailing newline, so M2.3 must strip the body before parsing.
- Concurrency: async httpx (`httpx.AsyncClient` + `asyncio.gather`), chosen in M2.3 over threads or sequential calls. Every request in a run happens at once, so the run takes as long as the slowest request (about 5 s at worst), not the sum, which keeps the 10-second goal. The CLI will wrap the checks in `asyncio.run()`. Tests call `asyncio.run()` too, so no pytest-asyncio dependency.
- Checks take an `httpx.AsyncClient` from the caller instead of creating their own, so one client (one timeout, one connection pool) is shared by every check in a run.
- Added `Status.WARNING` (M2.3): the check ran but its sources conflict. Used when IPv4 services disagree, so the verdict can see "signals conflict" from the status alone without parsing `reason`.
- IPv4 check returns one `CheckResult` named `ipv4` (matches the spec JSON). Majority wins. On a tie, the service listed first in `endpoints.py` wins (`Counter.most_common` keeps first-seen order). One service answering is still `ok`, and the reason names the silent one. None answering is `unavailable`.
- A non-IPv4 body (login page, empty, an IPv6 address) counts as "no answer" from that service for now. M2.5 will turn it into a captive-portal signal.
- httpx is a runtime dependency (added in M2.3), respx a dev dependency.
- IPv6 services (M2.4): `api6.ipify.org` and `6.ident.me`, verified 2026-11-17 as AAAA-only (no A record), so the request can only leave over IPv6. Same operators and terms as the IPv4 pair. Both are asked at once: for IPv6 a failure reads as "safe", so one service's outage must not be able to fake "no IPv6 route".
- IPv6 "no route" means connection-level failure only (`httpx.ConnectError`, `httpx.ConnectTimeout`) from every service: `ok`, `value=None`. If any service was reached over IPv6 but gave no usable address (4xx/5xx, read timeout, non-IPv6 body), a route exists, so the check is `unavailable`, not safe. Known gap: httpx reports a failed TLS handshake as `ConnectError`, so it counts as no route.
- An IPv6 answer counts only if `ipaddress` says `is_global`: link-local `fe80::`, unique-local `fc00::/7`, loopback and documentation `2001:db8::` are rejected as bad answers. Test fixtures therefore use a made-up global address, not `2001:db8::`.
- A found IPv6 address is `ok` with the address as `value`, like IPv4. Whether it leaks depends on its owner (VPN-tunnelled IPv6 exists), so M3 ownership and M5 verdict decide, not the check.
- IPv4 and IPv6 share one `_compare` helper (majority wins, `warning` on disagreement), so both behave the same. IPv6 tests live in their own file, `tests/test_public_ipv6.py`. Endpoint rule tests now run over every endpoint list, and no host may appear in two lists.
- Captive portals (M2.5): a dedicated probe, not the IP services. Behind a portal our HTTPS IP services fail with TLS errors or timeouts instead of returning a login page, so "non-IP body" almost never fires. Rejected: reading IP-service bodies only (misses the common case) and treating TLS errors as a portal (corporate HTTPS inspection and antivirus break TLS too).
- Probe: Firefox's `http://firefox-portal-detection.com/generate_204` (Mozilla Corporation, Fastly, A + AAAA), verified 2026-11-19 against the Firefox source docs. Chosen over Apple's and Google's probes because Mozilla documents it openly; no published terms for other clients, accepted since every Firefox install calls it. The older `detectportal.firefox.com/success.txt` still answers but is no longer the documented default.
- The probe is the only plain-HTTP endpoint, on purpose: a portal can only show itself by rewriting a request it can read. The HTTPS endpoint test excludes it, and a separate test pins it to `http`.
- Portal rules copy Firefox's: empty 200/204 = `ok`; 3xx, 511 or any other 2xx = portal; connection errors and other 4xx/5xx = `unavailable` (not proof of a portal). Redirects are never followed (`follow_redirects=False` on the request), and the `Location` header becomes `value`, so the report can show the login page.
- A portal is `Status.WARNING` (widened to "the check ran and found something the user must act on that isn't a leak"), not `LEAK` and not a new status. Lives in its own module `checks/captive_portal.py` as a `CheckResult` named `captive_portal`.
- Behind a portal, the IPv6 check's TLS-as-no-route gap (M2.4) can fake "no IPv6 route". M5.1 verdict must not call IPv6 safe while `captive_portal` is `warning`; the IP checks themselves are unchanged.
- Endpoint override: ship built-in defaults only for now. An optional override file in `~/.config/vpnleakcheck/` gets added in a later step, once the checks that read the endpoints exist. Until then the spec's "make the endpoints configurable" is not met.
- Ownership API (M3.1): RIPEstat (RIPE NCC, non-profit), verified 2026-11-19. Free, no key, no paid tier, IPv4 + IPv6, global coverage, no request cap (register above ~1000/day, max 8 parallel per IP). Two calls per IP, run in parallel: `prefix-overview` (ASN + holder) and `maxmind-geo-lite` (country where the IP is used). Both send `sourceapp=vpnleakcheck` (`RIPESTAT_SOURCEAPP`); the check adds `resource` and `sourceapp` as params, URLs carry no query.
- RIPEstat terms Art. 3.3: commercial use (paid services/products) needs written permission from stat@ripe.net, and the data may not be redistributed. Fine for a free tool doing live lookups of the user's own IP; revisit before selling anything built on it.
- Rejected for ownership: ip-api.com (free tier is plain HTTP only, so the untrusted network could read or rewrite the answer; non-commercial only), Team Cymru DNS (query goes through the suspect resolver, portals hijack DNS, country is registry data not location), ipinfo without a token (legacy API "may be discontinued"), ipapi.co (rate-limited on first call), iptoasn.com (no response). ipwho.is (1000/day, no SLA, one call, commercial OK) is the fallback if RIPEstat proves unreliable.
- RIPEstat response shapes M3.2 must handle (fixtures `tests/fixtures/ripestat_*.json`): `data.asns` is a list (can be empty with `announced: false`, or hold several ASNs); `holder` reads `"SHORTNAME - Full Name"`; an unknown country is an empty `located_resources`, not an error; a 200 still needs `status == "ok"` checked.
- Ownership endpoints share one host (`stat.ripe.net`) on purpose, so they're outside the "different hosts" test; a separate test keeps that host apart from every IP service and the portal probe.
- Ownership (M3.2) is a helper, not a check: `lookup_owner(client, ip) -> Owner | None` in `checks/ownership.py`. The spec JSON has no separate ownership entry, so a later step puts the `Owner` on the ipv4/ipv6/dns results (`dataclasses.replace`). Rejected: a separate `CheckResult` per owner (duplicates the IP, doesn't match the spec JSON).
- `Owner.org` stores RIPEstat's holder raw. Its format differs by registry (`"CLOUDFLARENET - Cloudflare, Inc."` from ARIN, `"HETZNER-AS Hetzner Online GmbH"` and `"M247 M247 Europe SRL"` from RIPE), so no cleaning heuristic is safe; M3.3 keywords can match the handle too, and M5.2 may tidy it for display only.
- Partial answers are kept (only the ASN call worked → `country=None`, and the reverse); `None` only when nothing was learned. Several ASNs → first listed wins. Any HTTP error, non-JSON body, RIPEstat `status` other than `"ok"`, or unexpected shape drops that half of the answer.
- Unknown country arrives three ways: empty `located_resources`, a missing key, or `"country": "?"` (real, for anycast addresses like 1.1.1.1). Only `^[A-Z]{2}$` is accepted.
- `lookup_owner` never sends a non-global address (private, CGNAT `100.64/10`, loopback, link-local, unique-local, documentation): it means nothing on the internet and would leak local network details. Tests therefore use 8.8.8.8 / `2001:4860:4860::8888`, not the documentation ranges.
- `lookup_owner` takes no `endpoints` argument (unlike the IP checks): the parsing is RIPEstat-specific, so swapping the URL for another service couldn't work anyway.
- Classification (M3.3): `classify(owner, providers=None) -> Classification` in `checks/ownership.py` (where the spec puts it). Exact ASN match first, then whole-word, case-insensitive keywords in the holder name, else `unknown`. The caller only classifies when `lookup_owner` returned an `Owner`; no owner keeps `classification=None`.
- Keyword precedence is mobile > isp/residential > vpn/hosting, the cautious order: calling an ISP "hosting" hides a leak, calling a VPN server an ISP is only a false alarm. It lives in code (`KEYWORD_PRECEDENCE`), not in the JSON, because it's a safety rule.
- New `Classification.PUBLIC_DNS` (`"public-dns"`) for Cloudflare 13335, Google 15169, Quad9 19281, Cisco OpenDNS 36692. Assigned by exact ASN only (no keywords), so a DNS leak to 8.8.8.8 doesn't read as the VPN's resolver. `classify` only labels; M5.1 decides what it means per check.
- `src/vpnleakcheck/data/known_providers.json`: an `asns` list (`asn`, `class`, `name` = RIPEstat holder) plus `keywords` per class, with `about` and `verified` keys in place of comments (JSON has none). 26 ASNs seeded, each verified via RIPEstat `as-overview` on 2026-11-19: hosting/VPN networks (M247, Datacamp, Hetzner, OVH, DigitalOcean, LeaseWeb, Vultr, Linode, AWS ×2, Google Cloud, Microsoft, Mullvad's 31173 Services, NordVPN's PacketHub ×2, Proton ×2), 4 public DNS, 4 US mobile, Comcast.
- The ASN list catches what keywords can't: Verizon's mobile ASNs are registered as "CELLCO - Verizon Business", AT&T Mobility as "AT&T Enterprises" (hence the `mobility` keyword, matched in the handle).
- Read with `importlib.resources.files("vpnleakcheck")`, so it works from an installed wheel (confirmed: uv_build includes `data/known_providers.json` with no config). Loaded once per run (`functools.cache`).
- `load_providers(path)` validates and raises `ValueError` on any broken entry (bad ASN, unknown class, `unknown` assigned, duplicate ASN, keywords for `public-dns`, empty keyword), so a bad edit fails loudly instead of quietly making everything `unknown`. M5.5 turns that error into a warning for user override files.
- User overrides for both endpoints and providers get their own step, M5.5, once the CLI runs the checks.
- RIPEstat is sometimes slow: uncached `as-overview` queries took over 15 s in testing, and a 3.7 s answer was common. With the 5 s default timeout an ownership lookup will sometimes come back `None`; M5 must treat that as "owner unknown", not as an error.
- `watch` (M7.2) must cache owners by IP (an IP's owner doesn't change in 30 s) to stay within RIPEstat's fair-use guidance.
- DNS resolver check (M4.1): dnspython's `dns.asyncresolver`, chosen over the OS resolver (`loop.getaddrinfo`). It's async, has a real timeout (`lifetime`), separate exceptions per failure, and is easy to fake. `getaddrinfo` runs in a thread with no real timeout, so a dropped DNS query could hold the tool at exit for 30 s or more.
- Known gap: dnspython sends plain DNS to the servers in `/etc/resolv.conf`. On macOS with a system-wide encrypted DNS profile (NextDNS, 1.1.1.1 apps) apps use that instead, so the check can raise a false alarm, never hide a leak. Linux with systemd-resolved is fine (the `127.0.0.53` stub forwards). Goes in the M7.3 README Limitations.
- Who's-asking name: `whoami.akamai.net` A only (`DNS_WHOAMI_NAME` in `endpoints.py`, a bare name, not an `Endpoint`), verified 2026-11-21 with dig. AAAA gives NXDOMAIN. One source only: Google's `o-o.myaddr.l.google.com` TXT gave NXDOMAIN on the test network.
- `check_dns(resolver)` in `checks/dns.py` returns a `CheckResult` named `dns`. A global IPv4 answer is `ok` with the resolver's IP as `value`. A non-global answer (private, CGNAT, loopback, `0.0.0.0`) is `warning`, because Akamai can only see a public address, so the network made it up (portal or DNS filter). Any lookup failure is `unavailable`. Owner and class get added later, as for the IPs.
- The caller owns the resolver (like the httpx client): `make_system_resolver(timeout)` sets `lifetime` to `--timeout`. With no DNS config it returns an empty resolver, whose lookup fails with `NoNameservers`, so the check reports `unavailable` instead of crashing. Tests pass a `FakeResolver` that returns real dnspython `RRset`s or raises real dnspython errors.
- dnspython is a runtime dependency (added in M4.1, 2.9.2).
- The macOS CI job promised for M4 is still to do; add it in M4.2, where `scutil --dns` is the first macOS-only code.

## Open questions

Resolve each one before (or during) the step in brackets.

- [M5.3] Exit code clash: Typer/Click exits with 2 on usage errors, but the spec uses 2 for UNCERTAIN and 3 for usage errors. Remap Typer's usage errors to 3, or change the table?
- [M5.1] Verdict rules: which verdict wins (and a detected captive portal should override everything with "log in first") when several rows match? What number counts as "too many checks unavailable"? How to handle a VPN on the router (no local VPN interface but the IPv4 is VPN-owned), which the current rules call NOT PROTECTED?
- [M4.3] Linux VPN interface names don't always fit `wg*`/`tun*` (e.g. `nordlynx`, `wg0-mullvad`, custom WireGuard names). How much weight do interface names get vs. IPv4 ownership?
- [M5.1] What `public-dns` means per check: for `dns` it isn't the VPN's resolver (a leak or warning?); for `ipv4`/`ipv6` it may be a VPN like Cloudflare WARP (exits from AS13335). Also: how to treat `unknown` (e.g. Andrews & Arnold, a real UK ISP, has no keyword and comes out `unknown`).
- [M5.4] Confirm my VPN lets me turn DNS protection off, for the manual test matrix.
- [M7.3] README "Limitations" section: ownership lookups send your IP to a third party; browser DNS-over-HTTPS and WebRTC are invisible to a CLI.

## Notes for my portfolio

Concepts I learned and want to share about.

- What `pyproject.toml` does, and how a `[project.scripts]` entry point turns a Python function into a terminal command. Why the src layout forces you to test the installed package. Front end (uv) vs. build backend (uv_build).
- How Typer turns a function signature into a CLI: type hints become options, the docstring becomes the help text. Callback vs. command, and why `--version` has to be an "eager" option.
- Linter vs. formatter, and why ruff does both. How pytest discovers tests, and how `CliRunner` tests a CLI without starting a real process. Dev dependencies vs. runtime dependencies.
- What continuous integration is and why to add it while the test suite is tiny. Anatomy of a GitHub Actions workflow: trigger, job, matrix, steps. Why CI uses `uv sync --locked` and `ruff format --check` (report, never modify), and why actions are pinned to a commit SHA.
- Data contracts: why every check returns one shared shape, so the verdict and report never depend on how a check works. Dataclasses (`frozen=True`, defaults, free `==`, `asdict()`), and `StrEnum` vs. plain strings for a fixed set of values.
- Why your computer can't know its own public IP (NAT and VPNs rewrite it on the way out), so you have to ask a server. How to vet a free API before depending on it: terms, key, rate limit, who hosts it. Two services on the same network (both behind Cloudflare) aren't really independent. A records vs. AAAA records, and how a hostname with no AAAA record forces IPv4.
- async/await in Python: what an event loop is, why `asyncio.gather` makes two 5-second requests take 5 seconds instead of 10, and why I/O-bound work like HTTP calls suits async. Designing for failure: most of a network check is deciding what each failure (timeout, 5xx, garbage body) means. Mocking HTTP with respx so tests cover every failure without the network.
- IPv6 leaks: why a VPN that only tunnels IPv4 leaks on dual-stack Wi-Fi, and how an AAAA-only hostname tests the IPv6 path on its own. When failure is the safe outcome, you need two services and must tell "never connected" (no route) apart from "connected, bad answer" (route exists). Link-local `fe80::` vs. global addresses, and `ipaddress.is_global`.
- Captive portals: how hotel Wi-Fi hijacks DNS or redirects HTTP until you log in, why an HTTPS request can only fail behind a portal while plain HTTP lets the portal show itself, and how OSes and browsers detect portals with a "known answer" probe (an empty 204). HTTP 511 Network Authentication Required. Why a probe must never follow redirects.
- Who owns an IP: ASNs, BGP announcements, and the regional registries (ARIN, RIPE, ...). Registry country vs. geolocation country. Why a security tool must never look up ownership over plain HTTP on an untrusted network (the network can rewrite "ISP" into "hosting"). Reading an API's terms: "free" vs. "free for non-commercial use" vs. "no redistribution".
- Parsing someone else's JSON defensively: a 200 isn't success, "unknown" can arrive in three different shapes, and one live call found a case (`"?"` for anycast 1.1.1.1) that the saved fixtures didn't have. Anycast: one IP served from many countries at once. Why a privacy-minded tool refuses to send private addresses to an API.
- Heuristic classifiers and asymmetric errors: when one mistake hides a leak and the other only raises a false alarm, ties go to the cautious answer. Exact lists vs. keyword rules (Verizon's mobile network calls itself "Verizon Business"). Regex word boundaries (`\b`). Keeping safety rules in code and data in an editable file, and making a bad edit fail loudly. Shipping data files inside a Python package with `importlib.resources`.
- DNS leaks from the inside: stub vs. recursive vs. authoritative resolvers, and why the resolver you configured (often the router) isn't the one doing the work. How a "who's asking" name like `whoami.akamai.net` makes the authoritative server report the resolver's own address. Why a private address in that answer proves the network is tampering with DNS. Library resolvers (`/etc/resolv.conf`) vs. the OS resolver, and how encrypted DNS profiles open a gap between them.
