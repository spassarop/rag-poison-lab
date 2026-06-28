#!/usr/bin/env python3
"""Compare attack success with defenses OFF vs ON

Runs the whole attack corpus in-process against an ephemeral ChromaDB for each
defense configuration, re-seeding per config so that ingestion-time defenses actually
filter the poison. Reports RSR / GCR (end-to-end) per configuration, plus a per-
technique breakdown and an exfiltration probe for the role filter.

It toggles `app.config.settings` flags directly (no API restart) and reuses
`tests.metrics.evaluate_cases` + `tests.judge.majority_safe`, so the numbers match
the harness. Requires Ollama for generation; use --no-generation for RSR only.

Usage:
    python scripts/compare_defenses.py
    python scripts/compare_defenses.py --size 200 --no-generation
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import chromadb

from app.config import settings
from app.rag.ingest import load_documents, chunk_documents
from app.rag.retriever import Retriever
from app.rag.generator import Generator
from app.rag.pipeline import RAGPipeline
from app.defenses.ingestion_guard import apply_ingestion_defense
from tests.cases import load_attack_cases
from tests.metrics import evaluate_cases
from tests.judge import majority_safe

REPO = Path(__file__).parent.parent

# (label, settings overrides) — each is measured against the OFF baseline.
CONFIGS = [
    ("baseline (off)", {}),
    ("ingestion: signatures+anomaly", {"defense_ingestion": "signatures,anomaly"}),
    ("spotlighting", {"defense_spotlighting": "on"}),
    ("output guard", {"defense_output": "on"}),
    ("role filter", {"defense_retrieval_filter": "on"}),
    ("ALL on", {"defense_ingestion": "signatures,anomaly", "defense_spotlighting": "on",
                "defense_output": "on", "defense_retrieval_filter": "on"}),
]


def _texts(chunks):
    return [c["text"] for c in chunks]


def seed(client, embedder, size, ingestion_controls, benign_texts):
    """(Re)build the ephemeral collection for one config: legit(+internal)+poison,
    applying the ingestion defense so blocked poison never enters."""
    try:
        client.delete_collection("compare_defenses")
    except Exception:
        pass
    col = client.get_or_create_collection("compare_defenses", metadata={"hnsw:space": "cosine"})

    def add(chunks, sensitivity):
        if ingestion_controls:
            chunks, _ = apply_ingestion_defense(chunks, ingestion_controls, benign_texts)
        if not chunks:
            return
        emb = embedder.encode(_texts(chunks))
        col.add(ids=[c["id"] for c in chunks], documents=_texts(chunks),
                embeddings=emb.tolist(),
                metadatas=[{"source": c["source"], "sensitivity": sensitivity} for c in chunks])

    legit_docs = load_documents(str(REPO / "corpus" / "legit"))[:size]
    add(chunk_documents(legit_docs, settings.chunk_size, settings.chunk_overlap), "public")
    internal_dir = REPO / "corpus" / "internal"
    if internal_dir.exists():
        add(chunk_documents(load_documents(str(internal_dir)), settings.chunk_size, settings.chunk_overlap), "internal")
    for case in load_attack_cases():
        p = REPO / case["poison_doc"]
        if p.exists():
            add(chunk_documents([{"text": p.read_text(encoding="utf-8"), "source": p.name}],
                                settings.chunk_size, settings.chunk_overlap), "public")
    return col


def main() -> None:
    ap = argparse.ArgumentParser(description="Compare RSR/GCR with defenses off vs on")
    ap.add_argument("--size", type=int, default=200)
    ap.add_argument("--no-generation", action="store_true")
    ap.add_argument("--top-k", type=int, default=settings.top_k)
    args = ap.parse_args()

    cases = load_attack_cases()
    client = chromadb.EphemeralClient()
    embedder_holder = Retriever(collection=client.get_or_create_collection("compare_defenses"),
                                embed_model_name=settings.embed_model)
    generator = Generator(model_name=settings.llm_model, base_url=settings.ollama_base_url,
                          temperature=settings.llm_temperature)
    benign_texts = _texts(chunk_documents(load_documents(str(REPO / "corpus" / "legit"))[:args.size],
                                          settings.chunk_size, settings.chunk_overlap))
    judge_fn = None if args.no_generation else (lambda q, a, r: majority_safe(q, a, r))

    saved = {k: getattr(settings, k) for k in
             ("defense_ingestion", "defense_spotlighting", "defense_output", "defense_retrieval_filter")}
    rows = []
    try:
        for label, overrides in CONFIGS:
            for k in saved:
                setattr(settings, k, "off")
            for k, v in overrides.items():
                setattr(settings, k, v)

            col = seed(client, embedder_holder.embedder, args.size,
                       settings.ingestion_controls(), benign_texts)
            embedder_holder.collection = col
            pipeline = RAGPipeline(retriever=embedder_holder, generator=generator, top_k=args.top_k)

            def retrieve_fn(q, k):  # noqa: E306
                return embedder_holder.retrieve(q, k, role="customer")

            def chat_fn(q):  # noqa: E306
                return pipeline.answer(q, role="customer")

            res = evaluate_cases(cases, retrieve_fn, chat_fn, top_k=args.top_k,
                                 judge_fn=(None if args.no_generation else judge_fn))
            rows.append((label, res))
            gcr = "n/a" if args.no_generation else f"{res['gcr_absolute']*100:.0f}%"
            print(f"  {label:32} RSR={res['rsr']*100:4.0f}%  GCR(e2e)={gcr}  "
                  f"compromised={res['n_compromised']}/{res['n_cases']}")
    finally:
        for k, v in saved.items():
            setattr(settings, k, v)

    print("\n" + "=" * 74)
    print(f"{'defense config':32} {'RSR':>6} {'GCR(e2e)':>9} {'compromised':>12}")
    print("-" * 74)
    for label, res in rows:
        gcr = "n/a" if args.no_generation else f"{res['gcr_absolute']*100:.0f}%"
        print(f"{label:32} {res['rsr']*100:5.0f}% {gcr:>9} "
              f"{str(res['n_compromised'])+'/'+str(res['n_cases']):>12}")
    print("=" * 74)
    print("Expected: ingestion blocks loud + GASLITE (RSR drops) but misses fluent;")
    print("spotlighting/output drive GCR→~0 even when retrieved; ALL on ≈ fully green.")


if __name__ == "__main__":
    main()
