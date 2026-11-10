# vpnleakcheck

Python CLI (`vpnleakcheck`) that tells a traveler, in one command, whether their VPN is protecting them on the current network: public IPv4/IPv6, IP ownership, and DNS resolver checks, combined into one verdict.

Full spec: @docs/SPEC.md
Current progress: @docs/PROGRESS.md

## Commands

- Install deps: `uv sync`
- Run the CLI: `uv run vpnleakcheck` (add `--json`, `--timeout N`)
- Tests: `uv run pytest`
- Lint and format: `uv run ruff check --fix . && uv run ruff format .`

Run tests and ruff before saying a change is done.

## How we work (I'm building this to learn)

I want to understand every part of this project, so we go step by step.

- At the start of a session, read docs/PROGRESS.md and tell me the current milestone and step.
- Do one step at a time (the M1.1, M1.2, ... list in PROGRESS.md). Never start the next step until I say so.
- Before writing code for a step: explain in a few sentences what we're building, why, and the concept behind it (networking, Python, or tooling). If there's a real choice to make (a library, an API, a design), give me the options with trade-offs and let me pick.
- Keep each change small enough to read in a couple of minutes. Write complete, runnable files, not fragments, and include the tests.
- After the change: walk me through the code briefly (the parts that aren't obvious) and give me the exact command to run it or test it myself.
- When I ask to change something, explain what the change affects before you make it.
- If I ask "why", answer the question before writing any more code.
- At the end of each step, update docs/PROGRESS.md: tick the step, set the current step, record any decision in Decisions, and add a line to "Notes for my LinkedIn posts" if we covered a concept worth writing about. Then suggest a commit message.

## Code rules

- Python 3.11+, src layout (`src/vpnleakcheck/`), packaged with pyproject.toml.
- Dependencies: typer, rich, httpx, dnspython, psutil. Tests: pytest, respx. Ask before adding anything else.
- Every check returns the shared result object (name, status, value, owner, classification, reason). Verdict and report code must not depend on how a check works.
- A failed request never crashes the tool. Mark that check `unavailable` and continue.
- Keep all external endpoints in one config file. Before using a new IP or ownership API, confirm it's free, needs no key, and allows this use.
- Tests never touch the real network. Mock HTTP with respx and DNS with fakes. Keep fixtures in `tests/fixtures/`.

## Hard limits

- Read-only. Never write code that changes DNS, routes, firewall rules, or VPN settings.
- No root required. Never use sudo.
- No telemetry. Store data only in `~/.config/vpnleakcheck/` and `~/.local/share/vpnleakcheck/`.
- Store only the first 64 bits of an IPv6 address in a baseline.

## Platform notes

- macOS first, Linux second. Flag any command or API that behaves differently between the two.
- macOS: resolvers come from `scutil --dns`. VPN interfaces usually show up as `utun*`, but macOS also creates `utun` interfaces for iCloud and other system services, so an up `utun` alone doesn't prove a VPN is on.
- macOS 14+: reading the Wi-Fi SSID needs Location Services permission. Fall back to "unknown network".
