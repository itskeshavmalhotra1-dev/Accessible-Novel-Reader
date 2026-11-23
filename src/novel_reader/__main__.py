"""
Main CLI entry point for Novel Reader.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

from novel_reader import __version__
from novel_reader.core.exceptions import NovelReaderError
from novel_reader.library.database import Database
from novel_reader.library.manager import LibraryManager
from novel_reader.sources.registry import default_sources
from novel_reader.ui.cli import ReaderSession, run_interactive_session
from novel_reader.ui.gui import launch_gui


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="novel-reader",
        description="A lightweight, accessible, high-performance novel reader designed for screen readers and keyboard efficiency.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    parser.add_argument(
        "--gui",
        action="store_true",
        help="Launch the accessible desktop GUI (default when no arguments provided)",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # Command: gui
    subparsers.add_parser("gui", help="Launch the accessible desktop GUI")

    # Command: search
    search_parser = subparsers.add_parser("search", help="Search online novels across sources")
    search_parser.add_argument("query", help="Novel name or keyword")
    search_parser.add_argument("--source", default=None, help="Specific source (e.g. FreeWebNovel, NovelFull)")

    # Command: open
    open_parser = subparsers.add_parser("open", help="Open and read a local book file (.txt, .md, .epub)")
    open_parser.add_argument("file", help="Path to book file to open")

    # Command: list
    subparsers.add_parser("list", help="List all books stored in your local library")

    # Command: resume
    resume_parser = subparsers.add_parser("resume", help="Resume reading a book by ID")
    resume_parser.add_argument("book_id", help="Book identifier")

    # Command: delete
    delete_parser = subparsers.add_parser("delete", help="Delete a book from the local library")
    delete_parser.add_argument("book_id", help="Book identifier")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    # Default to GUI when no command is specified or --gui is flagged
    if not args.command or args.gui or args.command == "gui":
        try:
            launch_gui()
            return 0
        except Exception as e:
            print(f"Error launching GUI: {e}", file=sys.stderr)
            return 1

    manager = LibraryManager()

    try:
        if args.command == "search":
            if args.source:
                src = default_sources.get_source(args.source)
                if not src:
                    print(f"Unknown source: '{args.source}'. Available: {default_sources.list_source_names()}")
                    return 1
                results = src.search(args.query)
            else:
                results = default_sources.search_all(args.query)

            if not results:
                print(f"No novels found matching '{args.query}'.")
                return 0

            print(f"Found {len(results)} novels:\n")
            for idx, n in enumerate(results, start=1):
                print(f"{idx}. [{n.source_name}] {n.title}\n   URL: {n.url}\n")
            return 0

        elif args.command == "open":
            file_path = Path(args.file)
            if not file_path.exists():
                print(f"Error: File does not exist: {file_path}", file=sys.stderr)
                return 1

            print(f"Loading '{file_path.name}'...")
            book = manager.import_book(file_path)
            progress = manager.get_progress(book.id)
            session = ReaderSession(book, progress, manager)
            run_interactive_session(session)
            return 0

        elif args.command == "list":
            books = manager.list_books()
            if not books:
                print("Your library is currently empty. Open a book using 'novel-reader open <filename>'.")
                return 0

            print(f"Library ({len(books)} books):\n")
            for b in books:
                pct = b.get("percentage") or 0.0
                print(
                    f"ID: {b['id']}\n"
                    f"  Title: {b['title']}\n"
                    f"  Author: {b['author']}\n"
                    f"  Chapters: {b['total_chapters']} | Format: {b['source_format'].upper()} | Progress: {pct:.1f}%\n"
                )
            return 0

        elif args.command == "resume":
            book = manager.load_book(args.book_id)
            progress = manager.get_progress(book.id)
            session = ReaderSession(book, progress, manager)
            run_interactive_session(session)
            return 0

        elif args.command == "delete":
            deleted = manager.remove_book(args.book_id)
            if deleted:
                print(f"Book '{args.book_id}' successfully removed from library.")
            else:
                print(f"Book '{args.book_id}' not found in library.")
            return 0

    except NovelReaderError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
