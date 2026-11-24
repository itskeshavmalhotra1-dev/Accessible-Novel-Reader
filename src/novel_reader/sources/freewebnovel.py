"""
Scraper for freewebnovel.com.
"""

from __future__ import annotations

import re
import time
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
from novel_reader.utils.network import http_get, http_get_json, http_get_soup
from novel_reader.utils.text import normalize_whitespace, strip_html_tags

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


class FreeWebNovelSource(BaseNovelSource):
    """Scraper implementation for freewebnovel.com."""

    @property
    def name(self) -> str:
        return "FreeWebNovel"

    @property
    def base_url(self) -> str:
        return "https://freewebnovel.com"

    def get_categories(self) -> List[CategoryItem]:
        categories: List[CategoryItem] = [
            CategoryItem(name="Latest Release", url=f"{self.base_url}/sort/latest-release"),
            CategoryItem(name="Most Popular", url=f"{self.base_url}/sort/most-popular"),
            CategoryItem(name="Latest Novels", url=f"{self.base_url}/sort/latest-novel"),
            CategoryItem(name="Completed Novels", url=f"{self.base_url}/sort/completed-novel"),
        ]
        soup = http_get_soup(self.base_url, timeout=12)
        if soup:
            seen_urls = {c.url for c in categories}
            for a in soup.find_all("a", href=True):
                href = a["href"].strip()
                if href.startswith("/genre/"):
                    full_url = urljoin(self.base_url, href)
                    name = a.text.strip()
                    if name and full_url not in seen_urls:
                        seen_urls.add(full_url)
                        categories.append(CategoryItem(name=name, url=full_url))
        return categories

    def get_novels_by_category(self, category_url: str, page: int = 1) -> List[NovelItem]:
        clean_url = category_url.rstrip("/")
        parts = clean_url.split("/")
        if parts[-1].isdigit():
            base_cat_url = "/".join(parts[:-1])
        else:
            base_cat_url = clean_url

        if page > 1:
            target_url = f"{base_cat_url}/{page}"
        else:
            target_url = base_cat_url

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
        url = f"{self.base_url}/sort/latest-release"
        return self.get_novels_by_category(url, page=page)

    def _parse_novel_list(self, html_content: str) -> List[NovelItem]:
        soup = BeautifulSoup(html_content, "html.parser")
        items: List[NovelItem] = []
        seen_urls = set()

        elements = soup.select(".li-row, .ul-list1 li, .m-newest1 li")
        if not elements:
            elements = soup.select("h3.tit, .tit, h3 a")

        for el in elements:
            # Look for novel link in h3 or anchor
            link = el.select_one("h3.tit a, .tit a, a[title]") if el.name != "a" else el
            if not link or not link.get("href"):
                link = el.find("a", href=lambda h: h and h.startswith("/novel/"))

            if not link or not link.get("href"):
                continue

            href = link["href"].strip()
            if not href.startswith("/novel/"):
                continue

            # Must not be a chapter link
            clean_href = href.rstrip("/")
            if "/chapter-" in clean_href:
                continue

            full_url = urljoin(self.base_url, href)
            if full_url in seen_urls:
                continue
            seen_urls.add(full_url)

            title = (link.get("title") or link.text).strip()
            if not title:
                continue

            latest_chap = ""
            latest_el = el.find("a", href=lambda h: h and "/chapter-" in h)
            if latest_el:
                latest_chap = latest_el.text.strip()

            novel_id = clean_href.split("/")[-1]
            items.append(
                NovelItem(
                    id=novel_id,
                    title=title,
                    url=full_url,
                    source_name=self.name,
                    latest_chapter=latest_chap,
                )
            )

        return items

    def get_chapters(self, novel_url: str) -> List[ChapterItem]:
        soup = http_get_soup(novel_url, timeout=15)
        if not soup:
            return []

        chapters: List[ChapterItem] = []
        seen_urls = set()

        # 1. Check if indexListPage has total chapters or pagination
        page_root = soup.select_one("#indexListPage")
        total_pages = 1
        if page_root:
            if page_root.get("data-total-chapters"):
                try:
                    tot_ch = int(page_root.get("data-total-chapters"))
                    total_pages = max(1, (tot_ch + 199) // 200)
                except ValueError:
                    total_pages = 1
            elif page_root.get("data-total-page"):
                try:
                    total_pages = int(page_root.get("data-total-page"))
                except ValueError:
                    total_pages = 1

        if total_pages > 1:
            clean_novel_url = novel_url.split("?")[0].rstrip("/")
            pages_to_fetch = list(range(1, total_pages + 1))
            combined_html = ""

            for p in pages_to_fetch:
                ajax_url = f"{clean_novel_url}?ajax=chapters&page={p}&pageSize=200"
                headers = {"Referer": novel_url}
                data = http_get_json(ajax_url, headers=headers, timeout=8)
                if not data:
                    time.sleep(0.3)
                    data = http_get_json(ajax_url, headers=headers, timeout=8)
                if data and isinstance(data, dict):
                    combined_html += data.get("html", "")

            if combined_html:
                ajax_soup = BeautifulSoup(combined_html, "html.parser")
                for a in ajax_soup.find_all("a", href=True):
                    href = a["href"].strip()
                    if "/chapter-" not in href:
                        continue
                    full_url = urljoin(self.base_url, href)
                    if full_url in seen_urls:
                        continue
                    seen_urls.add(full_url)
                    title = (a.get("title") or a.text).strip() or f"Chapter {len(chapters) + 1}"
                    chapters.append(
                        ChapterItem(
                            index=len(chapters) + 1,
                            title=title,
                            url=full_url,
                            novel_url=novel_url,
                        )
                    )
                if chapters:
                    return chapters

        # 2. Fallback to static page links
        chapter_anchors = soup.select("#idData a, ul.ul-list5 li a, .m-newest2 ul li a, .m-newest1 ul li a")
        if not chapter_anchors:
            chapter_anchors = [a for a in soup.find_all("a", href=True) if "/chapter-" in a["href"]]

        for idx, a in enumerate(chapter_anchors, start=1):
            href = a["href"].strip()
            full_url = urljoin(self.base_url, href)
            if full_url in seen_urls:
                continue
            seen_urls.add(full_url)

            title = (a.get("title") or a.text).strip()
            if not title:
                title = f"Chapter {idx}"

            chapters.append(
                ChapterItem(
                    index=len(chapters) + 1,
                    title=title,
                    url=full_url,
                    novel_url=novel_url,
                )
            )

        # Some sites list newest first; if Chapter 1 is at the end, reverse it
        if len(chapters) > 1 and "chapter 1" in chapters[-1].title.lower():
            chapters.reverse()
            for idx, ch in enumerate(chapters, start=1):
                ch.index = idx

        return chapters

    def get_chapter_content(self, chapter_url: str) -> ChapterContent:
        soup = http_get_soup(chapter_url, timeout=15)
        if not soup:
            raise RuntimeError(f"Failed to fetch chapter from {chapter_url}")

        # Chapter Title
        title_el = soup.select_one(".titles h1, h1.chapter-title, .title-con, h2")
        title = title_el.text.strip() if title_el else "Chapter"

        # Content container
        content_el = soup.select_one(".txt, #chapter-content, .chapter-content, .article, .reading-content")
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

        # Remove ads, scripts, inline styling
        for junk in content_el.select("script, style, ins, .ads, .ad, .google-auto-placed"):
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

        # Prev / Next navigation links
        prev_url = None
        next_url = None

        for a in soup.find_all("a", href=True):
            txt = a.text.strip().lower()
            href = a["href"].strip()
            if not href or href.startswith("javascript"):
                continue
            full_href = urljoin(self.base_url, href)

            if "prev" in txt or a.get("id") == "prev_url":
                if not prev_url and full_href != chapter_url:
                    prev_url = full_href
            elif "next" in txt or a.get("id") == "next_url":
                if not next_url and full_href != chapter_url:
                    next_url = full_href

        return ChapterContent(
            title=title,
            content=cleaned_text,
            url=chapter_url,
            prev_chapter_url=prev_url,
            next_chapter_url=next_url,
        )
