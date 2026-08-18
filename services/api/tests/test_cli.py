from typer.testing import CliRunner

from invoicepilot import __version__
from invoicepilot.cli import cli

runner = CliRunner()


def test_version() -> None:
    result = runner.invoke(cli, ["version"])
    assert result.exit_code == 0
    assert __version__ in result.stdout


def test_help_lists_commands() -> None:
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "config" in result.stdout
