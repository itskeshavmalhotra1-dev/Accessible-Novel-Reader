"""
Universal Accessibility & Screen Reader Bridge.
Zero-Emoji, Zero-Chatter compliant TTS announcements and acoustic earcons.
Uses accessible-output2 (NVDA, JAWS) and crisp winsound earcons.
"""

from __future__ import annotations

import sys
import threading
from typing import Optional

from novel_reader.utils.text import sanitize_speech_text

# Initialize accessible-output2
try:
    if "pytest" in sys.modules:
        _SPEECH_ENGINE = None
    else:
        import accessible_output2.outputs.auto
        _SPEECH_ENGINE = accessible_output2.outputs.auto.Auto()
except Exception:
    _SPEECH_ENGINE = None

# Winsound for acoustic earcons on Windows
if sys.platform == "win32":
    try:
        import winsound
    except ImportError:
        winsound = None
else:
    winsound = None


class ScreenReaderAnnouncer:
    """Screen reader announcer with acoustic feedback earcons."""

    def __init__(self) -> None:
        self._speech = _SPEECH_ENGINE
        self._sound_enabled = False

    def speak(self, text: str, interrupt: bool = True) -> None:
        """
        Announce text to the active screen reader (NVDA, JAWS, Narrator).
        Avoids unsolicited SAPI chatter over active screen readers.
        """
        if not text:
            return

        cleaned = sanitize_speech_text(text, remove_emojis=True)
        if not cleaned:
            return

        # Emit to stdout for CLI / test debugging
        sys.stdout.write(f"\n[Announcement] {cleaned}\n")
        sys.stdout.flush()

        if self._speech:
            def _async_output() -> None:
                try:
                    self._speech.output(cleaned, interrupt=interrupt)
                except Exception:
                    pass

            threading.Thread(target=_async_output, daemon=True).start()

    def stop(self) -> None:
        """Stop current speech output."""
        if self._speech:
            try:
                self._speech.output("", interrupt=True)
            except Exception:
                pass

    def play_earcon(self, event_type: str) -> None:
        """
        Acoustic feedback earcons. Silenced by default for a quiet, non-disruptive
        screen reader experience.
        """
        if not self._sound_enabled or not winsound:
            return

        def _beep_worker() -> None:
            try:
                if event_type == "start":
                    winsound.Beep(650, 60)
                    winsound.Beep(850, 70)
                elif event_type == "complete":
                    winsound.Beep(850, 70)
                    winsound.Beep(1200, 90)
                elif event_type == "error":
                    winsound.Beep(320, 180)
                elif event_type == "click":
                    winsound.Beep(1000, 30)
                elif event_type == "change":
                    winsound.Beep(750, 45)
            except Exception:
                pass

        threading.Thread(target=_beep_worker, daemon=True).start()


_announcer = ScreenReaderAnnouncer()
BaseAnnouncer = ScreenReaderAnnouncer
ConsoleAnnouncer = ScreenReaderAnnouncer
WindowsSapiAnnouncer = ScreenReaderAnnouncer


def get_default_announcer() -> ScreenReaderAnnouncer:
    return _announcer
