"""
Tests for text utilities, HTML stripping, and speech sanitization.
"""

from novel_reader.utils.text import (
    estimate_reading_time_minutes,
    normalize_whitespace,
    sanitize_speech_text,
    split_into_paragraphs,
    strip_html_tags,
)


def test_strip_html_tags() -> None:
    html_input = "<h1>Title</h1><p>First paragraph &amp; more.</p><p>Second paragraph.</p>"
    cleaned = strip_html_tags(html_input)
    assert "Title" in cleaned
    assert "First paragraph & more." in cleaned
    assert "Second paragraph." in cleaned
    assert "<" not in cleaned
    assert ">" not in cleaned


def test_normalize_whitespace() -> None:
    raw = "  Line 1   \n\n\n\n   Line 2   \n\n\nLine 3  "
    normalized = normalize_whitespace(raw)
    assert normalized == "Line 1\n\nLine 2\n\nLine 3"


def test_sanitize_speech_text_removes_emojis() -> None:
    raw_with_emoji = "Welcome to the reader! 🚀📖 Read comfortably 🌟"
    sanitized = sanitize_speech_text(raw_with_emoji, remove_emojis=True)
    assert sanitized == "Welcome to the reader! Read comfortably"
    assert "🚀" not in sanitized
    assert "📖" not in sanitized
    assert "🌟" not in sanitized


def test_split_into_paragraphs() -> None:
    text = "Paragraph 1 line A.\nParagraph 1 line B.\n\nParagraph 2.\n\n\nParagraph 3."
    paras = split_into_paragraphs(text)
    assert len(paras) == 3
    assert paras[0] == "Paragraph 1 line A.\nParagraph 1 line B."
    assert paras[1] == "Paragraph 2."
    assert paras[2] == "Paragraph 3."


def test_intra_paragraph_unwrapping() -> None:
    html_input = (
        "<p>Standing in front of him was an afraid looking\n"
        "young man with a delicate appearance\n"
        "and a slender build.</p>\n"
        "<p>He lifted his head,<br>calmly smiling.</p>"
    )
    cleaned = strip_html_tags(html_input)
    paragraphs = cleaned.split("\n\n")
    assert len(paragraphs) == 2
    assert paragraphs[0] == "Standing in front of him was an afraid looking young man with a delicate appearance and a slender build."
    assert paragraphs[1] == "He lifted his head, calmly smiling."
    assert "\n" not in paragraphs[0]
    assert "\n" not in paragraphs[1]


def test_estimate_reading_time() -> None:
    assert estimate_reading_time_minutes(200, words_per_minute=200) == 1
    assert estimate_reading_time_minutes(500, words_per_minute=200) == 3
    assert estimate_reading_time_minutes(0) == 0
