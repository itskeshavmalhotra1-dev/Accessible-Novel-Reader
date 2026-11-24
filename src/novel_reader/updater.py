"""
Auto-Updater module for Accessible Novel Reader.
Checks GitHub Releases for updates, displays changelog in an accessible dialog,
and automatically downloads and applies updates for source and standalone installations.
"""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from typing import Any, Callable, Dict, Optional, Tuple
import zipfile

import requests

from novel_reader.accessibility.announcer import get_default_announcer

CURRENT_VERSION = "26.0.2"
DEFAULT_GITHUB_REPO = os.environ.get("NOVEL_READER_REPO", "itskeshavmalhotra1-dev/Accessible-Novel-Reader")
USER_AGENT = f"AccessibleNovelReader-Updater/{CURRENT_VERSION}"

logger = logging.getLogger(__name__)


def parse_version(ver_str: str) -> Tuple[int, int, int]:
    """Parse version strings like 'v1.0.1' or '1.0.0' into a comparable 3-tuple of ints."""
    if not ver_str:
        return (0, 0, 0)
    clean = re.sub(r"^[^\d]*", "", ver_str.strip())
    parts = []
    for p in clean.split("."):
        m = re.match(r"(\d+)", p)
        if m:
            parts.append(int(m.group(1)))
        else:
            parts.append(0)
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts[:3])  # type: ignore


def is_standalone_executable() -> bool:
    """Check whether the application is running as a packaged executable."""
    return getattr(sys, "frozen", False) or hasattr(sys, "__compiled__") or "novel_reader.exe" in sys.executable.lower()


def get_install_paths() -> Dict[str, Any]:
    """Detect installation mode, root directory, and git repository presence."""
    if is_standalone_executable():
        exe_dir = os.path.dirname(os.path.abspath(sys.executable))
        if os.path.basename(exe_dir).lower() == "bin":
            install_dir = os.path.dirname(exe_dir)
        else:
            install_dir = exe_dir
        return {
            "mode": "standalone",
            "install_dir": install_dir,
            "exe_name": os.path.basename(sys.executable),
        }
    else:
        src_dir = os.path.dirname(os.path.abspath(__file__))
        # If in src/novel_reader, root is 2 levels up
        parent = os.path.dirname(src_dir)
        root_dir = os.path.dirname(parent) if os.path.basename(parent) == "src" else parent
        has_git = os.path.exists(os.path.join(root_dir, ".git"))
        return {
            "mode": "source",
            "install_dir": root_dir,
            "has_git": has_git,
            "main_script": os.path.join(root_dir, "main.py"),
        }


def check_for_updates(
    current_version: str = CURRENT_VERSION,
    repo: str = DEFAULT_GITHUB_REPO,
) -> Optional[Dict[str, Any]]:
    """
    Query GitHub API for the latest release.
    Returns release info dictionary if a newer version exists, else None.
    """
    url = f"https://api.github.com/repos/{repo}/releases/latest"
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/vnd.github.v3+json",
    }
    try:
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code in (404, 403):
            logger.info("GitHub release check returned status %d for %s", r.status_code, repo)
            return None
        r.raise_for_status()
        data = r.json()
        remote_tag = data.get("tag_name", "")
        remote_ver = parse_version(remote_tag)
        local_ver = parse_version(current_version)

        if remote_ver > local_ver:
            assets = data.get("assets", [])
            zip_asset = None
            for a in assets:
                name = a.get("name", "").lower()
                if name.endswith(".zip"):
                    zip_asset = a
                    break

            return {
                "update_available": True,
                "current_version": current_version,
                "latest_version": remote_tag,
                "release_name": data.get("name") or remote_tag,
                "published_at": (data.get("published_at") or "")[:10],
                "changelog": data.get("body", "No release notes provided."),
                "html_url": data.get("html_url", f"https://github.com/{repo}/releases"),
                "download_url": zip_asset.get("browser_download_url") if zip_asset else None,
                "download_size": zip_asset.get("size", 0) if zip_asset else 0,
                "asset_name": zip_asset.get("name") if zip_asset else None,
            }
        return None
    except Exception as e:
        logger.warning("Update check failed: %s", e)
        return None


def download_file(
    url: str,
    dest_path: str,
    progress_callback: Optional[Callable[[int, int, int], None]] = None,
) -> str:
    """Download a file with streaming progress updates."""
    headers = {"User-Agent": USER_AGENT}
    resp = requests.get(url, headers=headers, stream=True, timeout=30)
    resp.raise_for_status()
    total_size = int(resp.headers.get("content-length", 0))
    downloaded = 0

    with open(dest_path, "wb") as f:
        for chunk in resp.iter_content(chunk_size=65536):
            if chunk:
                f.write(chunk)
                downloaded += len(chunk)
                if progress_callback:
                    pct = int(downloaded / total_size * 100) if total_size > 0 else 0
                    progress_callback(downloaded, total_size, pct)
    return dest_path


def apply_update(
    zip_path: Optional[str] = None,
    status_callback: Optional[Callable[[str], None]] = None,
) -> None:
    """
    Apply downloaded update and restart the software.
    Supports both Git Source repository hot-pull and Standalone binary hot-swap.
    """
    paths = get_install_paths()

    # Case 1: Running from Source repository with Git tracking
    if paths["mode"] == "source" and paths.get("has_git"):
        if status_callback:
            status_callback("Syncing latest updates from GitHub repository...")
        try:
            cmd = ["git", "pull", "origin", "main"]
            res = subprocess.run(
                cmd,
                cwd=paths["install_dir"],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if res.returncode == 0:
                if status_callback:
                    status_callback("Update applied successfully! Restarting...")
                time.sleep(1)
                subprocess.Popen(
                    [sys.executable, "main.py"],
                    cwd=paths["install_dir"],
                    creationflags=0x08000000 if sys.platform == "win32" else 0,
                )
                time.sleep(0.5)
                os._exit(0)
        except Exception as e:
            logger.error("Git pull update error: %s", e)

    # Case 2: Standalone binary or offline zip package
    if not zip_path or not os.path.exists(zip_path):
        raise FileNotFoundError("Update zip package not found.")

    if status_callback:
        status_callback("Extracting update package...")

    temp_extract = os.path.join(tempfile.gettempdir(), f"nr_update_{os.getpid()}")
    os.makedirs(temp_extract, exist_ok=True)

    with zipfile.ZipFile(zip_path, "r") as z:
        z.extractall(temp_extract)

    subdirs = [
        os.path.join(temp_extract, d)
        for d in os.listdir(temp_extract)
        if os.path.isdir(os.path.join(temp_extract, d))
    ]
    src_folder = temp_extract
    if len(subdirs) == 1:
        sub = subdirs[0]
        if (
            os.path.exists(os.path.join(sub, "main.py"))
            or os.path.exists(os.path.join(sub, "Accessible_Novel_Reader.exe"))
            or os.path.exists(os.path.join(sub, "bin"))
        ):
            src_folder = sub

    target_dir = paths["install_dir"]
    if paths.get("mode") == "standalone":
        launcher_exe = os.path.join(target_dir, "Accessible_Novel_Reader.exe")
        if not os.path.exists(launcher_exe):
            launcher_exe = os.path.join(target_dir, paths.get("exe_name", "Accessible_Novel_Reader.exe"))
        restart_cmd = f'start "" "{launcher_exe}"'
    else:
        restart_cmd = 'start "" pythonw main.py'
    restart_dir = paths["install_dir"]

    bat_path = os.path.join(tempfile.gettempdir(), "apply_novel_reader_update.bat")
    bat_content = f"""@echo off
timeout /t 1 /nobreak > nul
echo Updating Accessible Novel Reader...
xcopy "{src_folder}\\*" "{target_dir}\\" /s /e /y /q > nul
rd /s /q "{temp_extract}" > nul 2>&1
del "{zip_path}" > nul 2>&1
echo Launching updated application...
cd /d "{restart_dir}"
{restart_cmd}
del "%~f0" > nul 2>&1
exit
"""
    with open(bat_path, "w", encoding="ascii") as f:
        f.write(bat_content)

    if status_callback:
        status_callback("Restarting with updated version...")

    subprocess.Popen(["cmd.exe", "/c", bat_path], creationflags=0x08000000)
    time.sleep(0.5)
    os._exit(0)


# Optional wxPython GUI Dialog for accessible update notifications
try:
    import wx

    WX_AVAILABLE = True
except ImportError:
    WX_AVAILABLE = False

if WX_AVAILABLE:

    class UpdateDialog(wx.Dialog):
        """Accessible update dialog presenting release notes and 1-click update."""

        def __init__(self, parent: Optional[wx.Window], update_info: Dict[str, Any]) -> None:
            super().__init__(
                parent,
                title="Software Update Available",
                size=(580, 440),
                style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
            )
            self.update_info = update_info
            self.announcer = get_default_announcer()
            self.download_thread: Optional[threading.Thread] = None
            self.is_downloading = False

            panel = wx.Panel(self)
            main_sizer = wx.BoxSizer(wx.VERTICAL)

            # Header Info
            cur_ver = update_info.get("current_version", CURRENT_VERSION)
            new_ver = update_info.get("latest_version", "New Version")
            pub_date = update_info.get("published_at", "")
            sz_mb = update_info.get("download_size", 0) / (1024 * 1024)

            header_text = (
                f"A new version of Accessible Novel Reader is available!\r\n\r\n"
                f"- Installed Version: v{cur_ver}\r\n"
                f"- Latest Release: {new_ver} ({pub_date})\r\n"
                f"- Download Size: {sz_mb:.1f} MB"
            )
            self.lbl_header = wx.StaticText(panel, label=header_text)
            self.lbl_header.SetName("Update Release Information")
            main_sizer.Add(self.lbl_header, 0, wx.ALL | wx.EXPAND, 12)

            # Release Notes / Changelog
            lbl_notes = wx.StaticText(panel, label="What's New in this Release (Changelog):")
            main_sizer.Add(lbl_notes, 0, wx.LEFT | wx.RIGHT, 12)

            raw_notes = update_info.get("changelog", "No release notes provided.")
            crlf_notes = raw_notes.replace("\r\n", "\n").replace("\r", "\n").replace("\n", "\r\n")

            self.txt_changelog = wx.TextCtrl(
                panel,
                value=crlf_notes,
                style=wx.TE_MULTILINE | wx.TE_READONLY,
            )
            self.txt_changelog.SetName("Release Notes Changelog (Read line by line with Up and Down arrow keys)")
            main_sizer.Add(self.txt_changelog, 1, wx.ALL | wx.EXPAND, 12)

            # Progress Gauge
            self.gauge = wx.Gauge(panel, range=100, size=(-1, 20))
            self.gauge.SetName("Update Download Progress")
            self.gauge.Hide()
            main_sizer.Add(self.gauge, 0, wx.LEFT | wx.RIGHT | wx.EXPAND, 12)

            self.lbl_status = wx.StaticText(
                panel,
                label="Read the changelog above. Press 'Update Now' to apply this update.",
            )
            self.lbl_status.SetName("Update Status")
            main_sizer.Add(self.lbl_status, 0, wx.ALL | wx.EXPAND, 12)

            # Action Buttons
            btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
            self.btn_update = wx.Button(panel, label="Update Now (Alt+U)")
            self.btn_update.SetName("Update Now (Alt+U)")
            self.btn_update.Bind(wx.EVT_BUTTON, self.on_start_update)
            btn_sizer.Add(self.btn_update, 0, wx.RIGHT, 8)

            self.btn_later = wx.Button(panel, wx.ID_CANCEL, label="Later (Esc)")
            self.btn_later.SetName("Later (Close)")
            btn_sizer.Add(self.btn_later, 0)

            main_sizer.Add(btn_sizer, 0, wx.ALIGN_RIGHT | wx.BOTTOM | wx.RIGHT, 12)

            panel.SetSizer(main_sizer)
            self.CenterOnParent()

            # Place focus on Changelog text control so screen reader announces and reads it immediately
            self.txt_changelog.SetInsertionPoint(0)
            self.txt_changelog.SetFocus()

            self.announcer.speak(
                f"Update {new_ver} available! Changelog is open. Use Up and Down arrow keys to read what is new, then press Tab to Update Now or Later."
            )

        def on_start_update(self, event: wx.Event) -> None:
            if self.is_downloading:
                return

            self.is_downloading = True
            self.btn_update.Enable(False)
            self.btn_later.SetLabel("Cancel")
            self.gauge.Show()
            self.gauge.SetValue(0)
            self.Layout()

            paths = get_install_paths()

            # If in source mode with git, fast git pull
            if paths["mode"] == "source" and paths.get("has_git"):
                msg = "Updating source files directly from GitHub..."
                self.lbl_status.SetLabel(msg)
                self.announcer.speak(msg)

                def _bg_git_update() -> None:
                    try:
                        apply_update(
                            status_callback=lambda s: wx.CallAfter(self._update_status, s)
                        )
                    except Exception as e:
                        wx.CallAfter(self._on_update_failed, str(e))

                self.download_thread = threading.Thread(target=_bg_git_update, daemon=True)
                self.download_thread.start()
                return

            # Otherwise, download standalone zip package
            download_url = self.update_info.get("download_url")
            if not download_url:
                msg = "No zip package URL found in this release. Opening release page."
                self.lbl_status.SetLabel(msg)
                self.announcer.speak(msg)
                import webbrowser
                webbrowser.open(self.update_info.get("html_url", ""))
                self.btn_update.Enable(True)
                self.is_downloading = False
                return

            msg = "Connecting to GitHub to download update..."
            self.lbl_status.SetLabel(msg)
            self.announcer.speak(msg)

            def _bg_download() -> None:
                temp_zip = os.path.join(tempfile.gettempdir(), f"nr_latest_{os.getpid()}.zip")
                try:
                    def _prog(cur: int, total: int, pct: int) -> None:
                        cur_mb = cur / (1024 * 1024)
                        tot_mb = total / (1024 * 1024)
                        wx.CallAfter(self.gauge.SetValue, pct)
                        wx.CallAfter(
                            self.lbl_status.SetLabel,
                            f"Downloading: {cur_mb:.1f} MB of {tot_mb:.1f} MB ({pct}%)...",
                        )

                    download_file(download_url, temp_zip, progress_callback=_prog)
                    wx.CallAfter(
                        self._update_status,
                        "Download complete! Applying update and restarting...",
                    )
                    apply_update(
                        temp_zip,
                        status_callback=lambda s: wx.CallAfter(self._update_status, s),
                    )
                except Exception as e:
                    wx.CallAfter(self._on_update_failed, str(e))

            self.download_thread = threading.Thread(target=_bg_download, daemon=True)
            self.download_thread.start()

        def _update_status(self, text: str) -> None:
            self.lbl_status.SetLabel(text)
            self.announcer.speak(text)

        def _on_update_failed(self, error: str) -> None:
            self.lbl_status.SetLabel(f"Update failed: {error}")
            self.announcer.speak(f"Update failed: {error}")
            self.btn_update.Enable(True)
            self.is_downloading = False
