"""Output guard: the last line of defense — scan the generated answer before it
reaches the user.

Policy: a support bot should only surface **official Cocina Cloud** links. Any other
(external) URL is redacted and the answer is flagged unsafe. The guard does NOT know
the test canary — that would be unrealistic; the canary is caught simply because it is
an external, non-official URL. (The canary string is the *test* oracle, used by the
metrics, not by this defense.)
"""
from __future__ import annotations

import re
from typing import Tuple

# External URLs are blocked unless the host is an official Cocina Cloud domain.
_URL_RE = re.compile(r"https?://[^\s)>\]\"']+", re.IGNORECASE)
_OFFICIAL_HOST_RE = re.compile(r"(^|\.)(cocinacloud\.io|api\.cocinacloud\.io)$", re.IGNORECASE)
_REDACTED = "[enlace externo bloqueado]"


def _host(url: str) -> str:
    m = re.match(r"https?://([^/]+)", url, re.IGNORECASE)
    return (m.group(1) if m else "").split(":")[0].lower()


def scan_output(answer: str) -> Tuple[bool, str]:
    """Return (is_safe, sanitized_answer).

    Unsafe if the answer contains any external URL whose host is not an official
    Cocina Cloud domain; such URLs are redacted in place.
    """
    if not answer:
        return True, answer or ""

    unsafe = False

    def _redact(match: "re.Match") -> str:
        nonlocal unsafe
        url = match.group(0)
        if _OFFICIAL_HOST_RE.search(_host(url)):
            return url  # official link allowed
        unsafe = True
        return _REDACTED

    sanitized = _URL_RE.sub(_redact, answer)
    return (not unsafe), sanitized
