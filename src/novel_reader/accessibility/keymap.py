"""
Keyboard navigation mappings and command definitions.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, Optional


@dataclass
class Command:
    """A user command with description and shortcut key."""
    key: str
    name: str
    description: str


DEFAULT_KEYMAP: Dict[str, Command] = {
    "n": Command(key="n", name="Next Chapter", description="Advance to the next chapter"),
    "p": Command(key="p", name="Previous Chapter", description="Return to the previous chapter"),
    "j": Command(key="j", name="Next Paragraph", description="Read the next paragraph"),
    "k": Command(key="k", name="Previous Paragraph", description="Read the previous paragraph"),
    "r": Command(key="r", name="Repeat Paragraph", description="Repeat the current paragraph"),
    "b": Command(key="b", name="Add Bookmark", description="Save a bookmark at the current position"),
    "l": Command(key="l", name="List Bookmarks", description="View saved bookmarks for this book"),
    "g": Command(key="g", name="Go to Chapter", description="Jump directly to a chapter number"),
    "t": Command(key="t", name="Table of Contents", description="List all chapters in the book"),
    "i": Command(key="i", name="Book Information", description="Read current progress and book details"),
    "?": Command(key="?", name="Help", description="Display available keyboard shortcuts"),
    "q": Command(key="q", name="Quit", description="Save progress and exit reader"),
}


def get_command_for_key(key: str) -> Optional[Command]:
    """Resolve a key stroke to a command."""
    return DEFAULT_KEYMAP.get(key.lower().strip())
