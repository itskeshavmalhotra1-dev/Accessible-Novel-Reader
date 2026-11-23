"""
Scraper for novelping.com.
"""

from __future__ import annotations

import re
from typing import List, Optional
from urllib.parse import quote_plus, urljoin

from bs4 import BeautifulSoup
import requests

from novel_reader.sources.base import (
    BaseNovelSource,
    CategoryItem,
    ChapterContent,
    ChapterItem,
    NovelItem,
)
from novel_reader.utils.text import strip_html_tags

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


class NovelPingSource(BaseNovelSource):
    """Scraper implementation for novelping.com."""

    @property
    def name(self) -> str:
        return "NovelPing"

    @property
    def base_url(self) -> str:
        return "https://novelping.com"

    def get_categories(self) -> List[CategoryItem]:
        categories: List[CategoryItem] = [
            CategoryItem(name="Latest Updates", url=f"{self.base_url}/sort/updates"),
            CategoryItem(name="Hot Novels", url=f"{self.base_url}/sort/hot"),
            CategoryItem(name="Most Popular", url=f"{self.base_url}/sort/popular"),
            CategoryItem(name="Completed Novels", url=f"{self.base_url}/sort/complete"),
        ]
        try:
            resp = requests.get(self.base_url, headers=DEFAULT_HEADERS, timeout=10)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "html.parser")
                seen = {c.url for c in categories}
                for a in soup.find_all("a", href=True):
                    href = a["href"].strip()
                    if "/novelping-genres/" in href:
                        full_url = urljoin(self.base_url, href)
                        name = a.text.strip()
                        if not name:
                            name = href.rstrip("/").split("/")[-1].replace("-", " ").title()
                        if full_url not in seen and name:
                            seen.add(full_url)
                            categories.append(CategoryItem(name=name, url=full_url))
        except Exception:
            pass
        return categories

    def get_novels_by_category(self, category_url: str, page: int = 1) -> List[NovelItem]:
        clean_url = re.sub(r"[?&]page=\d+", "", category_url)
        if page > 1:
            sep = "&" if "?" in clean_url else "?"
            target_url = f"{clean_url}{sep}page={page}"
        else:
            target_url = clean_url

        try:
            resp = requests.get(target_url, headers=DEFAULT_HEADERS, timeout=12)
            if resp.status_code != 200:
                return []
            return self._parse_novel_list(resp.text)
        except Exception:
            return []

    def search(self, query: str, page: int = 1) -> List[NovelItem]:
        encoded = quote_plus(query.strip())
        url = f"{self.base_url}/search?keyword={encoded}"
        if page > 1:
            url += f"&page={page}"
        try:
            resp = requests.get(url, headers=DEFAULT_HEADERS, timeout=12)
            if resp.status_code != 200:
                return []
            return self._parse_novel_list(resp.text)
        except Exception:
            return []

    def get_latest(self, page: int = 1) -> List[NovelItem]:
        return self.get_novels_by_category(f"{self.base_url}/sort/updates", page=page)

    def _parse_novel_list(self, html_content: str) -> List[NovelItem]:
        soup = BeautifulSoup(html_content, "html.parser")
        items: List[NovelItem] = []
        seen = set()

        for h3 in soup.select("h3"):
            a = h3.find("a", href=True)
            if not a or not a.get("href"):
                continue

            href = a["href"].strip()
            if "/book/" not in href or "/chapter" in href:
                continue

            full_url = urljoin(self.base_url, href)
            if full_url in seen:
                continue
            seen.add(full_url)

            title = (a.get("title") or a.text).strip()
            if not title:
                continue

            novel_id = href.rstrip("/").split("/")[-1]
            items.append(
                NovelItem(
                    id=novel_id,
                    title=title,
                    url=full_url,
                    source_name=self.name,
                )
            )

        return items

    def get_chapters(self, novel_url: str) -> List[ChapterItem]:
        try:
            resp = requests.get(novel_url, headers=DEFAULT_HEADERS, timeout=15)
            if resp.status_code != 200:
                return []

            soup = BeautifulSoup(resp.text, "html.parser")
            chapters: List[ChapterItem] = []
            seen = set()

            for a in soup.find_all("a", href=True):
                href = a["href"].strip()
                if "/chapter" not in href or href.endswith("read") or "read now" in a.text.lower():
                    continue

                full_url = urljoin(self.base_url, href)
                if full_url in seen or full_url == novel_url:
                    continue
                seen.add(full_url)

                title = (a.get("title") or a.text).strip()
                if not title:
                    title = f"Chapter {len(chapters) + 1}"

                chapters.append(
                    ChapterItem(
                        index=len(chapters) + 1,
                        title=title,
                        url=full_url,
                        novel_url=novel_url,
                    )
                )

            return chapters
        except Exception:
            return []

    def get_chapter_content(self, chapter_url: str) -> ChapterContent:
        resp = requests.get(chapter_url, headers=DEFAULT_HEADERS, timeout=15)
        if resp.status_code != 200:
            raise RuntimeError(f"Failed to fetch chapter from {chapter_url} (HTTP {resp.status_code})")

        soup = BeautifulSoup(resp.text, "html.parser")

        title_el = soup.select_one(".chapter-title, h1, h2, .titles")
        title = title_el.text.strip() if title_el else "Chapter"

        content_el = soup.select_one(
            "div.chapter.container, #chapter-content, #chr-content, .txt, .chapter-content, .reading-content"
        )
        if not content_el:
            # Fallback: search for largest text paragraph container
            candidates = soup.find_all("div")
            best = None
            max_p = 0
            for div in candidates:
                p_count = len(div.find_all("p"))
                if p_count > max_p:
                    max_p = p_count
                    best = div
            if best and max_p >= 3:
                content_el = best
            else:
                raise RuntimeError("Could not find chapter content container on page.")

        for junk in content_el.select("script, style, ins, .ads, .ad"):
            junk.decompose()

        # If container has <p> tags, extract them cleanly to eliminate intra-paragraph line breaking
        p_tags = content_el.find_all("p")
        if len(p_tags) >= 2:
            paras = []
            for p in p_tags:
                clean_p = " ".join(p.get_text().split())
                if clean_p:
                    paras.append(clean_p)
            cleaned_text = "\n\n".join(paras)
        else:
            cleaned_text = strip_html_tags(str(content_el))

        prev_url = None
        next_url = None

        for a in soup.find_all("a", href=True):
            txt = a.text.strip().lower()
            href = a["href"].strip()
            if not href or href.startswith("javascript") or href == "#":
                continue
            full_href = urljoin(self.base_url, href)

            if "prev" in txt or a.get("id") in ["prev_chap", "prev_url"]:
                if not prev_url and full_href != chapter_url:
                    prev_url = full_href
            elif "next" in txt or a.get("id") in ["next_chap", "next_url"]:
                if not next_url and full_href != chapter_url:
                    next_url = full_href

        return ChapterContent(
            title=title,
            content=cleaned_text,
            url=chapter_url,
            prev_chapter_url=prev_url,
            next_chapter_url=next_url,
        )
