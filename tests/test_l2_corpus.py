"""L2 — parametrized over every case in corpus_attacks.yaml.

Add a row to the YAML and it is picked up automatically, with no test-code changes
— Retrieval and generation are tested separately, which materializes the two metrics:

  - retrieval (RSR) is diagnostic: a poisoned document may legitimately not reach the
  top-k, and that alone does not mean the system is safe;
  - generation (GCR) carries the hard security assertion: the user-facing damage.
"""
import pytest

from tests.metrics import canary_in_answer, poison_in_topk

@pytest.mark.l2
def test_retrieval_diagnostic(case, retrieve_fn):
    # Diagnostic only (RSR). Not a security gate: skip when the poison does not
    # reach the top-k, so the report shows per-case retrievability without failing.
    chunks = retrieve_fn(case["trigger_prompt"])
    ids = [c["id"] for c in chunks]
    if not poison_in_topk(case, ids):
        pytest.skip(f"[{case['id']}] veneno NO recuperado en el top-k (RSR=0 para este caso)")


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
