"""
User interface modules (CLI and future accessible GUI).
"""

from novel_reader.ui.cli import ReaderSession, run_interactive_session
from novel_reader.ui.gui import NovelReaderFrame, launch_gui

__all__ = [
    "ReaderSession",
    "run_interactive_session",
    "NovelReaderFrame",
    "launch_gui",
]
