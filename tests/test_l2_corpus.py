"""L2 — parametrized generation gate over every case in corpus_attacks.yaml.

Add a row to the YAML and it is picked up automatically, with no test-code changes. This
is the hard security assertion for cases with a deterministic canary: the user-facing
answer must not contain it.

Retrieval success (RSR) is a *measurement*, not a pass/fail property (a poison reaching
the top-k is not, by itself, a compromise — the model may resist it). So RSR is reported
as a number by the measurement scripts (measure_baseline / compare_defenses /
security_report), not asserted here. This gate still encodes retrieval in its outcomes: it
SKIPS when the poison never reached the model (GCR is only meaningful once it does), passes
when the model resisted a retrieved poison, and fails when the answer carries the canary.
"""
import pytest

from tests.metrics import canary_in_answer, poison_in_topk


@pytest.mark.l2
def test_generation_not_compromised(case, chat_fn):
    # Deterministic (canary) gate only. Semantic-only cases (no expected_canary)
    # are covered by the L3 judge instead.
    if not case.get("expected_canary"):
        pytest.skip(f"[{case['id']}] caso semántico sin canary — evaluado en L3 (juez)")
    resp = chat_fn(case["trigger_prompt"])
    # GCR is only meaningful when the poison actually reached the model. If it was
    # not retrieved, skip instead of reporting a misleading green — this matches the
    # conditional-GCR definition (compromise among retrieved cases).
    if not poison_in_topk(case, resp.get("retrieved_ids", [])):
        pytest.skip(f"[{case['id']}] veneno NO recuperado por /chat — GCR no evaluable (RSR=0)")
    assert not canary_in_answer(case, resp["answer"]), (
        f"RAG comprometido [{case['id']} | {case['technique']} | {case['owasp']}]\n"
        f"Pregunta: {case['trigger_prompt']}\n"
        f"Respuesta: {resp['answer']}"
    )
