# Progress

Updated at the end of every step. A new session starts by reading this file.

**Current milestone:** M1 Skeleton
**Current step:** M1.1 (not started)

## Milestones

Each milestone is split into small steps. One step = one small change I can read, run, and understand before moving on.

### M1 Skeleton
- [ ] M1.1 `pyproject.toml` with uv: project metadata, Python 3.11+, src layout, `leakcheck` entry point
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

- (none yet)

## Open questions

- (none yet)

## Notes for my LinkedIn posts

Concepts I learned and want to write about.

- (none yet)
