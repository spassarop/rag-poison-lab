"""Runtime semantic output guard (DEFENSE_SEMANTIC_OUTPUT).

The deterministic output guard only blocks external URLs, so it cannot stop knowledge
corruption (a false fact with no link — unsafe food advice, a wrong allergen claim,
etc.). This guard runs the LLM judge on the final answer with a GENERIC safety rubric
(it does not know the attack/case — only the question and answer) and replaces an
unsafe answer with a safe refusal.

Trade-off (why it ships off by default): it adds an extra LLM call per answer
(latency) and the judge is non-deterministic — the same reasons L3 stays a
non-blocking detection layer in CI rather than a hard gate. As a runtime control it
*reduces*, it does not *eliminate*.
"""
from __future__ import annotations

from typing import Tuple

from app.defenses.llm_judge import majority_safe

SAFE_REPLACEMENT = (
    "No puedo confirmar esa información con seguridad. Te recomiendo verificarla en una "
    "fuente oficial de Cocina Cloud o con un profesional."
)


def scan_semantic(question: str, answer: str) -> Tuple[bool, str]:
    """Return (is_safe, sanitized_answer). Replaces an unsafe answer with a refusal."""
    if not answer:
        return True, answer or ""
    safe = majority_safe(question, answer)
    return (safe, answer if safe else SAFE_REPLACEMENT)
