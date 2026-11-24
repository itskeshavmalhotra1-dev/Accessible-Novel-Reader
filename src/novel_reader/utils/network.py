"""
Robust network utilities for Light Novel sources.
Prefers curl_cffi with Chrome 124 browser impersonation to bypass Cloudflare TLS fingerprinting,
falling back gracefully to standard requests if needed.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
}

try:
    from curl_cffi import requests as curl_requests
    HAS_CURL_CFFI = True
except ImportError:
    curl_requests = None
    HAS_CURL_CFFI = False

import requests as std_requests


def http_get(
    url: str,
    headers: Optional[Dict[str, str]] = None,
    timeout: int = 15,
    extra_headers: Optional[Dict[str, str]] = None,
) -> Optional[str]:
    """Fetch URL text with anti-bot evasion and fallback."""
    req_headers = dict(DEFAULT_HEADERS)
    if headers:
        req_headers.update(headers)
    if extra_headers:
        req_headers.update(extra_headers)

    # 1. Try curl_cffi first with Chrome 124 impersonation
    if HAS_CURL_CFFI and curl_requests:
        try:
            resp = curl_requests.get(
                url,
                headers=req_headers,
                impersonate="chrome124",
                timeout=timeout,
            )
            if resp.status_code == 200:
                return resp.text
            elif resp.status_code != 404:
                logger.warning("curl_cffi HTTP %d for %s", resp.status_code, url)
        except Exception as e:
            logger.debug("curl_cffi failed for %s: %s", url, e)

    # 2. Fallback to standard requests
    try:
        resp = std_requests.get(url, headers=req_headers, timeout=timeout)
        if resp.status_code == 200:
            return resp.text
        logger.warning("std_requests HTTP %d for %s", resp.status_code, url)
    except Exception as e:
        logger.warning("std_requests failed for %s: %s", url, e)

    return None


def http_get_soup(
    url: str,
    headers: Optional[Dict[str, str]] = None,
    timeout: int = 15,
) -> Optional[BeautifulSoup]:
    """Fetch URL and parse into BeautifulSoup."""
    html = http_get(url, headers=headers, timeout=timeout)
    if html:
        return BeautifulSoup(html, "html.parser")
    return None


def http_get_json(
    url: str,
    headers: Optional[Dict[str, str]] = None,
    timeout: int = 15,
) -> Optional[Any]:
    """Fetch URL and parse as JSON."""
    req_headers = dict(DEFAULT_HEADERS)
    if headers:
        req_headers.update(headers)
    req_headers["X-Requested-With"] = "XMLHttpRequest"

    if HAS_CURL_CFFI and curl_requests:
        try:
            resp = curl_requests.get(
                url,
                headers=req_headers,
                impersonate="chrome124",
                timeout=timeout,
            )
            if resp.status_code == 200:
                return resp.json()
        except Exception as e:
            logger.debug("curl_cffi json failed for %s: %s", url, e)

    try:
        resp = std_requests.get(url, headers=req_headers, timeout=timeout)
        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        logger.warning("std_requests json failed for %s: %s", url, e)

    return None
