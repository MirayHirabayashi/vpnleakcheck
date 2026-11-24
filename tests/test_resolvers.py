"""Tests for configured-resolver detection.

The parsers read saved command output from tests/fixtures/, so they run the same
on any platform. `get_configured_resolvers` gets fake `run` and `read` functions,
so no command is run and no real file is read.
"""

from pathlib import Path

from vpnleakcheck.checks.resolvers import (
    ConfiguredResolver,
    get_configured_resolvers,
    parse_resolv_conf,
    parse_resolvectl,
    parse_scutil,
)

FIXTURES = Path(__file__).parent / "fixtures"


def fixture(name: str) -> str:
    return (FIXTURES / name).read_text()


def test_scutil_home_skips_mdns_entries_and_dedupes_scoped_copy():
    # Real output: resolver #1 twice (plain + scoped) plus five nameserver-less
    # mdns entries.
    assert parse_scutil(fixture("scutil_dns_home.txt")) == [
        ConfiguredResolver("192.168.0.1", "en0")
    ]


def test_scutil_vpn_finds_the_vpn_resolver_on_its_interface():
    found = parse_scutil(fixture("scutil_dns_vpn.txt"))
    assert ConfiguredResolver("10.64.0.1", "utun4") in found
    assert ConfiguredResolver("192.168.0.1", "en0") in found


def test_scutil_strips_ipv6_zone_suffix():
    found = parse_scutil(fixture("scutil_dns_vpn.txt"))
    assert ConfiguredResolver("fe80::1", "en0") in found


def test_scutil_skips_domain_only_resolvers():
    addresses = [r.address for r in parse_scutil(fixture("scutil_dns_vpn.txt"))]
    assert "172.16.5.5" not in addresses  # only answers for corp.example.test


def test_scutil_garbage_gives_empty_list():
    assert parse_scutil("") == []
    assert parse_scutil("scutil: not what you expected") == []


def test_resolv_conf_reads_nameservers_and_ignores_bad_lines():
    assert parse_resolv_conf(fixture("resolv_conf_plain.txt")) == [
        ConfiguredResolver("192.168.1.1"),
        ConfiguredResolver("2001:4860:4860::8888"),
    ]


def test_resolvectl_reads_servers_per_link_with_continuation_lines():
    assert parse_resolvectl(fixture("resolvectl_status.txt")) == [
        ConfiguredResolver("10.0.2.3", "enp0s3"),
        ConfiguredResolver("10.0.2.4", "enp0s3"),
        ConfiguredResolver("10.2.0.1", "wg0"),
        ConfiguredResolver("fd00::1", "wg0"),
    ]


def fakes(command_output: str = "", file_text: str = ""):
    """A fake `run` that records the command, and a fake `read`."""
    commands: list[list[str]] = []

    def run(command: list[str]) -> str:
        commands.append(command)
        return command_output

    return commands, run, lambda path: file_text


def test_macos_uses_scutil():
    commands, run, read = fakes(fixture("scutil_dns_home.txt"), "nameserver 9.9.9.9")
    found = get_configured_resolvers("darwin", run, read)
    assert commands == [["scutil", "--dns"]]
    assert found == [ConfiguredResolver("192.168.0.1", "en0")]


def test_macos_falls_back_to_resolv_conf_when_scutil_fails():
    _, run, read = fakes("", "nameserver 9.9.9.9")
    assert get_configured_resolvers("darwin", run, read) == [
        ConfiguredResolver("9.9.9.9")
    ]


def test_linux_prefers_resolvectl():
    commands, run, read = fakes(
        fixture("resolvectl_status.txt"), "nameserver 127.0.0.53"
    )
    found = get_configured_resolvers("linux", run, read)
    assert commands[0][0] == "resolvectl"
    assert ConfiguredResolver("10.0.2.3", "enp0s3") in found
    assert all(r.address != "127.0.0.53" for r in found)


def test_linux_falls_back_to_resolv_conf_without_resolvectl():
    _, run, read = fakes("", fixture("resolv_conf_plain.txt"))
    found = get_configured_resolvers("linux", run, read)
    assert [r.address for r in found] == ["192.168.1.1", "2001:4860:4860::8888"]


def test_nothing_readable_gives_empty_list():
    _, run, read = fakes()
    assert get_configured_resolvers("linux", run, read) == []
    assert get_configured_resolvers("darwin", run, read) == []
