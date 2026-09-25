"""Lightweight self-updater.

Polls a version manifest (version.json in the repo) once at startup in the
background. If the remote version is newer than the running one, the UI offers
a REAL update: on the Windows EXE build it downloads the new bundle and swaps
it in place (with a detached helper that waits for this process to exit), so
the app genuinely updates instead of just opening a download page. Pure
standard library; any network failure is silent.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import urllib.request
import webbrowser

from . import __version__

MANIFEST_URL = ("https://raw.githubusercontent.com/"
                "mohammedahakimmk-beep/roadmind/main/version.json")

RELEASE_URL = "https://github.com/mohammedahakimmk-beep/roadmind/releases"


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


def download_and_apply(url: str, timeout: float = 600.0):
    """Download a new build and swap it in so the app ACTUALLY updates.

    This only works on the frozen Windows EXE (PyInstaller): the new EXE is
    downloaded next to the running one, then a detached `cmd` helper waits for
    this process to exit, force-stops the old instance, replaces the file and
    relaunches the new build. On dev/macOS builds we can't self-replace, so we
    return (False, message) and the caller falls back to the release page.

    Returns (ok: bool, message: str).
    """
    if not (getattr(sys, "frozen", False) and sys.platform == "win32"):
        return (False, "Self-update is built for the Windows EXE \u2014 "
                       "opening the download page instead.")
    if not url:
        return (False, "No download URL available.")

    current = os.path.abspath(sys.executable)
    staging = current + ".new"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            with open(staging, "wb") as f:
                while True:
                    chunk = r.read(256 * 1024)
                    if not chunk:
                        break
                    f.write(chunk)
        if os.path.getsize(staging) <= 0:
            raise IOError("staged file is empty")
        with open(staging, "rb") as f:
            if f.read(2) != b"MZ":
                raise IOError("not a Windows EXE")
    except Exception as e:
        if os.path.exists(staging):
            try:
                os.remove(staging)
            except Exception:
                pass
        return (False, f"Update download failed: {e}")

    title = os.path.basename(current)
    cmd = (f'ping -n 3 127.0.0.1 >nul & '
           f'taskkill /im "{title}" /f >nul 2>&1 & '
           f'move /y "{staging}" "{current}" >nul & '
           f'start "" "{current}"')
    start_info = None
    if hasattr(subprocess, "STARTUPINFO"):
        start_info = subprocess.STARTUPINFO()
        start_info.dwFlags |= getattr(subprocess, "STARTF_USESHOWWINDOW", 0x1)
    flags = getattr(subprocess, "DETACHED_PROCESS", 0x8) \
        | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x200)
    try:
        subprocess.Popen(["cmd", "/c", cmd], creationflags=flags,
                         startupinfo=start_info,
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, close_fds=True)
    except Exception as e:
        return (False, f"Could not start the updater: {e}")
    return (True, "Update downloaded \u2014 GameROBOT restarts with the new "
                  "version in a moment.")