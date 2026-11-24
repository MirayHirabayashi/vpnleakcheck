"""Configured DNS resolvers: which servers is this machine told to ask?

This is not the same as the DNS check (dns.py). That one finds the resolver
that really does the work, as seen from the internet. This one reads the
operating system's settings: the list of servers it sends DNS queries to. On a
home network that is usually the router; with a VPN it should include a
VPN-owned address.

Read-only: we only run `scutil --dns` / `resolvectl status` and read
/etc/resolv.conf. Nothing is changed.

Platform notes:
- macOS: `scutil --dns` lists every resolver, including ones a VPN adds for
  one interface (shown as `if_index : 17 (utun4)`). /etc/resolv.conf is only a
  summary of the main one. Entries for a single domain (`domain : local`,
  or a company's `corp.example`) are skipped: they only answer for that
  domain, not for general lookups.
- Linux with systemd-resolved: /etc/resolv.conf only says `127.0.0.53` (a local
  stub), so we ask `resolvectl status` for the real servers first.
- Anything else, or if the command is missing: fall back to /etc/resolv.conf.
"""

import ipaddress
import re
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

RESOLV_CONF = Path("/etc/resolv.conf")
COMMAND_TIMEOUT = 5  # seconds; these commands answer instantly when they work


@dataclass(frozen=True)
class ConfiguredResolver:
    """One DNS server the system is configured to use."""

    address: str  # IPv4 or IPv6, without any `%interface` suffix
    interface: str | None = None  # e.g. "en0" or "utun4", when known


def _address(text: str) -> str | None:
    """A clean IP address from `text`, or None. Drops `%en0` and `#name` suffixes."""
    candidate = re.split(r"[%#]", text.strip(), maxsplit=1)[0]
    try:
        return str(ipaddress.ip_address(candidate))
    except ValueError:
        return None


def _merge(found: list[ConfiguredResolver]) -> list[ConfiguredResolver]:
    """Remove duplicates, keeping order. Prefer the entry that names an interface.

    macOS lists the same server twice (plain and "scoped"), and only one copy
    may carry the interface.
    """
    merged: dict[str, ConfiguredResolver] = {}
    for item in found:
        current = merged.get(item.address)
        if current is None or (current.interface is None and item.interface):
            merged[item.address] = item
    return list(merged.values())


def parse_scutil(text: str) -> list[ConfiguredResolver]:
    """Read the output of `scutil --dns`."""
    found: list[ConfiguredResolver] = []
    # Each "resolver #N" block is one resolver; split on the heading.
    for block in re.split(r"^resolver #\d+\s*$", text, flags=re.MULTILINE)[1:]:
        if re.search(r"^\s*domain\s*:", block, flags=re.MULTILINE):
            continue  # only answers for one domain
        match = re.search(r"^\s*if_index\s*:\s*\d+\s*\((\S+)\)", block, re.MULTILINE)
        interface = match.group(1) if match else None
        for line in re.findall(r"^\s*nameserver\[\d+\]\s*:\s*(\S+)", block, re.M):
            if address := _address(line):
                found.append(ConfiguredResolver(address, interface))
    return _merge(found)


def parse_resolv_conf(text: str) -> list[ConfiguredResolver]:
    """Read /etc/resolv.conf: one `nameserver <address>` line per server."""
    found = []
    for line in text.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[0] == "nameserver" and (a := _address(parts[1])):
            found.append(ConfiguredResolver(a))
    return _merge(found)


def parse_resolvectl(text: str) -> list[ConfiguredResolver]:
    """Read `resolvectl status`: a `DNS Servers:` line per `Link N (name)` section.

    A long list continues on the following lines, indented and holding only
    addresses.
    """
    found: list[ConfiguredResolver] = []
    interface: str | None = None
    in_servers = False
    for line in text.splitlines():
        if link := re.match(r"^Link \d+ \((\S+)\)", line):
            interface, in_servers = link.group(1), False
            continue
        if re.match(r"^(Global|Link \d+)", line):
            # Section headings sit at column 0, but so does the longest label
            # ("Current DNS Server:"), so only headings may reset the interface.
            interface, in_servers = None, False  # the "Global" section
            continue
        servers = re.match(r"^\s*DNS Servers:\s*(.*)$", line)
        tokens = servers.group(1).split() if servers else line.split()
        addresses = [a for t in tokens if (a := _address(t))]
        if servers:
            in_servers = True
        elif not (in_servers and tokens and len(addresses) == len(tokens)):
            in_servers = False  # not a continuation line
            continue
        found.extend(ConfiguredResolver(a, interface) for a in addresses)
    return _merge(found)


def _run(command: list[str]) -> str:
    """Run a read-only command and return its output, or "" if it can't run."""
    try:
        done = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=COMMAND_TIMEOUT,
            check=True,
        )
    except (OSError, subprocess.SubprocessError):
        return ""  # missing, timed out, or failed: the caller falls back
    return done.stdout


def _read(path: Path) -> str:
    try:
        return path.read_text()
    except OSError:
        return ""


def get_configured_resolvers(
    platform: str | None = None,
    run: Callable[[list[str]], str] = _run,
    read: Callable[[Path], str] = _read,
) -> list[ConfiguredResolver]:
    """The DNS servers this machine is set to use; an empty list if unknown.

    This blocks briefly (it may run a command), so async code should call it
    with `asyncio.to_thread`. `platform`, `run` and `read` exist so tests can
    pass fakes.
    """
    platform = platform or sys.platform
    if platform == "darwin":
        if found := parse_scutil(run(["scutil", "--dns"])):
            return found
    elif platform.startswith("linux") and (
        found := parse_resolvectl(run(["resolvectl", "status", "--no-pager"]))
    ):
        return found
    return parse_resolv_conf(read(RESOLV_CONF))
