"""Lightweight self-update checker.

Polls a version manifest (version.json in the repo) once at startup in the
background. If the remote version is newer than the running one, the UI shows
"Update available" pointing at the GitHub release asset (the DMG). Pure
standard library; any network failure is silent.
"""

from __future__ import annotations

import json
import sys
import threading
import urllib.request
import webbrowser

from . import __version__

MANIFEST_URL = ("https://raw.githubusercontent.com/"
                "mohammedahakimmk-beep/roadmind/main/version.json")


def _parse(v: str) -> tuple:
    parts = []
    for x in v.strip().lstrip("v").split("."):
        if x.isdigit():
            parts.append(int(x))
    return tuple(parts)


def is_newer(candidate: str, current: str) -> bool:
    if not candidate.strip():
        return False
    try:
        return _parse(candidate) > _parse(current)
    except Exception:
        return False


def check_once(timeout: float = 6.0):
    """Blocking manifest check. Returns (latest, url, notes, newer_exists: bool).

    Fails silent on any network error so the app never hangs on launch.
    """
    try:
        with urllib.request.urlopen(MANIFEST_URL, timeout=timeout) as r:
            data = json.load(r)
    except Exception:
        return (__version__, "", "", False)
    latest = str(data.get("version", ""))
    url = str(data.get("url", ""))
    notes = str(data.get("notes", ""))
    # Windows builds download the EXE directly; macOS shows the release page
    # (where it now reads the official deprecation notice).
    if sys.platform == "win32":
        url = str(data.get("exe_url") or url) or url
    return (latest, url, notes, is_newer(latest, __version__))


class Updater:
    """Checks for a newer release. Calls on_result(version, url, notes)."""

    def __init__(self, on_result=None, manifest_url: str = MANIFEST_URL):
        self.on_result = on_result or (lambda *a: None)
        self.manifest_url = manifest_url

    def poll(self) -> bool:
        threading.Thread(target=self._check, daemon=True).start()
        return True

    def _check(self):
        latest, url, notes, newer = check_once()
        if newer:
            self.on_result(latest, url, notes)


def open_release(url: str):
    if url:
        webbrowser.open(url)