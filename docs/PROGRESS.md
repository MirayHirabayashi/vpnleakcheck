# Progress

Updated at the end of every step. A new session starts by reading this file.

**Current milestone:** M1 Skeleton
**Current step:** M1.2 (not started)

## Milestones

Each milestone is split into small steps. One step = one small change I can read, run, and understand before moving on.

### M1 Skeleton
- [x] M1.1 `pyproject.toml` with uv: project metadata, Python 3.11+, src layout, `vpnleakcheck` entry point
- [ ] M1.2 Minimal Typer app in `cli.py` with `--version` and `--help`
- [ ] M1.3 ruff config + first pytest test (`--version` prints the version)
- [ ] M1.4 `.gitignore`, short README stub, first commit

### M2 IP checks
- [ ] M2.1 Shared result object (name, status, value, owner, classification, reason)
- [ ] M2.2 Endpoint config file; pick and verify two free, no-key IPv4 services
- [ ] M2.3 IPv4 lookup from two services + disagreement warning, with respx tests
- [ ] M2.4 IPv6-only lookup; timeout = "no IPv6 route"; ignore `fe80::`
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
- Entry point is `vpnleakcheck.cli:app`. `cli.py` holds a placeholder `app()` until M1.2 replaces it with the Typer app.
- Development Python is 3.13 (`.python-version`); `requires-python` stays `>=3.11`. `uv.lock` is committed.

## Open questions

Resolve each one before (or during) the step in brackets.

- [M5.3] Exit code clash: Typer/Click exits with 2 on usage errors, but the spec uses 2 for UNCERTAIN and 3 for usage errors. Remap Typer's usage errors to 3, or change the table?
- [M3.3 / M5.1] Public DNS resolvers (1.1.1.1, 8.8.8.8, Quad9) used outside the tunnel would classify as "hosting" and hide a DNS leak. Add a separate `public-dns` class that doesn't count as VPN?
- [M5.1] Verdict rules: which verdict wins when several rows match? What number counts as "too many checks unavailable"? How to handle a VPN on the router (no local VPN interface but the IPv4 is VPN-owned), which the current rules call NOT PROTECTED?
- [M4.3] Linux VPN interface names don't always fit `wg*`/`tun*` (e.g. `nordlynx`, `wg0-mullvad`, custom WireGuard names). How much weight do interface names get vs. IPv4 ownership?
- [M2.5] Behind a captive portal, HTTPS IP APIs usually fail with a TLS error or redirect instead of returning a login page. Treat those as captive-portal signals? Add a dedicated probe (e.g. `captive.apple.com`, would need vetting)?
- [M2] 10-second goal vs. 5 s per-request timeout: checks must run concurrently. Async httpx or threads?
- [M2.2 / M3.3] `known_providers.json` and the endpoint config ship inside the installed package, so users can't edit them after `pipx install`. Ship defaults plus an optional override in the user config directory?
- [M1.4] `.gitignore`, README and LICENSE already exist and the remote is set up. Repurpose M1.4 (e.g. README update + GitHub Actions CI running ruff and pytest)?
- [M5.4] Confirm my VPN lets me turn DNS protection off, for the manual test matrix.
- [M7.3] README "Limitations" section: ownership lookups send your IP to a third party; browser DNS-over-HTTPS and WebRTC are invisible to a CLI.
- [M1.1] Test on Python 3.11 now and then (`uv run --python 3.11 pytest`), since development uses 3.13.

## Notes for my portfolio

Concepts I learned and want to share about.

- What `pyproject.toml` does, and how a `[project.scripts]` entry point turns a Python function into a terminal command. Why the src layout forces you to test the installed package. Front end (uv) vs. build backend (uv_build).
