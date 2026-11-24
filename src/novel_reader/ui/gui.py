"""
Accessible wxPython Novel Reader GUI.
Engineered with first-class screen reader compatibility (NVDA, JAWS),
Explicit Accelerator Bindings (Zero-Unknowns), Deterministic Focus,
Acoustic Earcons, Independent Token Guards, and CRLF Line Normalization.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
import re
import threading
import time
from typing import Dict, List, Optional
import wx

from novel_reader.accessibility.announcer import get_default_announcer
from novel_reader.library.database import Database
from novel_reader.sources.base import (
    BaseNovelSource,
    CategoryItem,
    ChapterContent,
    ChapterItem,
    NovelItem,
)
from novel_reader.sources.registry import default_sources

# Logging setup
LOG_PATH = Path("novel_reader.log")
logging.basicConfig(
    filename=LOG_PATH,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)


def safe_call_after(func, *args, **kwargs) -> None:
    """Safely invoke wx.CallAfter only if wx.App is alive."""
    app = wx.GetApp()
    if app:
        try:
            wx.CallAfter(func, *args, **kwargs)
        except Exception:
            pass


# Standard Windows CRLF Welcome Text
WELCOME_TEXT = (
    "Welcome to Accessible Novel Reader.\r\n\r\n"
    "Essential Shortcuts:\r\n"
    "- PageDown: Next Page of novels\r\n"
    "- PageUp: Previous Page of novels\r\n"
    "- Ctrl+J: Jump to Chapter by number\r\n"
    "- Ctrl+B: Bookmark current chapter\r\n"
    "- Ctrl+U: Update bookmark to current chapter\r\n"
    "- Ctrl+L: Load saved bookmark to resume reading\r\n"
    "- Alt+N: Next Chapter\r\n"
    "- Alt+P: Previous Chapter\r\n"
    "- F5: Reload current source\r\n\r\n"
    "How to read:\r\n"
    "1. Use Tab / Shift+Tab to navigate between lists and controls.\r\n"
    "2. In Categories, press Enter to load novels for that category.\r\n"
    "3. In Novels, press Enter to load chapters. Use PageDown / PageUp to browse pages.\r\n"
    "4. In Chapters, press Enter to open a chapter (or press Ctrl+J to jump directly).\r\n"
    "5. In the Reading Section, use Up Arrow and Down Arrow to read line-by-line with NVDA.\r\n"
    "6. Press Alt+N to move to the next chapter anytime.\r\n"
    "7. Press Ctrl+B to bookmark your chapter, Ctrl+U to update it as you read, or Ctrl+L to resume anytime."
)

# Explicit Positive IDs for Accelerator Table (Essential Shortcuts Only)
ID_HOTKEY_RELOAD = 2001
ID_HOTKEY_PREV_PAGE = 2002
ID_HOTKEY_NEXT_PAGE = 2003
ID_HOTKEY_PREV_CHAPTER = 2004
ID_HOTKEY_NEXT_CHAPTER = 2005
ID_HOTKEY_JUMP_CHAPTER = 2006
ID_HOTKEY_BOOKMARK = 2007
ID_HOTKEY_UPDATE_BOOKMARK = 2008
ID_HOTKEY_LOAD_BOOKMARK = 2009


class BookmarkDialog(wx.Dialog):
    """Accessible dialog for selecting, loading, and managing novel bookmarks."""

    def __init__(self, parent: wx.Window, bookmarks: List[dict], db: Database) -> None:
        super().__init__(
            parent,
            title="Saved Bookmarks",
            size=(700, 430),
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )
        self.bookmarks = list(bookmarks)
        self.db = db
        self.selected_bookmark: Optional[dict] = None

        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)

        lbl = wx.StaticText(
            panel,
            label="Select a bookmark to resume reading (Use Up/Down arrows and press Enter):",
        )
        sizer.Add(lbl, 0, wx.ALL, 10)

        choices = self._format_choices()
        self.list_bookmarks = wx.ListBox(panel, choices=choices, style=wx.LB_SINGLE)
        self.list_bookmarks.SetName("Saved Bookmarks List")
        if choices:
            self.list_bookmarks.SetSelection(0)
        sizer.Add(self.list_bookmarks, 1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.btn_load = wx.Button(panel, wx.ID_OK, label="Load Bookmark (Enter)")
        self.btn_load.SetDefault()
        self.btn_load.SetName("Load Selected Bookmark")

        self.btn_delete = wx.Button(panel, label="Delete Bookmark (Alt+D)")
        self.btn_delete.SetName("Delete Selected Bookmark (Alt+D)")

        self.btn_cancel = wx.Button(panel, wx.ID_CANCEL, label="Close (Esc)")
        self.btn_cancel.SetName("Close Dialog (Esc)")

        btn_sizer.Add(self.btn_load, 0, wx.RIGHT, 8)
        btn_sizer.Add(self.btn_delete, 0, wx.RIGHT, 8)
        btn_sizer.Add(self.btn_cancel, 0)
        sizer.Add(btn_sizer, 0, wx.ALIGN_RIGHT | wx.RIGHT | wx.BOTTOM, 10)

        panel.SetSizer(sizer)

        self.list_bookmarks.Bind(wx.EVT_LISTBOX_DCLICK, self._on_load)
        self.list_bookmarks.Bind(wx.EVT_KEY_DOWN, self._on_key_down)
        self.btn_load.Bind(wx.EVT_BUTTON, self._on_load)
        self.btn_delete.Bind(wx.EVT_BUTTON, self._on_delete)

        self.CenterOnParent()

    def _format_choices(self) -> List[str]:
        items = []
        for bm in self.bookmarks:
            date_str = bm.get("updated_at", "")[:16]
            novel = bm.get("novel_title", "Novel")
            ch_idx = bm.get("chapter_index", 1)
            ch_tit = bm.get("chapter_title", "Chapter")
            src = bm.get("source_name", "")
            items.append(f"{novel} - Chapter {ch_idx}: {ch_tit} [{src}] ({date_str})")
        return items

    def _on_key_down(self, event: wx.KeyEvent) -> None:
        if event.GetKeyCode() in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
            self._on_load(None)
        elif event.GetKeyCode() == wx.WXK_DELETE:
            self._on_delete(None)
        else:
            event.Skip()

    def _on_load(self, event: Optional[wx.Event]) -> None:
        idx = self.list_bookmarks.GetSelection()
        if idx != wx.NOT_FOUND and idx < len(self.bookmarks):
            self.selected_bookmark = self.bookmarks[idx]
            self.EndModal(wx.ID_OK)

    def _on_delete(self, event: Optional[wx.Event]) -> None:
        idx = self.list_bookmarks.GetSelection()
        if idx == wx.NOT_FOUND or idx >= len(self.bookmarks):
            return

        bm = self.bookmarks[idx]
        bm_id = bm.get("id")
        if bm_id:
            self.db.delete_novel_bookmark(bm_id)

        del self.bookmarks[idx]
        choices = self._format_choices()
        self.list_bookmarks.Set(choices)
        if choices:
            new_idx = min(idx, len(choices) - 1)
            self.list_bookmarks.SetSelection(new_idx)
        else:
            self.EndModal(wx.ID_CANCEL)


class NovelReaderFrame(wx.Frame):
    """Accessible Main Window for browsing categories, novels, and reading chapters."""

    def __init__(self, parent: Optional[wx.Window] = None) -> None:
        super().__init__(
            parent,
            title="Accessible Novel Reader",
            size=(1160, 780),
        )

        self.sources = default_sources
        self.announcer = get_default_announcer()
        self.db = Database()

        # State
        self.categories: List[CategoryItem] = []
        self.novels: List[NovelItem] = []
        self.all_chapters: List[ChapterItem] = []
        self.chapters: List[ChapterItem] = []
        self.current_source: Optional[BaseNovelSource] = None
        self.current_category: Optional[CategoryItem] = None
        self.current_novel: Optional[NovelItem] = None
        self.current_chapter: Optional[ChapterItem] = None
        self.current_chapter_content: Optional[ChapterContent] = None
        self.current_page: int = 1
        self.search_mode: bool = False
        self.last_search_query: str = ""
        self.chapter_range_size: int = 100
        self.current_range_idx: int = 0
        self.chapter_sort_asc: bool = True

        # 0ms Memory Caches
        self._category_cache: Dict[str, List[CategoryItem]] = {}
        self._novel_cache: Dict[str, List[NovelItem]] = {}
        self._chapter_cache: Dict[str, List[ChapterItem]] = {}
        self._content_cache: Dict[str, ChapterContent] = {}

        # INDEPENDENT Token Guards per list to guarantee zero race conditions
        self._cat_token: int = 0
        self._novel_token: int = 0
        self._chap_token: int = 0
        self._content_token: int = 0
        self._loading_novel_url: Optional[str] = None

        self._init_ui()
        self._bind_events()
        self.Center()

        # Load initial source cleanly
        wx.CallAfter(self._load_initial_source)
        wx.CallAfter(self._start_background_update_check)

    def _init_ui(self) -> None:
        panel = wx.Panel(self)
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        # ---------------- 1. Top Bar: Source Selection & Search ----------------
        top_sizer = wx.BoxSizer(wx.HORIZONTAL)

        lbl_source = wx.StaticText(panel, label="Website Source:")
        source_names = self.sources.list_source_names()
        self.choice_source = wx.Choice(panel, choices=source_names)
        if source_names:
            self.choice_source.SetSelection(0)
        self.choice_source.SetName("Website Source")

        lbl_search = wx.StaticText(panel, label="Find Novel:")
        self.txt_search = wx.TextCtrl(panel, style=wx.TE_PROCESS_ENTER)
        self.txt_search.SetName("Find Novel")

        self.btn_search = wx.Button(panel, label="Find")
        self.btn_search.SetName("Find Novels")

        self.btn_reload = wx.Button(panel, label="Reload")
        self.btn_reload.SetName("Reload Source (F5)")

        self.btn_update = wx.Button(panel, label="Check Updates")
        self.btn_update.SetName("Check for Software Updates")

        top_sizer.Add(lbl_source, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)
        top_sizer.Add(self.choice_source, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 15)
        top_sizer.Add(lbl_search, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)
        top_sizer.Add(self.txt_search, 1, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)
        top_sizer.Add(self.btn_search, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        top_sizer.Add(self.btn_reload, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        top_sizer.Add(self.btn_update, 0, wx.ALIGN_CENTER_VERTICAL)

        main_sizer.Add(top_sizer, 0, wx.EXPAND | wx.ALL, 10)

        # ---------------- 2. Main Content Area (Three Columns) ----------------
        content_sizer = wx.BoxSizer(wx.HORIZONTAL)

        # Column 1 (Left): Categories / Genres
        col1_sizer = wx.BoxSizer(wx.VERTICAL)
        lbl_cats = wx.StaticText(panel, label="Categories:")
        self.list_categories = wx.ListBox(panel, style=wx.LB_SINGLE)
        self.list_categories.SetName("Categories")
        self.list_categories.Set(["Loading categories..."])
        col1_sizer.Add(lbl_cats, 0, wx.BOTTOM, 4)
        col1_sizer.Add(self.list_categories, 1, wx.EXPAND)
        content_sizer.Add(col1_sizer, 1, wx.EXPAND | wx.RIGHT, 10)

        # Column 2 (Middle): Novels & Chapters Lists
        col2_sizer = wx.BoxSizer(wx.VERTICAL)

        lbl_novels = wx.StaticText(panel, label="Novels:")
        self.list_novels = wx.ListBox(panel, style=wx.LB_SINGLE)
        self.list_novels.SetName("Novels")
        self.list_novels.Set(["Select a category to view novels"])

        self.btn_load_chapters = wx.Button(panel, label="Load Chapters for Selected Novel (Enter)")
        self.btn_load_chapters.SetName("Load Chapters for Selected Novel (Enter)")
        self.btn_load_chapters.Disable()

        # Pagination Controls Bar (matches Downloader - Python)
        page_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.btn_prev_page = wx.Button(panel, label="< Previous Page", size=(120, 28))
        self.btn_prev_page.SetName("Previous Page (PageUp)")
        self.lbl_page_info = wx.StaticText(panel, label="Page 1", style=wx.ALIGN_CENTER)
        self.lbl_page_info.SetName("Current Page")
        self.btn_next_page = wx.Button(panel, label="Next Page >", size=(120, 28))
        self.btn_next_page.SetName("Next Page (PageDown)")

        self.btn_prev_page.Disable()
        self.btn_next_page.Disable()

        page_sizer.Add(self.btn_prev_page, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        page_sizer.Add(self.lbl_page_info, 1, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        page_sizer.Add(self.btn_next_page, 0, wx.ALIGN_CENTER_VERTICAL)

        # Smart Chapter Header (Range Dropdown + Jump Button + Sort Button)
        chap_header_sizer = wx.BoxSizer(wx.HORIZONTAL)
        lbl_chapters = wx.StaticText(panel, label="Chapters:")
        self.choice_chapter_range = wx.Choice(panel, choices=["All Chapters"])
        self.choice_chapter_range.SetName("Chapter Range")
        self.choice_chapter_range.SetSelection(0)
        self.choice_chapter_range.Hide()

        self.btn_jump_chapter = wx.Button(panel, label="Jump (Ctrl+J)", size=(96, 26))
        self.btn_jump_chapter.SetName("Jump to Chapter (Ctrl+J)")
        self.btn_jump_chapter.Disable()

        self.btn_sort_chapters = wx.Button(panel, label="Sort: 1-9", size=(76, 26))
        self.btn_sort_chapters.SetName("Toggle Chapters Sort Order")
        self.btn_sort_chapters.Disable()

        chap_header_sizer.Add(lbl_chapters, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        chap_header_sizer.Add(self.choice_chapter_range, 1, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        chap_header_sizer.Add(self.btn_jump_chapter, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        chap_header_sizer.Add(self.btn_sort_chapters, 0, wx.ALIGN_CENTER_VERTICAL)

        self.list_chapters = wx.ListBox(panel, style=wx.LB_SINGLE)
        self.list_chapters.SetName("Chapters")
        self.list_chapters.Set(["Select a novel to view chapters"])

        self.btn_read_chapter = wx.Button(panel, label="Read Selected Chapter")
        self.btn_read_chapter.SetName("Read Selected Chapter")

        col2_sizer.Add(lbl_novels, 0, wx.BOTTOM, 4)
        col2_sizer.Add(self.list_novels, 1, wx.EXPAND | wx.BOTTOM, 6)
        col2_sizer.Add(self.btn_load_chapters, 0, wx.EXPAND | wx.BOTTOM, 6)
        col2_sizer.Add(page_sizer, 0, wx.EXPAND | wx.BOTTOM, 8)
        col2_sizer.Add(chap_header_sizer, 0, wx.EXPAND | wx.BOTTOM, 4)
        col2_sizer.Add(self.list_chapters, 1, wx.EXPAND | wx.BOTTOM, 8)
        col2_sizer.Add(self.btn_read_chapter, 0, wx.EXPAND)

        content_sizer.Add(col2_sizer, 2, wx.EXPAND | wx.RIGHT, 10)

        # Column 3 (Right): Reading Section & Chapter Navigation
        col3_sizer = wx.BoxSizer(wx.VERTICAL)

        nav_sizer = wx.BoxSizer(wx.HORIZONTAL)

        self.btn_prev_chapter = wx.Button(panel, label="< Previous Chapter (Alt+P)")
        self.btn_prev_chapter.SetName("Previous Chapter (Alt+P)")

        self.lbl_chapter_title = wx.StaticText(panel, label="No chapter loaded.")
        self.lbl_chapter_title.SetName("Current Chapter Title")

        self.btn_next_chapter = wx.Button(panel, label="Next Chapter (Alt+N) >")
        self.btn_next_chapter.SetName("Next Chapter (Alt+N)")

        self.btn_bookmark = wx.Button(panel, label="Bookmark (Ctrl+B)")
        self.btn_bookmark.SetName("Bookmark Current Chapter (Ctrl+B)")

        self.btn_update_bookmark = wx.Button(panel, label="Update Bookmark (Ctrl+U)")
        self.btn_update_bookmark.SetName("Update Bookmark to Current Chapter (Ctrl+U)")

        self.btn_load_bookmark = wx.Button(panel, label="Load Bookmark (Ctrl+L)")
        self.btn_load_bookmark.SetName("Load Saved Bookmark (Ctrl+L)")

        nav_sizer.Add(self.btn_prev_chapter, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        nav_sizer.Add(self.lbl_chapter_title, 1, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        nav_sizer.Add(self.btn_next_chapter, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        nav_sizer.Add(self.btn_bookmark, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        nav_sizer.Add(self.btn_update_bookmark, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        nav_sizer.Add(self.btn_load_bookmark, 0, wx.ALIGN_CENTER_VERTICAL)

        col3_sizer.Add(nav_sizer, 0, wx.EXPAND | wx.BOTTOM, 8)

        lbl_reading = wx.StaticText(
            panel,
            label="Reading Section (Use Up and Down arrows to read line by line):",
        )
        self.txt_reading = wx.TextCtrl(
            panel,
            style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_DONTWRAP | wx.HSCROLL,
            value=WELCOME_TEXT,
        )
        self.txt_reading.SetName("Reading Section")

        font = wx.Font(12, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL)
        self.txt_reading.SetFont(font)

        col3_sizer.Add(lbl_reading, 0, wx.BOTTOM, 4)
        col3_sizer.Add(self.txt_reading, 1, wx.EXPAND)

        content_sizer.Add(col3_sizer, 3, wx.EXPAND)

        main_sizer.Add(content_sizer, 1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        # ---------------- 3. Status Bar ----------------
        self.status_bar = self.CreateStatusBar(2)
        self.status_bar.SetStatusWidths([-3, -1])
        self.SetStatusText("Ready", 0)

        panel.SetSizer(main_sizer)
        self.SetMinSize((900, 600))
        self.Layout()
        panel.Layout()

    def _bind_events(self) -> None:
        self.Bind(wx.EVT_SIZE, self._on_resize)
        self.Bind(wx.EVT_CHAR_HOOK, self._on_char_hook)
        self.choice_source.Bind(wx.EVT_CHOICE, self.on_source_changed)
        self.btn_search.Bind(wx.EVT_BUTTON, self.on_search)
        self.txt_search.Bind(wx.EVT_TEXT_ENTER, self.on_search)
        self.btn_reload.Bind(wx.EVT_BUTTON, self.on_reload)
        self.btn_update.Bind(wx.EVT_BUTTON, self.on_check_updates)

        # ListBox Events: Single selection & Double click / Enter
        self.list_categories.Bind(wx.EVT_LISTBOX, self.on_category_selected)
        self.list_categories.Bind(wx.EVT_LISTBOX_DCLICK, self.on_category_selected)
        self.list_categories.Bind(wx.EVT_KEY_DOWN, self._on_category_key_down)

        self.list_novels.Bind(wx.EVT_LISTBOX_DCLICK, self.on_novel_selected)
        self.list_novels.Bind(wx.EVT_KEY_DOWN, self._on_novel_key_down)
        self.btn_load_chapters.Bind(wx.EVT_BUTTON, self.on_novel_selected)

        self.list_chapters.Bind(wx.EVT_LISTBOX_DCLICK, self.on_chapter_selected)
        self.list_chapters.Bind(wx.EVT_KEY_DOWN, self._on_chapter_key_down)
        self.btn_read_chapter.Bind(wx.EVT_BUTTON, self.on_chapter_selected)

        self.choice_chapter_range.Bind(wx.EVT_CHOICE, self.on_chapter_range_changed)
        self.btn_jump_chapter.Bind(wx.EVT_BUTTON, self.on_jump_to_chapter)
        self.btn_sort_chapters.Bind(wx.EVT_BUTTON, self.on_toggle_chapter_sort)

        self.btn_prev_chapter.Bind(wx.EVT_BUTTON, self.on_prev_chapter)
        self.btn_next_chapter.Bind(wx.EVT_BUTTON, self.on_next_chapter)
        self.btn_bookmark.Bind(wx.EVT_BUTTON, self.on_save_bookmark)
        self.btn_update_bookmark.Bind(wx.EVT_BUTTON, self.on_update_bookmark)
        self.btn_load_bookmark.Bind(wx.EVT_BUTTON, self.on_load_bookmark)

        self.btn_prev_page.Bind(wx.EVT_BUTTON, self.on_prev_page)
        self.btn_next_page.Bind(wx.EVT_BUTTON, self.on_next_page)

        # Essential Shortcuts Only (Matches Downloader - Python model)
        accel_entries = [
            wx.AcceleratorEntry(wx.ACCEL_NORMAL, wx.WXK_F5, ID_HOTKEY_RELOAD),
            wx.AcceleratorEntry(wx.ACCEL_NORMAL, wx.WXK_PAGEUP, ID_HOTKEY_PREV_PAGE),
            wx.AcceleratorEntry(wx.ACCEL_NORMAL, wx.WXK_PAGEDOWN, ID_HOTKEY_NEXT_PAGE),
            wx.AcceleratorEntry(wx.ACCEL_ALT, ord('P'), ID_HOTKEY_PREV_CHAPTER),
            wx.AcceleratorEntry(wx.ACCEL_ALT, ord('N'), ID_HOTKEY_NEXT_CHAPTER),
            wx.AcceleratorEntry(wx.ACCEL_CTRL, ord('J'), ID_HOTKEY_JUMP_CHAPTER),
            wx.AcceleratorEntry(wx.ACCEL_CTRL, ord('B'), ID_HOTKEY_BOOKMARK),
            wx.AcceleratorEntry(wx.ACCEL_CTRL, ord('U'), ID_HOTKEY_UPDATE_BOOKMARK),
            wx.AcceleratorEntry(wx.ACCEL_CTRL, ord('L'), ID_HOTKEY_LOAD_BOOKMARK),
        ]
        self.SetAcceleratorTable(wx.AcceleratorTable(accel_entries))

        # Explicit EVT_MENU Bindings for Essential Shortcuts
        self.Bind(wx.EVT_MENU, self.on_reload, id=ID_HOTKEY_RELOAD)
        self.Bind(wx.EVT_MENU, self.on_prev_page, id=ID_HOTKEY_PREV_PAGE)
        self.Bind(wx.EVT_MENU, self.on_next_page, id=ID_HOTKEY_NEXT_PAGE)
        self.Bind(wx.EVT_MENU, self.on_prev_chapter, id=ID_HOTKEY_PREV_CHAPTER)
        self.Bind(wx.EVT_MENU, self.on_next_chapter, id=ID_HOTKEY_NEXT_CHAPTER)
        self.Bind(wx.EVT_MENU, self.on_jump_to_chapter, id=ID_HOTKEY_JUMP_CHAPTER)
        self.Bind(wx.EVT_MENU, self.on_save_bookmark, id=ID_HOTKEY_BOOKMARK)
        self.Bind(wx.EVT_MENU, self.on_update_bookmark, id=ID_HOTKEY_UPDATE_BOOKMARK)
        self.Bind(wx.EVT_MENU, self.on_load_bookmark, id=ID_HOTKEY_LOAD_BOOKMARK)

    def _on_char_hook(self, event: wx.KeyEvent) -> None:
        key = event.GetKeyCode()
        if key in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
            focused = self.FindFocus()
            if focused == self.list_novels:
                self.on_novel_selected(None)
                return
            elif focused == self.list_categories:
                self.on_category_selected(None)
                return
            elif focused == self.list_chapters:
                self.on_chapter_selected(None)
                return
            elif focused == self.btn_load_chapters:
                self.on_novel_selected(None)
                return
        elif key == wx.WXK_TAB:
            focused = self.FindFocus()
            if focused:
                flags = wx.NavigationKeyEvent.IsBackward if event.ShiftDown() else wx.NavigationKeyEvent.IsForward
                focused.Navigate(flags)
                return
        event.Skip()

    def _on_resize(self, event: wx.SizeEvent) -> None:
        self.Layout()
        event.Skip()

    def _on_category_key_down(self, event: wx.KeyEvent) -> None:
        if event.GetKeyCode() in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
            self.on_category_selected(None)
        else:
            event.Skip()

    def _on_novel_key_down(self, event: wx.KeyEvent) -> None:
        if event.GetKeyCode() in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
            self.on_novel_selected(None)
        else:
            event.Skip()

    def _on_chapter_key_down(self, event: wx.KeyEvent) -> None:
        if event.GetKeyCode() in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
            self.on_chapter_selected(None)
        else:
            event.Skip()

    def _get_active_source(self) -> Optional[BaseNovelSource]:
        sel = self.choice_source.GetStringSelection()
        return self.sources.get_source(sel)

    # ---------------- 1. Category & Source Loading ----------------

    def _load_initial_source(self) -> None:
        source = self._get_active_source()
        if source:
            self._load_categories_for_source(source)

    def on_source_changed(self, event: wx.Event) -> None:
        source = self._get_active_source()
        if source:
            self.announcer.play_earcon("change")
            self._load_categories_for_source(source)

    def on_reload(self, event: Optional[wx.Event]) -> None:
        source = self._get_active_source()
        if source:
            # Clear caches for this source to force live reload
            if source.name in self._category_cache:
                del self._category_cache[source.name]
            keys_to_del = [k for k in self._novel_cache if k.startswith(source.name)]
            for k in keys_to_del:
                del self._novel_cache[k]
            self.current_page = 1
            self.search_mode = False
            self.announcer.play_earcon("change")
            self._load_categories_for_source(source)

    def _load_categories_for_source(self, source: BaseNovelSource) -> None:
        self._cat_token += 1
        token = self._cat_token
        self.current_source = source

        # Check in-memory cache
        if source.name in self._category_cache:
            cats = self._category_cache[source.name]
            self._update_categories_list(cats, token)
            return

        self.SetStatusText(f"Loading categories from {source.name}...", 0)
        self.announcer.play_earcon("start")

        def worker() -> None:
            try:
                cats = source.get_categories()
                self._category_cache[source.name] = cats
                if token == self._cat_token:
                    safe_call_after(self._update_categories_list, cats, token)
            except Exception as e:
                logging.error(f"Failed to load categories: {e}", exc_info=True)
                if token == self._cat_token:
                    safe_call_after(self._on_error, f"Failed to load categories: {e}")

        threading.Thread(target=worker, daemon=True).start()

    def _update_categories_list(self, categories: List[CategoryItem], token: int) -> None:
        if token != self._cat_token:
            return

        self.categories = categories
        items = [c.name for c in categories] if categories else ["No categories available"]
        self.list_categories.Set(items)

        self.SetStatusText(f"{len(categories)} categories loaded.", 0)
        self.announcer.play_earcon("complete")

        # Automatically load novels for the first category without stealing focus
        if categories:
            self.search_mode = False
            self.current_page = 1
            self.list_categories.SetSelection(0)
            self._fetch_novels_for_category(categories[0], page=1)

    # ---------------- 2. Category Selection -> Novel List ----------------

    def on_category_selected(self, event: Optional[wx.Event]) -> None:
        idx = self.list_categories.GetSelection()
        if idx == wx.NOT_FOUND or idx < 0:
            if self.categories:
                idx = 0
                self.list_categories.SetSelection(0)
            else:
                return
        if idx >= len(self.categories):
            return

        cat = self.categories[idx]
        self.search_mode = False
        self.current_page = 1
        self._fetch_novels_for_category(cat, page=1)

    def _fetch_novels_for_category(self, cat: CategoryItem, page: int = 1) -> None:
        self._novel_token += 1
        token = self._novel_token
        self.current_category = cat
        self.current_page = page
        source = self.current_source or self._get_active_source()
        if not source:
            return

        cache_key = f"{source.name}:{cat.url}:page:{page}"
        if cache_key in self._novel_cache:
            novels = self._novel_cache[cache_key]
            self._update_novel_list(novels, f"{len(novels)} novels in {cat.name} (Page {page}).", token)
            return

        self.SetStatusText(f"Loading novels in {cat.name} (Page {page})...", 0)

        def worker() -> None:
            try:
                novels = source.get_novels_by_category(cat.url, page=page)
                self._novel_cache[cache_key] = novels
                if token == self._novel_token:
                    safe_call_after(self._update_novel_list, novels, f"{len(novels)} novels in {cat.name} (Page {page}).", token)
            except Exception as e:
                logging.error(f"Failed to load novels: {e}", exc_info=True)
                if token == self._novel_token:
                    safe_call_after(self._on_error, f"Failed to load novels: {e}")

        threading.Thread(target=worker, daemon=True).start()

    # ---------------- 3. Search Query -> Novel List ----------------

    def on_search(self, event: Optional[wx.Event]) -> None:
        query = self.txt_search.GetValue().strip()
        if not query:
            self.SetStatusText("Please enter a novel title or keyword.", 0)
            return

        source = self._get_active_source()
        if not source:
            return

        self.search_mode = True
        self.last_search_query = query
        self.current_page = 1
        self._fetch_search_novels(query, page=1)

    def _fetch_search_novels(self, query: str, page: int = 1) -> None:
        self._novel_token += 1
        token = self._novel_token
        self.current_page = page
        source = self.current_source or self._get_active_source()
        if not source:
            return

        cache_key = f"{source.name}:search:{query}:page:{page}"
        if cache_key in self._novel_cache:
            novels = self._novel_cache[cache_key]
            self._update_novel_list(novels, f"Found {len(novels)} novels for '{query}' (Page {page}).", token)
            return

        self.SetStatusText(f"Searching for '{query}' on {source.name} (Page {page})...", 0)

        def worker() -> None:
            try:
                results = source.search(query, page=page)
                self._novel_cache[cache_key] = results
                if token == self._novel_token:
                    safe_call_after(self._update_novel_list, results, f"Found {len(results)} novels (Page {page}).", token)
            except Exception as e:
                logging.error(f"Search failed: {e}", exc_info=True)
                if token == self._novel_token:
                    safe_call_after(self._on_error, f"Search failed: {e}")

        threading.Thread(target=worker, daemon=True).start()

    def _update_novel_list(self, novels: List[NovelItem], message: str, token: int) -> None:
        if token != self._novel_token:
            return

        # If navigating beyond the last page and 0 novels returned:
        if not novels and self.current_page > 1:
            self.current_page -= 1
            self.lbl_page_info.SetLabel(f"Page {self.current_page}")
            self.btn_next_page.Disable()
            msg = f"No more novels. Staying on page {self.current_page}."
            self.SetStatusText(msg, 0)
            self.announcer.speak(msg)
            return

        self.novels = novels
        items = [n.title for n in novels] if novels else ["No novels found in this category"]
        self.list_novels.Set(items)

        # Update pagination bar controls
        self.lbl_page_info.SetLabel(f"Page {self.current_page}")
        self.btn_prev_page.Enable(self.current_page > 1)
        self.btn_next_page.Enable(len(novels) > 0)

        self.SetStatusText(message, 0)

        # Set novel selection; strictly do NOT fetch chapters until user presses Enter
        if novels:
            self.list_novels.SetSelection(0)
            self.btn_load_chapters.Enable(True)
            if not self._loading_novel_url:
                self.list_chapters.Set(["Press Enter on a novel to load its chapters"])
                self.btn_jump_chapter.Disable()
                self.btn_sort_chapters.Disable()
                self.choice_chapter_range.Hide()
            self.Layout()
            if self.current_page > 1:
                self.announcer.speak(f"Page {self.current_page} loaded. {len(novels)} novels.")
        else:
            self.btn_load_chapters.Disable()
            self.list_chapters.Set(["No novels found in this category"])
            self.btn_jump_chapter.Disable()
            self.btn_sort_chapters.Disable()
            self.choice_chapter_range.Hide()
            self.Layout()

    def on_prev_page(self, event: Optional[wx.Event]) -> None:
        if self.FindFocus() == self.txt_reading:
            self.txt_reading.ScrollLines(-10)
            return

        if self.current_page <= 1:
            self.announcer.speak("Already on first page.")
            return

        target_page = self.current_page - 1
        if self.search_mode:
            self._fetch_search_novels(self.last_search_query, page=target_page)
        elif self.current_category:
            self._fetch_novels_for_category(self.current_category, page=target_page)

    def on_next_page(self, event: Optional[wx.Event]) -> None:
        if self.FindFocus() == self.txt_reading:
            self.txt_reading.ScrollLines(10)
            return

        if not self.novels:
            self.announcer.speak("No novels to paginate.")
            return

        target_page = self.current_page + 1
        if self.search_mode:
            self._fetch_search_novels(self.last_search_query, page=target_page)
        elif self.current_category:
            self._fetch_novels_for_category(self.current_category, page=target_page)

    # ---------------- 4. Novel Selection -> Chapter List ----------------

    def on_novel_selected(self, event: Optional[wx.Event]) -> None:
        if not self.novels:
            return

        idx = self.list_novels.GetSelection()
        if idx == wx.NOT_FOUND or idx < 0:
            idx = 0
            self.list_novels.SetSelection(0)
        elif idx >= len(self.novels):
            idx = len(self.novels) - 1
            self.list_novels.SetSelection(idx)

        novel = self.novels[idx]
        self._fetch_chapters_for_novel(novel)

    def _fetch_chapters_for_novel(self, novel: NovelItem) -> None:
        if self._loading_novel_url == novel.url:
            return

        self._chap_token += 1
        token = self._chap_token
        self.current_novel = novel
        source = (
            self.sources.get_source(novel.source_name)
            if hasattr(novel, "source_name") and novel.source_name
            else None
        ) or self.current_source or self._get_active_source()
        if not source:
            return

        cache_key = f"{source.name}:{novel.url}"
        if cache_key in self._chapter_cache:
            chapters = self._chapter_cache[cache_key]
            self._update_chapter_list(chapters, token)
            return

        self._loading_novel_url = novel.url
        self.btn_load_chapters.Disable()
        self.btn_load_chapters.SetLabel("Loading Chapters...")
        self.list_chapters.Set([f"Loading chapters for '{novel.title}', please wait..."])
        self.SetStatusText(f"Loading chapters for '{novel.title}'...", 0)
        self.announcer.speak(f"Loading chapters for {novel.title}...")

        def worker() -> None:
            try:
                chapters = source.get_chapters(novel.url)
                self._chapter_cache[cache_key] = chapters
                if token == self._chap_token:
                    safe_call_after(self._update_chapter_list, chapters, token)
            except Exception as e:
                logging.error(f"Failed to load chapters: {e}", exc_info=True)
                if token == self._chap_token:
                    def _on_failed() -> None:
                        self._loading_novel_url = None
                        self.btn_load_chapters.Enable(True)
                        self.btn_load_chapters.SetLabel("Load Chapters for Selected Novel (Enter)")
                        self.list_chapters.Set([f"Failed to load chapters: {e}"])
                        self.SetStatusText(f"Failed to load chapters: {e}", 0)
                        self.announcer.speak(f"Failed to load chapters for {novel.title}.")
                    safe_call_after(_on_failed)
            finally:
                if self._loading_novel_url == novel.url:
                    self._loading_novel_url = None

        threading.Thread(target=worker, daemon=True).start()

    def _update_chapter_list(self, chapters: List[ChapterItem], token: int) -> None:
        if token != self._chap_token:
            return

        self._loading_novel_url = None
        self.btn_load_chapters.Enable(True)
        self.btn_load_chapters.SetLabel("Load Chapters for Selected Novel (Enter)")

        try:
            self.all_chapters = list(chapters)
            self.current_range_idx = 0
            total = len(self.all_chapters)
            title = self.current_novel.title if self.current_novel else "Novel"

            if not chapters:
                self.chapters = []
                self.list_chapters.Set([f"No chapters found for '{title}'. Try switching source or reloading."])
                self.choice_chapter_range.Hide()
                self.btn_jump_chapter.Disable()
                self.btn_sort_chapters.Disable()
                self.Layout()
                self.announcer.speak(f"No chapters found for {title}.")
                return

            self.btn_jump_chapter.Enable(True)
            self.btn_sort_chapters.Enable(True)

            if not self.chapter_sort_asc:
                self.all_chapters.reverse()

            self._rebuild_chapter_ranges(select_bucket=0, select_item=0)

            msg = f"{total} chapters loaded for {title}."
            self.SetStatusText(msg, 0)
            if total > self.chapter_range_size:
                self.announcer.speak(f"{total} chapters loaded. Viewing chapters 1 to {min(total, self.chapter_range_size)}.")
            else:
                self.announcer.speak(msg)
        except Exception as err:
            logging.error(f"Error rendering chapter list: {err}", exc_info=True)
            self.list_chapters.Set([f"Error displaying chapters: {err}"])
            self.announcer.speak("Error displaying chapters.")

    def _rebuild_chapter_ranges(self, select_bucket: int = 0, select_item: int = 0) -> None:
        total = len(self.all_chapters)
        if total == 0:
            return

        if total <= self.chapter_range_size:
            self.choice_chapter_range.Hide()
            self.current_range_idx = 0
            self.chapters = list(self.all_chapters)
            self.list_chapters.Set([ch.title for ch in self.chapters])
            if self.chapters:
                clamped = max(0, min(select_item, len(self.chapters) - 1))
                self.list_chapters.SetSelection(clamped)
                self.current_chapter = self.chapters[clamped]
        else:
            num_buckets = (total + self.chapter_range_size - 1) // self.chapter_range_size
            labels = []
            for b in range(num_buckets):
                start = b * self.chapter_range_size + 1
                end = min((b + 1) * self.chapter_range_size, total)
                labels.append(f"Chapters {start} - {end}")

            self.choice_chapter_range.Set(labels)
            clamped_bucket = max(0, min(select_bucket, num_buckets - 1))
            self.choice_chapter_range.SetSelection(clamped_bucket)
            self.choice_chapter_range.Show()
            self._render_chapter_bucket(clamped_bucket, select_item=select_item)

        self.Layout()

    def _render_chapter_bucket(self, bucket_idx: int, select_item: int = 0) -> None:
        self.current_range_idx = bucket_idx
        start = bucket_idx * self.chapter_range_size
        end = min(start + self.chapter_range_size, len(self.all_chapters))
        self.chapters = self.all_chapters[start:end]
        self.list_chapters.Set([ch.title for ch in self.chapters])

        if self.chapters:
            clamped = max(0, min(select_item, len(self.chapters) - 1))
            self.list_chapters.SetSelection(clamped)
            self.current_chapter = self.chapters[clamped]

    def on_chapter_range_changed(self, event: Optional[wx.Event] = None) -> None:
        sel = self.choice_chapter_range.GetSelection()
        if sel != wx.NOT_FOUND:
            self._render_chapter_bucket(sel, select_item=0)
            range_label = self.choice_chapter_range.GetString(sel)
            self.announcer.speak(f"Showing {range_label}.")

    def on_toggle_chapter_sort(self, event: Optional[wx.Event] = None) -> None:
        if not self.all_chapters:
            return

        self.chapter_sort_asc = not self.chapter_sort_asc
        self.all_chapters.reverse()

        if self.chapter_sort_asc:
            self.btn_sort_chapters.SetLabel("Sort: 1-9")
            msg = "Chapters sorted oldest first."
        else:
            self.btn_sort_chapters.SetLabel("Sort: 9-1")
            msg = "Chapters sorted newest first."

        self._rebuild_chapter_ranges(select_bucket=0, select_item=0)
        self.announcer.speak(msg)

    def on_jump_to_chapter(self, event: Optional[wx.Event] = None, target_input: Optional[str] = None) -> None:
        total = len(self.all_chapters)
        if total == 0:
            self.announcer.speak("No chapters loaded to jump to.")
            return

        if target_input is not None:
            val = target_input.strip()
        else:
            dlg = wx.TextEntryDialog(
                self,
                f"Enter chapter number to jump to (1 to {total}):",
                "Jump to Chapter",
                "",
            )
            dlg.SetName("Jump to Chapter Dialog")

            if dlg.ShowModal() == wx.ID_OK:
                val = dlg.GetValue().strip()
                dlg.Destroy()
            else:
                dlg.Destroy()
                return

        match = re.search(r"\d+", val)
        if not match:
            self.announcer.speak("Please enter a valid chapter number.")
            return

        num = int(match.group())
        target_idx = -1
        for idx, ch in enumerate(self.all_chapters):
            if ch.index == num:
                target_idx = idx
                break
            m = re.search(r"chapter\s*(\d+)", ch.title, re.IGNORECASE)
            if m and int(m.group(1)) == num:
                target_idx = idx
                break

        if target_idx == -1:
            if 1 <= num <= total:
                target_idx = num - 1 if self.chapter_sort_asc else (total - num)
            else:
                self.announcer.speak(f"Chapter {num} is outside range 1 to {total}.")
                return

        self._sync_chapter_bucket_selection(target_idx)
        target_chapter = self.all_chapters[target_idx]
        self.current_chapter = target_chapter
        self._load_chapter_by_url(target_chapter.url)
        self.announcer.speak(f"Jumped to {target_chapter.title}.")

    def _sync_chapter_bucket_selection(self, global_idx: int) -> None:
        if len(self.all_chapters) <= self.chapter_range_size:
            if 0 <= global_idx < len(self.chapters):
                self.list_chapters.SetSelection(global_idx)
                self.current_chapter = self.chapters[global_idx]
        else:
            bucket_idx = global_idx // self.chapter_range_size
            local_idx = global_idx % self.chapter_range_size
            if bucket_idx != self.current_range_idx:
                self.choice_chapter_range.SetSelection(bucket_idx)
                self._render_chapter_bucket(bucket_idx, select_item=local_idx)
            else:
                self.list_chapters.SetSelection(local_idx)
                if 0 <= local_idx < len(self.chapters):
                    self.current_chapter = self.chapters[local_idx]

    def _get_current_global_chapter_idx(self) -> int:
        if not self.current_chapter:
            return -1
        for idx, ch in enumerate(self.all_chapters):
            if ch.url == self.current_chapter.url:
                return idx
        return -1

    # ---------------- 5. Chapter Selection -> Reading Area ----------------

    def on_chapter_selected(self, event: Optional[wx.Event]) -> None:
        idx = self.list_chapters.GetSelection()
        if idx == wx.NOT_FOUND or idx < 0:
            if self.chapters:
                idx = 0
                self.list_chapters.SetSelection(0)
            else:
                self.SetStatusText("Please select a chapter first.", 0)
                return
        if idx >= len(self.chapters):
            self.SetStatusText("Please select a chapter first.", 0)
            return

        chapter = self.chapters[idx]
        self.current_chapter = chapter
        self._load_chapter_by_url(chapter.url)

    def _load_chapter_by_url(self, chapter_url: str) -> None:
        self._content_token += 1
        token = self._content_token

        source = self.current_source or self._get_active_source()
        if not source:
            return

        if chapter_url in self._content_cache:
            content = self._content_cache[chapter_url]
            self._display_chapter_content(content, token)
            return

        self.SetStatusText("Fetching chapter text...", 0)
        self.announcer.play_earcon("start")

        def worker() -> None:
            try:
                content = source.get_chapter_content(chapter_url)
                self._content_cache[chapter_url] = content
                if token == self._content_token:
                    safe_call_after(self._display_chapter_content, content, token)
            except Exception as e:
                logging.error(f"Failed to fetch chapter content: {e}", exc_info=True)
                if token == self._content_token:
                    safe_call_after(self._on_error, f"Failed to fetch chapter: {e}")

        threading.Thread(target=worker, daemon=True).start()

    def _display_chapter_content(self, content: ChapterContent, token: int) -> None:
        if token != self._content_token:
            return

        self.current_chapter_content = content

        self.lbl_chapter_title.SetLabel(content.title)

        # Standardize CRLF on Windows so NVDA reads line-by-line smoothly with Up/Down arrows
        crlf_text = content.content.replace("\r\n", "\n").replace("\r", "\n").replace("\n", "\r\n")
        self.txt_reading.SetValue(crlf_text)

        # Place cursor at top of reading area and shift focus so Up/Down arrows read immediately
        self.txt_reading.SetInsertionPoint(0)
        self.txt_reading.SetFocus()

        self.announcer.play_earcon("complete")
        msg = f"{content.title} loaded ({content.word_count} words). Ready to read."
        self.SetStatusText(msg, 0)
        self.SetStatusText(f"{content.word_count} words", 1)

    # ---------------- 6. Next & Previous Chapter Navigation ----------------

    def on_next_chapter(self, event: Optional[wx.Event]) -> None:
        if not self.current_chapter_content:
            self.SetStatusText("No chapter currently loaded.", 0)
            return

        self.announcer.stop()

        if self.current_chapter_content.next_chapter_url:
            next_url = self.current_chapter_content.next_chapter_url
            for idx, ch in enumerate(self.all_chapters):
                if ch.url == next_url:
                    self._sync_chapter_bucket_selection(idx)
                    break
            self._load_chapter_by_url(next_url)
            return

        cur_idx = self._get_current_global_chapter_idx()
        if cur_idx != -1 and cur_idx + 1 < len(self.all_chapters):
            next_idx = cur_idx + 1
            self._sync_chapter_bucket_selection(next_idx)
            target = self.all_chapters[next_idx]
            self.current_chapter = target
            self._load_chapter_by_url(target.url)
        else:
            self.SetStatusText("No further chapters available.", 0)

    def on_prev_chapter(self, event: Optional[wx.Event]) -> None:
        if not self.current_chapter_content:
            self.SetStatusText("No chapter currently loaded.", 0)
            return

        self.announcer.stop()

        if self.current_chapter_content.prev_chapter_url:
            prev_url = self.current_chapter_content.prev_chapter_url
            for idx, ch in enumerate(self.all_chapters):
                if ch.url == prev_url:
                    self._sync_chapter_bucket_selection(idx)
                    break
            self._load_chapter_by_url(prev_url)
            return

        cur_idx = self._get_current_global_chapter_idx()
        if cur_idx > 0:
            prev_idx = cur_idx - 1
            self._sync_chapter_bucket_selection(prev_idx)
            target = self.all_chapters[prev_idx]
            self.current_chapter = target
            self._load_chapter_by_url(target.url)
        else:
            self.SetStatusText("Already at first chapter.", 0)

    # ---------------- 7. Bookmark Lifecycle & Persistence ----------------

    def on_save_bookmark(self, event: Optional[wx.Event] = None) -> None:
        if not self.current_novel or not self.current_chapter:
            self.announcer.speak("No chapter is currently open to bookmark.")
            self.SetStatusText("Open a novel chapter first to bookmark it.", 0)
            return

        source = self.current_source or self._get_active_source()
        source_name = source.name if source else "FreeWebNovel"
        novel_title = self.current_novel.title
        novel_url = self.current_novel.url
        chapter_idx = self.current_chapter.index
        chapter_title = self.current_chapter.title
        chapter_url = self.current_chapter.url

        self.db.save_novel_bookmark(
            source_name=source_name,
            novel_title=novel_title,
            novel_url=novel_url,
            chapter_index=chapter_idx,
            chapter_title=chapter_title,
            chapter_url=chapter_url,
        )

        msg = f"Bookmarked {novel_title}, Chapter {chapter_idx}: {chapter_title}."
        self.SetStatusText(msg, 0)
        self.announcer.speak(msg)

    def on_update_bookmark(self, event: Optional[wx.Event] = None) -> None:
        if not self.current_novel or not self.current_chapter:
            self.announcer.speak("No chapter is currently open to update bookmark.")
            self.SetStatusText("Open a novel chapter first to update bookmark.", 0)
            return

        source = self.current_source or self._get_active_source()
        source_name = source.name if source else "FreeWebNovel"
        novel_title = self.current_novel.title
        novel_url = self.current_novel.url
        chapter_idx = self.current_chapter.index
        chapter_title = self.current_chapter.title
        chapter_url = self.current_chapter.url

        existing = self.db.get_novel_bookmark(novel_url)
        self.db.save_novel_bookmark(
            source_name=source_name,
            novel_title=novel_title,
            novel_url=novel_url,
            chapter_index=chapter_idx,
            chapter_title=chapter_title,
            chapter_url=chapter_url,
        )

        if existing:
            msg = f"Bookmark updated to Chapter {chapter_idx}: {chapter_title} for {novel_title}."
        else:
            msg = f"Created bookmark at Chapter {chapter_idx}: {chapter_title} for {novel_title}."

        self.SetStatusText(msg, 0)
        self.announcer.speak(msg)

    def on_load_bookmark(self, event: Optional[wx.Event] = None) -> None:
        bookmarks = self.db.list_novel_bookmarks()
        if not bookmarks:
            self.announcer.speak("No saved bookmarks found.")
            wx.MessageBox(
                "No saved bookmarks found.\r\n\r\nTo save a bookmark, read a chapter and click 'Bookmark' or press Ctrl+B.",
                "Bookmarks",
                wx.OK | wx.ICON_INFORMATION,
                self,
            )
            return

        if len(bookmarks) == 1:
            self._resume_from_bookmark(bookmarks[0])
            return

        dlg = BookmarkDialog(self, bookmarks, self.db)
        if dlg.ShowModal() == wx.ID_OK and dlg.selected_bookmark:
            target_bm = dlg.selected_bookmark
            dlg.Destroy()
            self._resume_from_bookmark(target_bm)
        else:
            dlg.Destroy()

    def _resume_from_bookmark(self, bm: dict) -> None:
        source_name = bm.get("source_name", "")
        novel_title = bm.get("novel_title", "")
        novel_url = bm.get("novel_url", "")
        target_ch_idx = bm.get("chapter_index", 1)
        target_ch_title = bm.get("chapter_title", "")
        target_ch_url = bm.get("chapter_url", "")

        # 1. Switch to source if available
        source = self.sources.get_source(source_name)
        if source:
            idx = self.choice_source.FindString(source.name)
            if idx != wx.NOT_FOUND:
                self.choice_source.SetSelection(idx)
            self.current_source = source
        else:
            source = self.current_source or self._get_active_source()

        # 2. Set current novel and show in novel list
        novel = NovelItem(
            id=novel_url.rstrip("/").split("/")[-1],
            title=novel_title,
            url=novel_url,
            source_name=source.name if source else source_name,
        )
        self.current_novel = novel

        novel_titles = [n.title for n in self.novels]
        if novel_title in novel_titles:
            n_idx = novel_titles.index(novel_title)
            self.list_novels.SetSelection(n_idx)
        else:
            self.novels = [novel]
            self.list_novels.Set([novel.title])
            self.list_novels.SetSelection(0)

        self.SetStatusText(f"Resuming bookmark: {novel_title}, Chapter {target_ch_idx}...", 0)
        self.announcer.speak(f"Loading bookmark for {novel_title}, Chapter {target_ch_idx}...")

        # 3. Fetch chapter catalog and jump to chapter
        self._chap_token += 1
        token = self._chap_token

        def worker() -> None:
            try:
                cache_key = f"{source.name}:{novel.url}" if source else novel.url
                if cache_key in self._chapter_cache:
                    chapters = self._chapter_cache[cache_key]
                else:
                    chapters = source.get_chapters(novel.url) if source else []
                    self._chapter_cache[cache_key] = chapters

                if token != self._chap_token:
                    return

                def on_chapters_ready() -> None:
                    if token != self._chap_token:
                        return
                    self.all_chapters = list(chapters)
                    self.current_range_idx = 0
                    total = len(self.all_chapters)
                    if not chapters:
                        self.chapters = []
                        self.list_chapters.Set(["No chapters available for this novel"])
                        self.choice_chapter_range.Hide()
                        self.btn_jump_chapter.Disable()
                        self.btn_sort_chapters.Disable()
                        self.Layout()
                        self.announcer.speak(f"No chapters found for {novel_title}.")
                        return

                    self.btn_jump_chapter.Enable(True)
                    self.btn_sort_chapters.Enable(True)

                    if not self.chapter_sort_asc:
                        self.all_chapters.reverse()

                    target_ch = None
                    for ch in self.all_chapters:
                        if ch.url == target_ch_url or ch.index == target_ch_idx:
                            target_ch = ch
                            break
                    if not target_ch and self.all_chapters:
                        target_ch = self.all_chapters[0]

                    bucket = 0
                    item_idx = 0
                    if target_ch and total > self.chapter_range_size:
                        bucket = (target_ch.index - 1) // self.chapter_range_size
                        item_idx = (target_ch.index - 1) % self.chapter_range_size
                    elif target_ch:
                        item_idx = target_ch.index - 1

                    self._rebuild_chapter_ranges(select_bucket=bucket, select_item=item_idx)

                    if target_ch:
                        self._load_chapter_by_url(target_ch.url)
                        msg = f"Loaded bookmark: {novel_title}, Chapter {target_ch.index}: {target_ch.title}."
                        self.SetStatusText(msg, 0)
                        self.announcer.speak(msg)

                safe_call_after(on_chapters_ready)

            except Exception as e:
                logging.error(f"Failed to load bookmark: {e}", exc_info=True)
                if token == self._chap_token:
                    safe_call_after(self._on_error, f"Failed to load bookmark: {e}")

        threading.Thread(target=worker, daemon=True).start()

    # ---------------- 8. Auto-Updater Integration ----------------

    def _start_background_update_check(self) -> None:
        def _bg() -> None:
            time.sleep(2.5)
            try:
                from novel_reader.updater import check_for_updates
                info = check_for_updates()
                if info and info.get("update_available"):
                    ver = info.get("latest_version")
                    def _notify() -> None:
                        self.SetStatusText(f"Notice: Update {ver} available! Click 'Check Updates'.", 0)
                        self.announcer.speak(f"A new software update {ver} is available.")
                    safe_call_after(_notify)
            except Exception:
                pass

        threading.Thread(target=_bg, daemon=True).start()

    def on_check_updates(self, event: Optional[wx.Event] = None) -> None:
        self.SetStatusText("Checking GitHub for updates...", 0)
        self.announcer.speak("Checking for updates...")
        self.btn_update.Disable()

        def _worker() -> None:
            try:
                from novel_reader.updater import check_for_updates, UpdateDialog, CURRENT_VERSION
                info = check_for_updates()
                def _done() -> None:
                    self.btn_update.Enable()
                    if info and info.get("update_available"):
                        dlg = UpdateDialog(self, info)
                        dlg.ShowModal()
                        dlg.Destroy()
                    else:
                        msg = "You are running the latest version."
                        self.SetStatusText(msg, 0)
                        self.announcer.speak(msg)
                        wx.MessageBox(
                            f"Accessible Novel Reader is up to date!\r\nInstalled Version: v{CURRENT_VERSION}",
                            "No Updates",
                            wx.OK | wx.ICON_INFORMATION,
                            self,
                        )
                safe_call_after(_done)
            except Exception as e:
                def _err() -> None:
                    self.btn_update.Enable()
                    self.SetStatusText(f"Update check error: {e}", 0)
                safe_call_after(_err)

        threading.Thread(target=_worker, daemon=True).start()

    # ---------------- 8. Error Handling ----------------

    def _on_error(self, message: str) -> None:
        self.SetStatusText(message, 0)
        self.announcer.play_earcon("error")
        wx.MessageBox(message, "Notice", wx.OK | wx.ICON_INFORMATION, self)


def launch_gui() -> None:
    """Launch the wxPython accessible novel reader interface."""
    app = wx.App(False)
    frame = NovelReaderFrame()
    frame.Show()
    app.MainLoop()
