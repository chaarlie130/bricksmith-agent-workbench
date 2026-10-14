"""Live search and file fetch against the LDraw Official Model Repository
(library.ldraw.org).

Anonymous, unauthenticated HTTP only -- no credentials are stored or
required. This covers most officially released LEGO sets, not every set
LEGO has ever made. Fetched files are real third-party designs with licenses
this module does not verify; treat results as reference data, not as
permission to copy a design verbatim into a submitted build.
"""
from __future__ import annotations

import html
import json
import re
from dataclasses import dataclass
from http.cookiejar import CookieJar
from urllib.error import HTTPError, URLError
from urllib.request import HTTPCookieProcessor, Request, build_opener

BASE = "https://library.ldraw.org"
OMR_PAGE = f"{BASE}/omr"
# The hash-like segment below is an app-build identifier baked into the
# Livewire JS bundle, not a secret. If requests start failing, re-derive it
# by loading OMR_PAGE and grepping for `livewire-[a-f0-9]+` in the HTML.
LIVEWIRE_UPDATE = f"{BASE}/livewire-c8d7718a/update"
FILE_URL = f"{BASE}/library/omr/{{model_number}}.mpd"

LICENSE_NOTE = (
    "Fetched from the live LDraw Official Model Repository. This is a "
    "real third-party design; its license is not verified by this tool. "
    "Use as reference data for study, not as permission to copy verbatim "
    "into a submitted design. OMR covers most, not all, officially "
    "released sets."
)

_CSRF_RE = re.compile(r'name="csrf-token"\s+content="([^"]+)"')
_SNAPSHOT_RE = re.compile(r'wire:snapshot="([^"]+)"')
_MODEL_NUMBER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


@dataclass
class OmrResult:
    model_id: str
    title: str
    model_number: str
    thumbnail_url: str | None


def _opener():
    return build_opener(HTTPCookieProcessor(CookieJar()))


_USER_AGENT = (
    "Mozilla/5.0 (compatible; BrickSmithWorkbench/1.0; "
    "+https://github.com/)"
)


def _get_text(opener, url: str, timeout: float) -> str:
    request = Request(url, headers={"Accept": "text/html", "User-Agent": _USER_AGENT})
    try:
        with opener.open(request, timeout=timeout) as response:
            return response.read().decode("utf-8", errors="replace")
    except (HTTPError, URLError) as exc:
        # Deliberately omit response bodies: unexpected error pages may be large or noisy.
        raise RuntimeError(f"LDraw OMR request failed ({exc})") from exc


def search_omr(query: str, *, limit: int = 10, timeout: float = 15.0) -> list[OmrResult]:
    """Search the live LDraw OMR library for real LEGO sets by name/keyword."""
    query = query.strip()[:160]
    if not query:
        raise ValueError("query must not be empty")
    limit = min(max(int(limit), 1), 25)

    opener = _opener()
    page_html = _get_text(opener, OMR_PAGE, timeout)

    csrf_match = _CSRF_RE.search(page_html)
    snapshot_match = _SNAPSHOT_RE.search(page_html)
    if not csrf_match or not snapshot_match:
        raise RuntimeError("Could not locate LDraw OMR search form on the page; site layout may have changed")
    token = csrf_match.group(1)
    snapshot = html.unescape(snapshot_match.group(1))

    payload = json.dumps({
        "_token": token,
        "components": [{
            "snapshot": snapshot,
            "updates": {"tableSearch": query},
            "calls": [],
        }],
    }).encode("utf-8")

    request = Request(
        LIVEWIRE_UPDATE,
        data=payload,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-Livewire": "true",
            "Referer": OMR_PAGE,
            "User-Agent": _USER_AGENT,
        },
    )
    try:
        with opener.open(request, timeout=timeout) as response:
            body = json.load(response)
    except (HTTPError, URLError) as exc:
        raise RuntimeError(f"LDraw OMR search request failed ({exc})") from exc

    try:
        result_html = body["components"][0]["effects"]["html"]
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError("Unexpected LDraw OMR search response shape") from exc

    return _parse_results(result_html)[:limit]


_ITEM_START_RE = re.compile(r'href="https://library\.ldraw\.org/omr/sets/(?P<id>\d+)"')
_THUMB_RE = re.compile(r'src="([^"]+)"')
_TITLE_RE = re.compile(r'<p[^>]*>\s*([^<]+?)\s*</p>')
_MODEL_NUMBER_BLOCK_RE = re.compile(r'<p[^>]*font-mono[^>]*>\s*([^<]+?)\s*</p>')
_ITEM_BLOCK_SIZE = 2000  # generous upper bound on one result card's markup


def _parse_results(result_html: str) -> list[OmrResult]:
    starts = list(_ITEM_START_RE.finditer(result_html))
    results: list[OmrResult] = []
    for index, start in enumerate(starts):
        end = starts[index + 1].start() if index + 1 < len(starts) else len(result_html)
        block = result_html[start.start():min(end, start.start() + _ITEM_BLOCK_SIZE)]

        title_match = _TITLE_RE.search(block)
        model_number_match = _MODEL_NUMBER_BLOCK_RE.search(block)
        if not title_match or not model_number_match:
            continue
        thumb_match = _THUMB_RE.search(block)

        results.append(OmrResult(
            model_id=start.group("id"),
            title=html.unescape(title_match.group(1)).strip(),
            model_number=html.unescape(model_number_match.group(1)).strip(),
            thumbnail_url=thumb_match.group(1) if thumb_match else None,
        ))
    return results


def fetch_omr_file(model_number: str, *, timeout: float = 20.0, max_chars: int = 200_000) -> str:
    """Fetch the raw LDraw (.ldr/.mpd) text for an OMR set by model number."""
    model_number = model_number.strip()
    if not _MODEL_NUMBER_RE.match(model_number):
        raise ValueError("model_number must look like '21006-1'")

    request = Request(FILE_URL.format(model_number=model_number),
                       headers={"Accept": "text/plain", "User-Agent": _USER_AGENT})
    try:
        with build_opener().open(request, timeout=timeout) as response:
            text = response.read().decode("utf-8", errors="replace")
    except (HTTPError, URLError) as exc:
        raise RuntimeError(f"LDraw OMR file fetch failed for {model_number} ({exc})") from exc

    if len(text) > max_chars:
        text = text[:max_chars] + "\n0 // [truncated by fetch_omr_set -- file exceeds preview size]\n"
    return text
