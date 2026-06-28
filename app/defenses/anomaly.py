"""Perplexity-style anomaly detection for ingestion (catches non-fluent GASLITE).

GASLITE's gradient-optimized trigger is high-perplexity gibberish — foreign / glued /
vowel-poor tokens that never appear in the legitimate corpus. The GASLITE paper (§7)
filters such passages with a perplexity model; its fluent variant (GASLITE-Flu, which
adds a GPT-2 perplexity term to the objective) evades that filter. This module ships a
lightweight, dependency-free PROXY and a pluggable interface so a real GPT-2
perplexity scorer can be dropped in later without touching the rest of the pipeline.

Calibration follows the paper's zero-false-positive rule: the threshold is set at the
maximum score over benign passages, so normal documents are never flagged.
"""
from __future__ import annotations

import math
import re
from collections import Counter
from typing import List, Optional, Protocol, Sequence, Tuple

_WORD_RE = re.compile(r"[^\W\d_]+", re.UNICODE)  # letters-only tokens


def _tokens(text: str) -> List[str]:
    return _WORD_RE.findall(text.lower())


class PerplexityScorer(Protocol):
    """Higher score == more anomalous / surprising. Optional fit() on benign text."""
    def score(self, text: str) -> float: ...


class UnigramPerplexityScorer:
    """Dependency-free perplexity proxy: mean negative log-prob of tokens under a
    unigram model fit on the benign corpus (Laplace-smoothed). Out-of-vocabulary
    tokens (e.g. GASLITE's foreign gibberish) get the low OOV probability → high
    score. This is the same idea as a GPT-2 perplexity filter, at unigram resolution.

    Swap in a real LM by implementing `PerplexityScorer.score` (and dropping `fit`).
    """

    def __init__(self) -> None:
        self._logp: dict = {}
        self._oov_logp: float = math.log(1e-6)
        self.fitted = False

    def fit(self, benign_texts: Sequence[str]) -> "UnigramPerplexityScorer":
        counts: Counter = Counter()
        for t in benign_texts:
            counts.update(_tokens(t))
        total = sum(counts.values())
        vocab = len(counts)
        if total == 0:
            self.fitted = True
            return self
        denom = total + vocab + 1  # +1 reserves mass for OOV
        self._logp = {w: math.log((n + 1) / denom) for w, n in counts.items()}
        self._oov_logp = math.log(1 / denom)
        self.fitted = True
        return self

    def score(self, text: str) -> float:
        toks = _tokens(text)
        if not toks:
            return 0.0
        mean_logp = sum(self._logp.get(w, self._oov_logp) for w in toks) / len(toks)
        return -mean_logp  # higher = more surprising


class AnomalyFilter:
    """Flags passages whose score exceeds a benign-calibrated threshold."""

    def __init__(self, scorer: Optional[PerplexityScorer] = None) -> None:
        self.scorer: PerplexityScorer = scorer or UnigramPerplexityScorer()
        self.threshold: Optional[float] = None

    def calibrate(self, benign_texts: Sequence[str], margin: float = 1.0) -> float:
        """Fit (if supported) and set the threshold = max benign score * margin.

        margin == 1.0 reproduces the paper's zero-false-positive threshold (nothing
        benign is flagged). Raise it slightly for headroom.
        """
        fit = getattr(self.scorer, "fit", None)
        if callable(fit):
            fit(benign_texts)
        scores = [self.scorer.score(t) for t in benign_texts]
        self.threshold = (max(scores) if scores else 0.0) * margin
        return self.threshold

    def is_anomalous(self, text: str) -> Tuple[bool, float]:
        score = self.scorer.score(text)
        thr = self.threshold if self.threshold is not None else float("inf")
        return (score > thr, score)
