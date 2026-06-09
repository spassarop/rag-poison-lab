"""L3 — semantic evaluation via LLM-as-judge.

Covers attack cases that carry a `judge_rubric` (knowledge corruption with no fixed
canary). It is non-deterministic, so it uses majority voting and is marked `l3`:
run it as a SEPARATE, non-blocking job. The hard CI gate stays on L1.

`case` is parametrized by pytest_generate_tests in conftest.py (shared with L2).
"""
import pytest

from tests.judge import majority_safe


@pytest.mark.l3
def test_generation_semantically_safe(case, chat_fn):
    rubric = case.get("judge_rubric")
    if not rubric:
        pytest.skip(f"[{case['id']}] caso sin judge_rubric — no aplica L3")
    resp = chat_fn(case["trigger_prompt"])
    assert majority_safe(case["trigger_prompt"], resp["answer"], rubric), (
        f"L3: el juez marcó la respuesta como INSEGURA "
        f"[{case['id']} | {case['technique']} | {case['owasp']}]\n"
        f"Pregunta: {case['trigger_prompt']}\n"
        f"Respuesta: {resp['answer']}"
    )
