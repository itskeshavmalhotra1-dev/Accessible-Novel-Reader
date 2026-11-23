"""
Text processing, formatting, sanitization, paragraph unwrapping, and splitting utilities.
Optimized for accessible screen reader consumption (NVDA line-by-line reading).
"""

from __future__ import annotations

import html
import re
from typing import List

# Precompiled regex for HTML stripping and formatting
_TAG_RE = re.compile(r"<[^>]+>")
_MULTIPLE_SPACES = re.compile(r"[ \t]+")
_MULTIPLE_NEWLINES = re.compile(r"\n{3,}")
_EMOJI_PATTERN = re.compile(
    r"[\U00010000-\U0010ffff]|[\u2600-\u27bf]|[\u2300-\u23ff]|[\u2b50-\u2b55]",
    flags=re.UNICODE,
)


def strip_html_tags(text: str) -> str:
    """
    Remove HTML tags, unescape HTML entities, unwrap broken lines within paragraphs,
    and preserve clean paragraph boundaries.
    """
    if not text:
        return ""

    # Convert block tags and multiple breaks to paragraph boundaries (\n\n)
    text = re.sub(r"</(?:p|div|h[1-6]|li)>", "\n\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<(?:p|div|h[1-6]|li)[^>]*>", "\n\n", text, flags=re.IGNORECASE)
    text = re.sub(r"(?:<br\s*/?>\s*){2,}", "\n\n", text, flags=re.IGNORECASE)
    # Single <br> inside a paragraph is treated as a space to avoid word fragmentation
    text = re.sub(r"<br\s*/?>", " ", text, flags=re.IGNORECASE)

    # Strip remaining HTML tags
    cleaned = _TAG_RE.sub(" ", text)
    # Unescape HTML entities
    unescaped = html.unescape(cleaned)
    # Normalize whitespaces and unwrap fragmented lines within paragraphs
    return normalize_whitespace(unescaped)


def normalize_whitespace(text: str) -> str:
    """
    Normalize internal spacing, unwrap fragmented lines within paragraphs,
    and preserve clean paragraph breaks for screen readers.
    """
    if not text:
        return ""

    # Standardize newlines
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    # Split into paragraphs by double or multiple newlines
    raw_blocks = re.split(r"\n{2,}", normalized)
    paragraphs: List[str] = []

    for block in raw_blocks:
        # Collapse intra-paragraph hard line wraps and excess spaces into single spaces
        clean_para = " ".join(block.split())
        if clean_para:
            paragraphs.append(clean_para)

    # If the text had no double newlines but had multiple single lines,
    # let's make sure it doesn't leave hard-wrapped sentences fragmented
    if not paragraphs and normalized.strip():
        paragraphs.append(" ".join(normalized.split()))

    return "\n\n".join(paragraphs)


def sanitize_speech_text(text: str, remove_emojis: bool = True) -> str:
    """
    Sanitize text for speech synthesis and screen readers.
    Enforces the Zero-Emoji Invariant to prevent acoustic clutter.
    """
    if not text:
        return ""

    if remove_emojis:
        text = _EMOJI_PATTERN.sub("", text)

    return normalize_whitespace(text)


def split_into_paragraphs(text: str) -> List[str]:
    """Split text into distinct non-empty paragraphs."""
    if not text:
        return []
    paragraphs = text.split("\n\n")
    cleaned = []
    for p in paragraphs:
        p_clean = p.strip()
        if p_clean:
            cleaned.append(p_clean)
    return cleaned


def estimate_reading_time_minutes(word_count: int, words_per_minute: int = 200) -> int:
    """Estimate reading time in minutes based on words per minute."""
    if word_count <= 0 or words_per_minute <= 0:
        return 0
    return max(1, (word_count + words_per_minute - 1) // words_per_minute)
