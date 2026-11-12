"""Tests for the command-line interface."""

from importlib.metadata import version

from typer.testing import CliRunner

from vpnleakcheck.cli import app

runner = CliRunner()


def test_version_prints_name_and_version() -> None:
    result = runner.invoke(app, ["--version"])

    assert result.exit_code == 0
    assert result.output.strip() == f"vpnleakcheck {version('vpnleakcheck')}"


def test_version_exits_before_running_checks() -> None:
    result = runner.invoke(app, ["--version"])

    assert "not implemented" not in result.output


def test_help_lists_the_version_option() -> None:
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "--version" in result.output
