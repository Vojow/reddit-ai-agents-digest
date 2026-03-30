from __future__ import annotations

import plistlib
from pathlib import Path


def test_launchd_daily_plist_has_expected_schedule_and_paths() -> None:
    plist_path = Path("ops/launchd/com.vojow.reddit-ai-agents-digest.daily.plist")
    assert plist_path.exists()

    payload = plistlib.loads(plist_path.read_bytes())

    assert payload["Label"] == "com.vojow.reddit-ai-agents-digest.daily"
    assert payload["ProgramArguments"] == [
        "/bin/bash",
        "/Users/wojciechwieczorek/Sii/reddit-ai-agents-digest/scripts/run_ai_launchd.sh",
    ]
    assert payload["WorkingDirectory"] == "/Users/wojciechwieczorek/Sii/reddit-ai-agents-digest"
    assert payload["RunAtLoad"] is False
    assert payload["StartCalendarInterval"] == {"Hour": 9, "Minute": 0}
    assert (
        payload["StandardOutPath"]
        == "/Users/wojciechwieczorek/Library/Logs/reddit-ai-agents-digest/daily.out.log"
    )
    assert (
        payload["StandardErrorPath"]
        == "/Users/wojciechwieczorek/Library/Logs/reddit-ai-agents-digest/daily.err.log"
    )
