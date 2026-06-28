"""Defense-layer tests:

- a signature/pattern scanner catches the LOUD attacks (overt injection + stealth
  obfuscation) but MISSES the fluent plausible injections and GASLITE;
- a perplexity anomaly filter catches the non-fluent GASLITE passage ONLY;
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


def test_anomaly_filter_flags_only_gaslite():
    texts = _cases_with_docs()
    if "t3_gaslite_pwd_reset" not in texts:
        pytest.skip("GASLITE passage not generated yet")
    af = AnomalyFilter()
    af.calibrate(_legit_chunk_texts())  # zero-FP threshold on benign chunks
    for cid, text in texts.items():
        flagged = af.is_anomalous(text)[0]
        if cid == "t3_gaslite_pwd_reset":
            assert flagged, "anomaly filter must flag the non-fluent GASLITE passage"
        else:
            assert not flagged, f"anomaly filter should not flag fluent case {cid}"


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
