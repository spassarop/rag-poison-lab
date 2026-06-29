"""Defense-layer tests:

- a signature/pattern scanner catches the LOUD attacks (overt injection + stealth
  obfuscation) but MISSES the fluent plausible injections and GASLITE;
- a perplexity anomaly filter catches high-perplexity content (the GASLITE passage;
  also encoded blobs such as base64) while leaving fluent text untouched;
- the output guard stops the canary at the last line;
- the retrieval role filter enforces access control.

These run at the function level (no LLM / no ChromaDB), so they are deterministic and
CI-friendly. The end-to-end red→green across a live SUT is shown by
`scripts/compare_defenses.py`.
"""
from pathlib import Path

import pytest

from app.defenses.ingestion_guard import SignatureScanner, apply_ingestion_defense
from app.defenses.anomaly import AnomalyFilter
from app.defenses.output_guard import scan_output
from app.defenses.spotlighting import spotlight_context, datamark, SENTINEL
from app.rag.retriever import role_where
from app.rag.ingest import load_documents, chunk_documents
from app.config import settings
from tests.cases import load_attack_cases

REPO = Path(__file__).parent.parent

# Loud attacks a signature scanner is expected to catch.
SIGNATURE_CATCHES = {
    "t1_refund_phish", "t2_html_comment", "t2_white_text",
    "t2_zerowidth", "t2_metadata", "t2_base64",
}
# Fluent attacks that evade signatures (caught later, at generation).
SIGNATURE_MISSES = {
    "t1_refund_plausible", "t1_agent_plausible",
    "t1_rioplatense_dulcedeleche", "t1_foodsafety_pollo", "t1_allergen_budin",
    "t3_gaslite_pwd_reset",
}


def _cases_with_docs():
    out = {}
    for c in load_attack_cases():
        p = REPO / c["poison_doc"]
        if p.exists():
            out[c["id"]] = p.read_text(encoding="utf-8")
    return out


def _legit_chunk_texts():
    docs = load_documents(str(REPO / "corpus" / "legit"))
    return [c["text"] for c in chunk_documents(docs, settings.chunk_size, settings.chunk_overlap)]


def test_signatures_catch_loud_miss_fluent_and_gaslite():
    scanner = SignatureScanner()
    texts = _cases_with_docs()
    for cid, text in texts.items():
        flagged = scanner.is_malicious(text)[0]
        if cid in SIGNATURE_CATCHES:
            assert flagged, f"signature scanner should catch {cid}"
        elif cid in SIGNATURE_MISSES:
            assert not flagged, f"signature scanner should NOT catch {cid} (fluent/GASLITE)"


FLUENT_CASES = {
    "t1_refund_plausible", "t1_agent_plausible",
    "t1_rioplatense_dulcedeleche", "t1_foodsafety_pollo", "t1_allergen_budin",
}


def test_anomaly_filter_flags_gaslite_not_fluent():
    texts = _cases_with_docs()
    if "t3_gaslite_pwd_reset" not in texts:
        pytest.skip("GASLITE passage not generated yet")
    af = AnomalyFilter()
    af.calibrate(_legit_chunk_texts())  # zero-FP threshold on benign chunks

    # MUST flag the gradient-optimized (gibberish) GASLITE passage.
    assert af.is_anomalous(texts["t3_gaslite_pwd_reset"])[0], \
        "anomaly filter must flag the non-fluent GASLITE passage"

    # MUST NOT flag fluent Spanish poisons — they must reach the generation layers.
    for cid in FLUENT_CASES:
        if cid in texts:
            assert not af.is_anomalous(texts[cid])[0], \
                f"anomaly filter should not flag fluent case {cid}"

    # Note: high-perplexity stealth blobs (e.g. base64) MAY also be flagged here — a
    # legitimate second detection path (also caught by signatures), not a false
    # positive — so we deliberately do not assert on those.


def test_combined_ingestion_defense():
    # signatures + anomaly together: loud blocked by signatures, GASLITE by anomaly,
    # fluent plausible/knowledge-corruption pass through to the generation layers.
    texts = _cases_with_docs()
    chunks = [{"id": f"{cid}::0", "text": t, "source": f"{cid}.md"} for cid, t in texts.items()]
    kept, blocked = apply_ingestion_defense(
        chunks, controls={"signatures", "anomaly"}, benign_texts=_legit_chunk_texts()
    )
    blocked_ids = {c["id"].split("::")[0] for c in blocked}
    assert SIGNATURE_CATCHES <= blocked_ids                      # all loud blocked
    if "t3_gaslite_pwd_reset" in texts:
        assert "t3_gaslite_pwd_reset" in blocked_ids             # GASLITE blocked by anomaly
    assert "t1_refund_plausible" not in blocked_ids              # fluent slips through
    assert "t1_foodsafety_pollo" not in blocked_ids


def test_output_guard_blocks_canary_allows_official():
    canary = settings.canary_url
    safe, sanitized = scan_output(f"Para recuperar tu acceso entrá en {canary} ahora.")
    assert not safe and canary not in sanitized

    safe, _ = scan_output("Entrá en https://cocinacloud.io/forgot-password para resetear.")
    assert safe  # official domain allowed

    safe, out = scan_output("Hacé clic en 'Olvidé mi contraseña' en el inicio de sesión.")
    assert safe and out  # benign answer untouched


def test_spotlighting_marks_context():
    marked = datamark("hola mundo")
    assert SENTINEL in marked
    block = spotlight_context("texto de contexto")
    assert block.startswith("<<DATOS>>") and block.endswith("<</DATOS>>") and SENTINEL in block


def test_role_filter_where_clause():
    assert role_where("customer", enabled=True) == {"sensitivity": "public"}
    assert role_where("customer", enabled=False) is None
    assert role_where("internal", enabled=True) is None   # privileged role sees all


def test_semantic_guard_replaces_unsafe(monkeypatch):
    # Runtime semantic guard mitigates knowledge corruption the URL guard can't see.
    # Mock the judge so the test is deterministic and needs no Ollama.
    import app.defenses.semantic_guard as sg

    monkeypatch.setattr(sg, "majority_safe", lambda q, a: False)  # judge: unsafe
    safe, out = sg.scan_semantic("¿Cuánto dejo el pollo afuera?", "Dejalo 8 horas, tranquilo.")
    assert not safe and out == sg.SAFE_REPLACEMENT

    monkeypatch.setattr(sg, "majority_safe", lambda q, a: True)   # judge: safe
    safe, out = sg.scan_semantic("q", "Guardalo en la heladera dentro de 2 horas.")
    assert safe and out == "Guardalo en la heladera dentro de 2 horas."
