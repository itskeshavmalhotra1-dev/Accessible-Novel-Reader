"""
Scraper for novelfull.net and compatible clones (novgo.net, novelping.com).
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


class NovelFullCompatibleSource(BaseNovelSource):
    """Reusable scraper for novelfull.net and compatible mirrors."""

    def __init__(self, name: str, base_url: str) -> None:
        self._name = name
        self._base_url = base_url.rstrip("/")

    @property
    def name(self) -> str:
        return self._name

    @property
    def base_url(self) -> str:
        return self._base_url

    def get_categories(self) -> List[CategoryItem]:
        categories: List[CategoryItem] = [
            CategoryItem(name="Latest Release", url=f"{self.base_url}/latest-release-novel"),
            CategoryItem(name="Hot Novels", url=f"{self.base_url}/hot-novel"),
            CategoryItem(name="Completed Novels", url=f"{self.base_url}/completed-novel"),
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
        url = f"{self.base_url}/latest-release-novel"
        return self.get_novels_by_category(url, page=page)

    def _parse_novel_list(self, html_content: str) -> List[NovelItem]:
        soup = BeautifulSoup(html_content, "html.parser")
        items: List[NovelItem] = []
        seen_urls = set()

        # Find novel links ending in .html that are root paths (e.g. /my-novel.html)
        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            if not href.endswith(".html") or href.startswith("http") or "/genre/" in href or "/index." in href:
                continue

            # Must not contain sub-paths (sub-paths are chapters like /novel/ch1.html)
            clean_href = href.lstrip("/")
            if "/" in clean_href:
                continue

            full_url = urljoin(self.base_url, href)
            if full_url in seen_urls:
                continue
            seen_urls.add(full_url)

            title = (a.get("title") or a.text).strip()
            if not title or len(title) < 2:
                continue

            novel_id = clean_href[:-5]
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
        seen_urls = set()

        # 1. Try to find novelId for AJAX full-catalog retrieval (fetches all 1000-3000+ chapters in 1 fast call)
        novel_id = None
        el_id = soup.select_one("[data-novel-id]")
        if el_id and el_id.get("data-novel-id"):
            novel_id = el_id.get("data-novel-id").strip()
        else:
            m = re.search(r"novel[_-]?id[:\s=]+['\"]?(\d+)", str(soup), re.IGNORECASE)
            if m:
                novel_id = m.group(1)

        if novel_id:
            ajax_url = f"{self.base_url}/ajax-chapter-option?novelId={novel_id}"
            ajax_soup = http_get_soup(ajax_url, timeout=15)
            if ajax_soup:
                options = ajax_soup.find_all("option")
                for idx, opt in enumerate(options, start=1):
                    val = opt.get("value", "").strip()
                    if not val:
                        continue
                    full_url = urljoin(self.base_url, val)
                    if full_url in seen_urls:
                        continue
                    seen_urls.add(full_url)
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

        # 2. Fallback to parsing embedded chapter links on the novel page
        anchors = [
            a for a in soup.find_all("a", href=True)
            if "chapter" in a["href"].lower() and a["href"].endswith(".html")
        ]

        for a in anchors:
            href = a["href"].strip()
            full_url = urljoin(self.base_url, href)
            if full_url in seen_urls or full_url == novel_url:
                continue
            seen_urls.add(full_url)

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

    def get_chapter_content(self, chapter_url: str) -> ChapterContent:
        soup = http_get_soup(chapter_url, timeout=15)
        if not soup:
            raise RuntimeError(f"Failed to fetch chapter from {chapter_url}")

        title_el = soup.select_one(".chapter-title, .chapter-text, h1, h2")
        title = title_el.text.strip() if title_el else "Chapter"

        content_el = soup.select_one(
            "#chr-content, #chapter-content, .chapter-content, .reading-content, .chapter-c, .entry-content, .txt"
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


class NovelFullSource(NovelFullCompatibleSource):
    def __init__(self) -> None:
        super().__init__(name="NovelFull", base_url="https://novelfull.net")


class NovGoSource(NovelFullCompatibleSource):
    def __init__(self) -> None:
        super().__init__(name="NovGo", base_url="https://novgo.net")


class NovelPingSource(NovelFullCompatibleSource):
    def __init__(self) -> None:
        super().__init__(name="NovelPing", base_url="https://novelping.com")
