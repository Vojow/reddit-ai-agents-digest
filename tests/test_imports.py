from reddit_digest import __version__
from reddit_digest.cli import build_parser, main


def test_package_imports() -> None:
    assert __version__ == "0.1.0"
    assert build_parser().prog == "reddit-digest"


def test_cli_main_returns_success() -> None:
    assert main() == 0
