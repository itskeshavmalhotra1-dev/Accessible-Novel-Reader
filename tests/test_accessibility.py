"""
Tests for accessibility announcer, speech sanitization, and keymap.
"""

from io import StringIO
import sys

from novel_reader.accessibility.announcer import ConsoleAnnouncer
from novel_reader.accessibility.keymap import DEFAULT_KEYMAP, get_command_for_key


def test_console_announcer_zero_emoji(monkeypatch) -> None:
    captured = StringIO()
    monkeypatch.setattr(sys, "stdout", captured)

    announcer = ConsoleAnnouncer()
    announcer.speak("Chapter 1: The Beginning 📖🚀")

    output = captured.getvalue().strip()
    assert "Chapter 1: The Beginning" in output
    assert "📖" not in output
    assert "🚀" not in output


def test_keymap_lookup() -> None:
    assert get_command_for_key("n") is not None
    assert get_command_for_key("N") is not None
    assert get_command_for_key("n").name == "Next Chapter"
    assert get_command_for_key("q").name == "Quit"
    assert get_command_for_key("z") is None
