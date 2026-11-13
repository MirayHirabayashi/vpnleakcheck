# vpnleakcheck

[![CI](https://github.com/MirayHirabayashi/vpnleakcheck/actions/workflows/ci.yml/badge.svg)](https://github.com/MirayHirabayashi/vpnleakcheck/actions/workflows/ci.yml)

**Is your VPN actually protecting you? Find out in one command.**

`vpnleakcheck` is a command-line tool for people who use a VPN on hotel, airport, and café Wi-Fi. It looks at your connection the way the rest of the internet sees it and tells you, in plain English, whether your VPN is doing its job or whether your real IP address, IPv6 traffic, or DNS lookups are slipping past it.

No browser tabs, no leak-test websites, no account. Just run it and get an answer.

> 🚧 **Work in progress.** This project is being built in public. Follow along as it comes together.

## Development

You need [uv](https://docs.astral.sh/uv/) and Python 3.11 or newer.

```sh
git clone https://github.com/MirayHirabayashi/vpnleakcheck
cd vpnleakcheck
uv sync                      # create .venv and install everything
uv run vpnleakcheck --help   # run the CLI
uv run pytest                # run the tests
uv run ruff check --fix . && uv run ruff format .   # lint and format
```

Every push and pull request runs the linter and the tests on Python 3.11 and 3.13 with GitHub Actions.
