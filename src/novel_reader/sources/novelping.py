"""
Scraper for novelping.com.
"""

from __future__ import annotations

import re
from typing import List, Optional
from urllib.parse import quote_plus, urljoin

from bs4 import BeautifulSoup

from novel_reader.sources.base import (
    BaseNovelSource,
    CategoryItem,
    ChapterContent,
    ChapterItem,
    NovelItem,
)
from novel_reader.utils.network import http_get, http_get_soup
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
        soup = http_get_soup(self.base_url, timeout=12)
        if soup:
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
        return categories

    def get_novels_by_category(self, category_url: str, page: int = 1) -> List[NovelItem]:
        clean_url = re.sub(r"[?&]page=\d+", "", category_url)
        if page > 1:
            sep = "&" if "?" in clean_url else "?"
            target_url = f"{clean_url}{sep}page={page}"
        else:
            target_url = clean_url

        html = http_get(target_url, timeout=15)
        if not html:
            return []
        return self._parse_novel_list(html)

    def search(self, query: str, page: int = 1) -> List[NovelItem]:
        encoded = quote_plus(query.strip())
        url = f"{self.base_url}/search?keyword={encoded}"
        if page > 1:
            url += f"&page={page}"
        html = http_get(url, timeout=15)
        if not html:
            return []
        return self._parse_novel_list(html)

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
        soup = http_get_soup(novel_url, timeout=15)
        if not soup:
            return []

        chapters: List[ChapterItem] = []
        seen = set()

        # 1. Try AJAX chapter-option for instant full catalog (all 400-3000+ chapters in 1 fast call)
        novel_id = None
        el_id = soup.select_one("[data-novel-id]")
        if el_id and el_id.get("data-novel-id"):
            novel_id = el_id.get("data-novel-id").strip()
        if not novel_id:
            novel_id = novel_url.rstrip("/").split("/")[-1]

        if novel_id:
            ajax_url = f"{self.base_url}/ajax/chapter-option?novelId={novel_id}"
            ajax_soup = http_get_soup(ajax_url, timeout=15)
            if ajax_soup:
                options = ajax_soup.find_all("option")
                for idx, opt in enumerate(options, start=1):
                    val = opt.get("value", "").strip()
                    if not val:
                        continue
                    full_url = urljoin(self.base_url, val)
                    if full_url in seen:
                        continue
                    seen.add(full_url)
                    title = opt.text.strip() or f"Chapter {idx}"
                    chapters.append(
                        ChapterItem(
                            index=idx,
                            title=title,
                            url=full_url,
                            novel_url=novel_url,
                        )
                    )
                if chapters:
                    return chapters

        # 2. Fallback to parsing embedded chapter links on the page
        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            if "/chapter" not in href or href.endswith("read") or "read now" in a.text.lower():
                continue

            full_url = urljoin(self.base_url, href)
            if full_url in seen or full_url == novel_url:
                continue
            seen.add(full_url)

            title_el = a.select_one(".chapter-title, .nchr-text")
            if title_el and title_el.text.strip():
                title = title_el.text.strip()
            else:
                title = (a.get("title") or a.text).strip()
            title = re.sub(r"\s+\d+\s*$", "", title)
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

    def get_chapter_content(self, chapter_url: str) -> ChapterContent:
        soup = http_get_soup(chapter_url, timeout=15)
        if not soup:
            raise RuntimeError(f"Failed to fetch chapter from {chapter_url}")

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
