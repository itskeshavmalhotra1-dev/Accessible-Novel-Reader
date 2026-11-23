"""
Accessibility and assistive technology interfaces.
"""

from novel_reader.accessibility.announcer import (
    BaseAnnouncer,
    ConsoleAnnouncer,
    WindowsSapiAnnouncer,
    get_default_announcer,
)
from novel_reader.accessibility.keymap import (
    DEFAULT_KEYMAP,
    Command,
    get_command_for_key,
)

__all__ = [
    "BaseAnnouncer",
    "ConsoleAnnouncer",
    "WindowsSapiAnnouncer",
    "get_default_announcer",
    "DEFAULT_KEYMAP",
    "Command",
    "get_command_for_key",
]
