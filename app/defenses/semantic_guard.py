"""Runtime semantic output guard (DEFENSE_SEMANTIC_OUTPUT).

The deterministic output guard only blocks external URLs, so it cannot stop knowledge
corruption (a false fact with no link — unsafe food advice, a wrong allergen claim, a
disputed origin stated as certain). This guard runs the LLM judge on the final answer
with a GENERIC safety rubric (it does not know the attack/case — only the question and
answer) and replaces an unsafe answer with a safe refusal.

Detection vs mitigation — why this does NOT use `majority_safe`:
  The L3 tests use `majority_safe` (majority vote) because a test wants a *stable*
  per-case signal. A runtime guard instead wants to *err toward caution*: a clean,
  confident poisoned answer (e.g. a bare "X es originario de Y", with no citations
  once the system prompt was tightened for UX) makes a small judge's verdict noisy, so a
  majority vote can let it through. The guard therefore uses **conservative
  aggregation**: the answer is unsafe if ANY of n independent judgments flags it. This
  trades a small chance of over-refusing a borderline-but-fine answer (replaced by a
  cautious "verify with an official source") for reliably catching the corruption — the
  right trade for a mitigation.

Trade-off (why it ships off by default): it adds n LLM calls per answer (latency) and
the judge is non-deterministic. As a runtime control it *reduces*, it does not
*eliminate*.
"""
from __future__ import annotations

from typing import Tuple

from app.defenses.llm_judge import panel_verdicts

SAFE_REPLACEMENT = (
    "No puedo confirmar esa información con seguridad. Te recomiendo verificarla en una "
    "fuente oficial de Cocina Cloud o con un profesional."
)


def _answer_is_safe(question: str, answer: str) -> bool:
    """Conservative panel verdict: safe only if EVERY judge in the panel agrees it is safe
    (i.e. unsafe if ANY model flags it — 'minority alert'). Diverse models give independent
    opinions; mitigation errs toward caution."""
    verdicts = panel_verdicts(question, answer)
    return all(v.safe for v in verdicts) if verdicts else True


def scan_semantic(question: str, answer: str) -> Tuple[bool, str]:
    """Return (is_safe, sanitized_answer). Replaces an unsafe answer with a refusal."""
    if not answer:
        return True, answer or ""
    safe = _answer_is_safe(question, answer)
    return (safe, answer if safe else SAFE_REPLACEMENT)
