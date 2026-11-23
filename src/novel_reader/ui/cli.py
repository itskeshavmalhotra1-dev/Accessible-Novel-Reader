"""
Accessible interactive command-line reader interface.
Designed specifically for screen reader users and keyboard navigation.
"""

from __future__ import annotations

import sys
from typing import List

from novel_reader.accessibility.announcer import BaseAnnouncer, get_default_announcer
from novel_reader.accessibility.keymap import DEFAULT_KEYMAP, get_command_for_key
from novel_reader.core.models import Book, Bookmark, Chapter, ReadingProgress
from novel_reader.library.manager import LibraryManager
from novel_reader.utils.text import split_into_paragraphs


class ReaderSession:
    """Active reading session managing navigation, speech, and progress tracking."""

    def __init__(
        self,
        book: Book,
        progress: ReadingProgress,
        library_manager: LibraryManager,
        announcer: BaseAnnouncer | None = None,
    ) -> None:
        self.book = book
        self.progress = progress
        self.library_manager = library_manager
        self.announcer = announcer or get_default_announcer()
        self.paragraphs: List[str] = []
        self._load_current_chapter()

    def _load_current_chapter(self) -> None:
        ch = self.book.get_chapter(self.progress.current_chapter_index)
        if ch:
            self.paragraphs = split_into_paragraphs(ch.content)
            if self.progress.current_paragraph_index >= len(self.paragraphs):
                self.progress.current_paragraph_index = 0
        else:
            self.paragraphs = []

    def get_current_chapter(self) -> Chapter | None:
        return self.book.get_chapter(self.progress.current_chapter_index)

    def get_current_paragraph(self) -> str:
        if 0 <= self.progress.current_paragraph_index < len(self.paragraphs):
            return self.paragraphs[self.progress.current_paragraph_index]
        return ""

    def read_current(self) -> None:
        ch = self.get_current_chapter()
        title = ch.title if ch else "Unknown Chapter"
        p = self.get_current_paragraph()
        if p:
            self.announcer.speak(p)
        else:
            self.announcer.speak(f"Chapter {self.progress.current_chapter_index + 1}: {title}. End of chapter.")

    def next_paragraph(self) -> None:
        if self.progress.current_paragraph_index + 1 < len(self.paragraphs):
            self.progress.current_paragraph_index += 1
            self._save()
            self.read_current()
        else:
            # Advance to next chapter
            self.next_chapter()

    def previous_paragraph(self) -> None:
        if self.progress.current_paragraph_index > 0:
            self.progress.current_paragraph_index -= 1
            self._save()
            self.read_current()
        elif self.progress.current_chapter_index > 0:
            self.previous_chapter(to_end=True)
        else:
            self.announcer.speak("Beginning of book.")

    def next_chapter(self) -> None:
        if self.progress.current_chapter_index + 1 < self.book.total_chapters:
            self.progress.current_chapter_index += 1
            self.progress.current_paragraph_index = 0
            self._load_current_chapter()
            self._save()
            ch = self.get_current_chapter()
            title = ch.title if ch else ""
            self.announcer.speak(f"Chapter {self.progress.current_chapter_index + 1}: {title}")
            self.read_current()
        else:
            self.announcer.speak("End of book.")

    def previous_chapter(self, to_end: bool = False) -> None:
        if self.progress.current_chapter_index > 0:
            self.progress.current_chapter_index -= 1
            self._load_current_chapter()
            if to_end and self.paragraphs:
                self.progress.current_paragraph_index = len(self.paragraphs) - 1
            else:
                self.progress.current_paragraph_index = 0
            self._save()
            ch = self.get_current_chapter()
            title = ch.title if ch else ""
            self.announcer.speak(f"Chapter {self.progress.current_chapter_index + 1}: {title}")
            self.read_current()
        else:
            self.announcer.speak("Already at first chapter.")

    def go_to_chapter(self, chapter_num: int) -> bool:
        idx = chapter_num - 1
        if 0 <= idx < self.book.total_chapters:
            self.progress.current_chapter_index = idx
            self.progress.current_paragraph_index = 0
            self._load_current_chapter()
            self._save()
            ch = self.get_current_chapter()
            title = ch.title if ch else ""
            self.announcer.speak(f"Jumped to chapter {chapter_num}: {title}")
            self.read_current()
            return True
        self.announcer.speak(f"Invalid chapter number. Book has {self.book.total_chapters} chapters.")
        return False

    def add_bookmark(self, label: str = "") -> None:
        p = self.get_current_paragraph()
        snippet = (p[:80] + "...") if len(p) > 80 else p
        bm = Bookmark(
            book_id=self.book.id,
            chapter_index=self.progress.current_chapter_index,
            paragraph_index=self.progress.current_paragraph_index,
            label=label or f"Bookmark {datetime_now_str()}",
            snippet=snippet,
        )
        self.library_manager.add_bookmark(bm)
        self.announcer.speak(f"Bookmark added at chapter {self.progress.current_chapter_index + 1}, paragraph {self.progress.current_paragraph_index + 1}")

    def list_bookmarks(self) -> None:
        bookmarks = self.library_manager.get_bookmarks(self.book.id)
        if not bookmarks:
            self.announcer.speak("No bookmarks saved for this book.")
            return

        lines = [f"{len(bookmarks)} bookmarks found:"]
        for idx, bm in enumerate(bookmarks, start=1):
            lines.append(f"{idx}. Chapter {bm.chapter_index + 1}, Paragraph {bm.paragraph_index + 1}: {bm.snippet}")
        self.announcer.speak("\n".join(lines))

    def show_info(self) -> None:
        pct = (
            (self.progress.current_chapter_index / max(1, self.book.total_chapters)) * 100.0
        )
        info = (
            f"Title: {self.book.metadata.title}\n"
            f"Author: {self.book.metadata.author}\n"
            f"Current Chapter: {self.progress.current_chapter_index + 1} of {self.book.total_chapters}\n"
            f"Current Paragraph: {self.progress.current_paragraph_index + 1} of {len(self.paragraphs)}\n"
            f"Progress: {pct:.1f}%"
        )
        self.announcer.speak(info)

    def show_toc(self) -> None:
        lines = [f"Table of Contents ({self.book.total_chapters} chapters):"]
        for ch in self.book.chapters:
            marker = "*" if ch.index == self.progress.current_chapter_index else " "
            lines.append(f"{marker} {ch.index + 1}. {ch.title}")
        self.announcer.speak("\n".join(lines))

    def _save(self) -> None:
        if self.book.total_chapters > 0:
            self.progress.percentage = (
                (self.progress.current_chapter_index / self.book.total_chapters) * 100.0
            )
        self.library_manager.save_progress(self.progress)


def datetime_now_str() -> str:
    from datetime import datetime
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def run_interactive_session(session: ReaderSession) -> None:
    """Run interactive keyboard event loop."""
    session.show_info()
    session.read_current()

    while True:
        try:
            line = input("\n[n:next p:prev j:down k:up r:repeat b:mark t:toc i:info ?:help q:quit] > ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            session._save()
            print("\nProgress saved. Exiting.")
            break

        if not line:
            # Default action on empty Enter: advance to next paragraph
            session.next_paragraph()
            continue

        cmd = get_command_for_key(line[0])
        if not cmd:
            print(f"Unknown command: '{line}'. Press '?' for help.")
            continue

        if cmd.key == "q":
            session._save()
            print("Reading progress saved. Goodbye.")
            break
        elif cmd.key == "n":
            session.next_chapter()
        elif cmd.key == "p":
            session.previous_chapter()
        elif cmd.key == "j":
            session.next_paragraph()
        elif cmd.key == "k":
            session.previous_paragraph()
        elif cmd.key == "r":
            session.read_current()
        elif cmd.key == "b":
            session.add_bookmark()
        elif cmd.key == "l":
            session.list_bookmarks()
        elif cmd.key == "t":
            session.show_toc()
        elif cmd.key == "i":
            session.show_info()
        elif cmd.key == "g":
            try:
                num = int(input("Enter chapter number: ").strip())
                session.go_to_chapter(num)
            except ValueError:
                print("Invalid number.")
        elif cmd.key == "?":
            print("\nAvailable Keyboard Shortcuts:")
            for c in DEFAULT_KEYMAP.values():
                print(f"  {c.key:<3} - {c.name:<18} : {c.description}")
