from reddit_digest import __version__
from reddit_digest.cli import build_parser, main


def test_package_imports() -> None:
    assert __version__ == "0.1.0"
    assert build_parser().prog == "reddit-digest"
    assert "run-daily" in build_parser()._subparsers._group_actions[0].choices
    assert "preflight" in build_parser()._subparsers._group_actions[0].choices


def test_cli_main_returns_success() -> None:
    assert main([]) == 0
