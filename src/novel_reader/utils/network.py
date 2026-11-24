"""
Robust network utilities for Light Novel sources.
Prefers curl_cffi with persistent Chrome 124 browser session to bypass Cloudflare TLS fingerprinting,
falling back gracefully to standard requests if needed.
"""

from __future__ import annotations

import logging
import threading
import time
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
    "Sec-Ch-Ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"Windows"',
    "Upgrade-Insecure-Requests": "1",
}

try:
    from curl_cffi import requests as curl_requests
    HAS_CURL_CFFI = True
except ImportError:
    curl_requests = None
    HAS_CURL_CFFI = False

import requests as std_requests

_CURL_SESSION: Optional[Any] = None
_STD_SESSION: Optional[std_requests.Session] = None
_SESSION_LOCK = threading.Lock()


def get_curl_session() -> Optional[Any]:
    global _CURL_SESSION
    if _CURL_SESSION is None and HAS_CURL_CFFI and curl_requests:
        with _SESSION_LOCK:
            if _CURL_SESSION is None:
                try:
                    _CURL_SESSION = curl_requests.Session(impersonate="chrome124")
                except Exception as e:
                    logger.debug("Failed to create curl_cffi session: %s", e)
    return _CURL_SESSION


def get_std_session() -> std_requests.Session:
    global _STD_SESSION
    if _STD_SESSION is None:
        with _SESSION_LOCK:
            if _STD_SESSION is None:
                _STD_SESSION = std_requests.Session()
    return _STD_SESSION


def http_get(
    url: str,
    headers: Optional[Dict[str, str]] = None,
    timeout: int = 15,
    extra_headers: Optional[Dict[str, str]] = None,
) -> Optional[str]:
    """Fetch URL text with anti-bot evasion, persistent session, and fallback."""
    req_headers = dict(DEFAULT_HEADERS)
    if headers:
        req_headers.update(headers)
    if extra_headers:
        req_headers.update(extra_headers)

    # 1. Try curl_cffi first with Chrome 124 session
    session = get_curl_session()
    if session:
        for attempt in range(2):
            try:
                resp = session.get(url, headers=req_headers, timeout=timeout)
                if resp.status_code == 200:
                    return resp.text
                elif resp.status_code == 429:
                    logger.warning("curl_cffi HTTP 429 (Rate Limited) for %s, retrying after 1.5s", url)
                    time.sleep(1.5)
                    continue
                elif resp.status_code != 404:
                    logger.warning("curl_cffi HTTP %d for %s", resp.status_code, url)
                    break
            except Exception as e:
                logger.debug("curl_cffi failed for %s: %s", url, e)
                break

    # 2. Fallback to standard requests session
    std_s = get_std_session()
    for attempt in range(2):
        try:
            resp = std_s.get(url, headers=req_headers, timeout=timeout)
            if resp.status_code == 200:
                return resp.text
            elif resp.status_code == 429:
                logger.warning("std_requests HTTP 429 for %s, retrying after 1.5s", url)
                time.sleep(1.5)
                continue
            logger.warning("std_requests HTTP %d for %s", resp.status_code, url)
            break
        except Exception as e:
            logger.warning("std_requests failed for %s: %s", url, e)
            break

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
    req_headers["X-Requested-With"] = "XMLHttpRequest"
    req_headers["Accept"] = "application/json, text/javascript, */*; q=0.01"
    req_headers["Sec-Fetch-Dest"] = "empty"
    req_headers["Sec-Fetch-Mode"] = "cors"
    if headers:
        req_headers.update(headers)

    session = get_curl_session()
    if session:
        for attempt in range(2):
            try:
                resp = session.get(url, headers=req_headers, timeout=timeout)
                if resp.status_code == 200:
                    return resp.json()
                elif resp.status_code == 429:
                    logger.warning("curl_cffi json HTTP 429 for %s, retrying after 1.5s", url)
                    time.sleep(1.5)
                    continue
            except Exception as e:
                logger.debug("curl_cffi json failed for %s: %s", url, e)
                break

    std_s = get_std_session()
    for attempt in range(2):
        try:
            resp = std_s.get(url, headers=req_headers, timeout=timeout)
            if resp.status_code == 200:
                return resp.json()
            elif resp.status_code == 429:
                time.sleep(1.5)
                continue
        except Exception as e:
            logger.warning("std_requests json failed for %s: %s", url, e)
            break

    return None
