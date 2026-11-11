"""Command-line interface: the Typer app behind the `vpnleakcheck` command."""

from importlib.metadata import version
from typing import Annotated

import typer

app = typer.Typer(add_completion=False)


def _print_version(value: bool) -> None:
    """Print the installed version and exit, if --version was given."""
    if value:
        typer.echo(f"vpnleakcheck {version('vpnleakcheck')}")
        raise typer.Exit()


@app.callback(invoke_without_command=True)
def main(
    show_version: Annotated[
        bool,
        typer.Option(
            "--version",
            callback=_print_version,
            is_eager=True,
            help="Show the version and exit.",
        ),
    ] = False,
) -> None:
    """Check whether your VPN is protecting you on the current network."""
    typer.echo("vpnleakcheck: checks are not implemented yet")
