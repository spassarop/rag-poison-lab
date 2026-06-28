"""Ingestion-time defenses: signature scanning (+ optional Veritensor) and the
perplexity-style anomaly filter. Applied before chunks enter the vector store.

Pedagogical point (made explicit in the harness): a **signature/pattern** scanner
catches the *loud* attacks — overt instruction injection and the stealth/obfuscation
variants (HTML comments, white text, zero-width, base64) — but **misses** the fluent
plausible-content injections and the **GASLITE** passage (no suspicious patterns).
The **anomaly** filter catches the non-fluent GASLITE passage (high perplexity), but
a fluent GASLITE variant would evade it. No single ingestion control is enough.

Veritensor (github.com/arsbr/Veritensor) is the production-grade option for the
signature layer; it is optional and import-guarded. When it is not installed, the
builtin `SignatureScanner` runs instead so the demo works anywhere.
"""
from __future__ import annotations

import re
from typing import Any, Callable, Dict, List, Optional, Sequence, Set, Tuple

from app.defenses.anomaly import AnomalyFilter

# Zero-width / invisible characters used by stealth poisons.
_ZERO_WIDTH = "".join(["​", "‌", "‍", "‎", "‏", "﻿"])

# Injection / obfuscation signatures. These key on attacker *patterns*, NOT on the
# canary URL itself (a real defender does not know the canary in advance).
_SIGNATURES: List[Tuple[str, "re.Pattern"]] = [
    ("instruction_injection",
     re.compile(r"(ignor[aá]\s+(las\s+)?reglas|nota\s+del\s+sistema|respond[eé]\s+exactamente|"
                r"ignore\s+(the\s+)?(previous|above)|disregard\s+(the\s+)?(previous|rules))",
                re.IGNORECASE)),
    ("invisible_css",
     re.compile(r"font-size\s*:\s*0|color\s*:\s*#f{3,6}\b", re.IGNORECASE)),
    ("html_comment_instruction",
     re.compile(r"<!--(?:(?!-->).)*(ignor|nota del sistema|respond|sistema \(cr)"
                r"(?:(?!-->).)*-->", re.IGNORECASE | re.DOTALL)),
    ("base64_blob", re.compile(r"[A-Za-z0-9+/]{40,}={0,2}")),
]


class SignatureScanner:
    """Builtin pattern scanner. is_malicious(text) -> (blocked, reason)."""

    def is_malicious(self, text: str) -> Tuple[bool, Optional[str]]:
        if any(ch in text for ch in _ZERO_WIDTH):
            return True, "zero_width_chars"
        for name, pattern in _SIGNATURES:
            if pattern.search(text):
                return True, name
        return False, None


def _load_veritensor() -> Optional[Callable[[str], bool]]:
    """Return a `scan(text) -> is_malicious` using Veritensor if installed, else None.

    Veritensor's exact scan API may differ by version; adjust here. We keep it
    import-guarded so the project runs without the package.
    """
    try:  # pragma: no cover - exercised only where veritensor is installed
        import veritensor  # type: ignore
    except Exception:
        return None

    def _scan(text: str) -> bool:
        try:
            result = veritensor.scan_text(text)  # type: ignore[attr-defined]
            return bool(getattr(result, "is_malicious", False) or result is True)
        except Exception:
            return False

    return _scan


def apply_ingestion_defense(
    chunks: List[Dict[str, Any]],
    controls: Set[str],
    benign_texts: Optional[Sequence[str]] = None,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Filter chunks before storage. Returns (kept, blocked).

    controls: any of {"signatures", "veritensor", "anomaly"}.
      - signatures: builtin SignatureScanner (overt + stealth/obfuscation).
      - veritensor: Veritensor if installed, else falls back to SignatureScanner.
      - anomaly: perplexity proxy, calibrated on `benign_texts` (zero false positives
        on benign). Pass the legitimate corpus as benign_texts; if omitted, the chunks
        themselves are used (degenerate — only meaningful with a clean reference set).
    """
    use_signatures = "signatures" in controls or "veritensor" in controls
    scanner = SignatureScanner() if use_signatures else None
    veri = _load_veritensor() if "veritensor" in controls else None

    anomaly: Optional[AnomalyFilter] = None
    if "anomaly" in controls:
        anomaly = AnomalyFilter()
        anomaly.calibrate(list(benign_texts) if benign_texts else [c["text"] for c in chunks])

    kept: List[Dict[str, Any]] = []
    blocked: List[Dict[str, Any]] = []
    for c in chunks:
        text = c["text"]
        reason: Optional[str] = None
        if veri is not None and veri(text):
            reason = "veritensor"
        elif scanner is not None:
            hit, sig = scanner.is_malicious(text)
            if hit:
                reason = f"signature:{sig}"
        if reason is None and anomaly is not None:
            flagged, score = anomaly.is_anomalous(text)
            if flagged:
                reason = f"anomaly:perplexity({score:.2f}>thr)"
        if reason is not None:
            blocked.append({**c, "blocked_reason": reason})
        else:
            kept.append(c)
    return kept, blocked
