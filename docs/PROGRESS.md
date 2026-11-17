# Progress

Updated at the end of every step. A new session starts by reading this file.

**Current milestone:** M2 IP checks
**Current step:** M2.5 (not started)

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
- [ ] M2.5 Captive-portal detection (response isn't an IP)

### M3 Ownership
- [ ] M3.1 Pick and verify an ownership API (ASN, org, country)
- [ ] M3.2 Ownership lookup with mocked tests
- [ ] M3.3 `data/known_providers.json` + keyword classification rules

### M4 DNS and interfaces
- [ ] M4.1 `whoami.akamai.net` resolver lookup with dnspython
- [ ] M4.2 Configured resolvers (`scutil --dns` on macOS, `/etc/resolv.conf` / resolvectl on Linux)
- [ ] M4.3 VPN interface detection with psutil (watch for macOS system `utun` interfaces)

### M5 Verdict and report (Level 1 done)
- [ ] M5.1 `verdict.py` + table-driven tests for every verdict row
- [ ] M5.2 Rich report
- [ ] M5.3 `--json` output and exit codes
- [ ] M5.4 Manual test on real networks

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
- Endpoint override: ship built-in defaults only for now. An optional override file in `~/.config/vpnleakcheck/` gets added in a later step, once the checks that read the endpoints exist. Until then the spec's "make the endpoints configurable" is not met.

## Open questions

Resolve each one before (or during) the step in brackets.

- [M5.3] Exit code clash: Typer/Click exits with 2 on usage errors, but the spec uses 2 for UNCERTAIN and 3 for usage errors. Remap Typer's usage errors to 3, or change the table?
- [M3.3 / M5.1] Public DNS resolvers (1.1.1.1, 8.8.8.8, Quad9) used outside the tunnel would classify as "hosting" and hide a DNS leak. Add a separate `public-dns` class that doesn't count as VPN?
- [M5.1] Verdict rules: which verdict wins when several rows match? What number counts as "too many checks unavailable"? How to handle a VPN on the router (no local VPN interface but the IPv4 is VPN-owned), which the current rules call NOT PROTECTED?
- [M4.3] Linux VPN interface names don't always fit `wg*`/`tun*` (e.g. `nordlynx`, `wg0-mullvad`, custom WireGuard names). How much weight do interface names get vs. IPv4 ownership?
- [M2.5] Behind a captive portal, HTTPS IP APIs usually fail with a TLS error or redirect instead of returning a login page. Treat those as captive-portal signals? Add a dedicated probe (e.g. `captive.apple.com`, would need vetting)?
- [M3.3] `known_providers.json` ships inside the installed package, so users can't edit it after `pipx install`. Ship defaults plus an optional override in the user config directory, as decided for endpoints? Also pick the step that builds both overrides.
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
