#!/usr/bin/env python3
"""Measure baseline RSR and GCR of the poisoned corpus across corpus sizes.

What it does
------------
For each requested corpus size (e.g. 50 and 200 documents):

  1. Ingests the legitimate corpus (a subset of the requested size) into a
     dedicated collection ('baseline_measure'), isolated from the API's collection
     ('cocina_kb'). By default it uses the Chroma instance configured in CHROMA_PATH
     (the docker-compose one); with --in-memory it uses an ephemeral in-process
     Chroma.
  2. For each attack case in the YAML, in ISOLATION:
       - inserts ONLY that case's poisoned document,
       - measures whether the poison enters the top-k (RSR) and whether the answer
         contains the canary (GCR),
       - removes the poisoned document before the next case.
  3. Reports a table with RSR and GCR per size.

Isolating one poison per case reproduces the realistic "one malicious document
among N legitimate ones" scenario and avoids several poisons competing in the top-k.

Why corpus size matters
-----------------------
With more legitimate documents, the poisoned chunk competes with more relevant
chunks: RSR tends to FALL as the corpus grows. That is the argument that motivates
white-box techniques (gradient optimization of the passage) which guarantee
retrievability even in large corpora.

Usage
-----
    python scripts/measure_baseline.py                 # sizes 50 and 200
    python scripts/measure_baseline.py --sizes 50      # a single size
    python scripts/measure_baseline.py --no-generation # RSR only (no Ollama)

Notes
-----
- Generation (GCR) requires Ollama running. Without Ollama, use --no-generation:
  RSR is reported and GCR is shown as "n/a".
- Measuring at 200 docs requires the legitimate corpus to have >=200 .md files. If
  there are fewer, the script measures at the available size and says so (grow the
  corpus with `python attacks/generate_corpus.py --scale 200`).
- The pipeline runs IN-PROCESS (same components as the API) for maximum
  reproducibility. The test harness instead uses HTTP clients against the API;
  both paths share tests/metrics.py.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List
from urllib.parse import urlparse

# Allow importing app/ and tests/ from the repo root
sys.path.insert(0, str(Path(__file__).parent.parent))

import yaml
import chromadb

from app.config import settings
from app.rag.ingest import load_documents, chunk_documents
from app.rag.retriever import Retriever
from app.rag.generator import Generator
from tests.metrics import poison_in_topk, canary_in_answer


def make_chroma_client(in_memory: bool, chroma_path: str):
    """Create the Chroma client and return (client, human-readable label).

    By default uses the instance configured in CHROMA_PATH (the one started by
    docker-compose, e.g. http://localhost:8001). With --in-memory it uses an
    ephemeral in-process instance (no server or Docker required). In both cases it
    works on a dedicated collection ('baseline_measure'), isolated from the API's
    collection ('cocina_kb').
    """
    if in_memory:
        return chromadb.EphemeralClient(), "in-memory (ephemeral, no server)"
    if chroma_path.startswith("http"):
        parsed = urlparse(chroma_path)
        client = chromadb.HttpClient(host=parsed.hostname, port=parsed.port or 8000)
        return client, chroma_path
    return chromadb.PersistentClient(path=chroma_path), chroma_path


def load_cases(attacks_path: Path) -> List[Dict[str, Any]]:
    with open(attacks_path, "r", encoding="utf-8") as f:
        cases = yaml.safe_load(f)
    if not isinstance(cases, list):
        raise ValueError(f"{attacks_path} must contain a list of cases")
    return cases


def select_legit_docs(corpus_dir: Path, n: int) -> tuple[list, int]:
    """Return (subset of loaded docs, total available).

    Deterministic (alphabetical) order for reproducibility.
    """
    files = sorted(corpus_dir.glob("*.md"))
    available = len(files)
    chosen = files[:n]
    docs = []
    for fp in chosen:
        docs.append({"text": fp.read_text(encoding="utf-8"), "source": fp.name})
    return docs, available


def add_poison(collection, retriever: Retriever, poison_doc: Path) -> list[str]:
    """Insert the poisoned document's chunks. Returns their ids."""
    text = poison_doc.read_text(encoding="utf-8")
    chunks = chunk_documents([{"text": text, "source": poison_doc.name}],
                             settings.chunk_size, settings.chunk_overlap)
    ids = [c["id"] for c in chunks]
    embeddings = retriever.embedder.encode([c["text"] for c in chunks])
    collection.add(
        ids=ids,
        documents=[c["text"] for c in chunks],
        embeddings=embeddings.tolist(),
        metadatas=[{"source": c["source"]} for c in chunks],
    )
    return ids


def ingest_legit(client, collection_name: str, docs: list, retriever_embedder):
    """Create (or recreate) the collection and insert the legitimate corpus."""
    try:
        client.delete_collection(name=collection_name)
    except Exception:
        pass
    collection = client.get_or_create_collection(
        name=collection_name, metadata={"hnsw:space": "cosine"}
    )
    chunks = chunk_documents(docs, settings.chunk_size, settings.chunk_overlap)
    if chunks:
        embeddings = retriever_embedder.encode(
            [c["text"] for c in chunks], show_progress_bar=False
        )
        collection.add(
            ids=[c["id"] for c in chunks],
            documents=[c["text"] for c in chunks],
            embeddings=embeddings.tolist(),
            metadatas=[{"source": c["source"]} for c in chunks],
        )
    return collection


def measure_size(
    cases: List[Dict[str, Any]],
    corpus_dir: Path,
    repo_root: Path,
    size: int,
    top_k: int,
    retriever: Retriever,
    generator: Generator,
    client,
    do_generation: bool,
) -> Dict[str, Any]:
    """Measure RSR/GCR for a given corpus size."""
    docs, available = select_legit_docs(corpus_dir, size)
    effective = len(docs)

    collection = ingest_legit(client, "baseline_measure", docs, retriever.embedder)
    retriever.collection = collection  # reuse the already-loaded embedder

    per_case = []
    n_retrieved = 0
    n_compromised = 0

    for case in cases:
        poison_path = repo_root / case["poison_doc"]
        poison_ids = add_poison(collection, retriever, poison_path)

        # RSR: does the poison enter the top-k?
        chunks = retriever.retrieve(case["trigger_prompt"], top_k)
        retrieved_ids = [c["id"] for c in chunks]
        retrieved = poison_in_topk(case, retrieved_ids)

        compromised = False
        gen_error = None
        if do_generation:
            try:
                answer = generator.generate(case["trigger_prompt"], chunks)
                compromised = canary_in_answer(case, answer)
            except Exception as e:  # Ollama down or another failure
                gen_error = str(e)

        if retrieved:
            n_retrieved += 1
        if compromised:
            n_compromised += 1

        per_case.append({
            "id": case["id"], "tier": case.get("tier"),
            "retrieved": retrieved, "compromised": compromised,
            "gen_error": gen_error,
        })

        # Remove the poison before the next case (isolation)
        collection.delete(ids=poison_ids)

    n = len(cases)
    rsr = n_retrieved / n if n else 0.0
    gcr_conditional = (n_compromised / n_retrieved) if n_retrieved else 0.0
    gcr_absolute = (n_compromised / n) if n else 0.0

    return {
        "requested_size": size,
        "effective_size": effective,
        "available": available,
        "top_k": top_k,
        "rsr": rsr,
        "gcr_conditional": gcr_conditional,
        "gcr_absolute": gcr_absolute,
        "n_cases": n,
        "n_retrieved": n_retrieved,
        "n_compromised": n_compromised,
        "per_case": per_case,
        "generation": do_generation and any(c["gen_error"] is None for c in per_case),
    }


def print_report(results: List[Dict[str, Any]], do_generation: bool) -> None:
    print()
    print("=" * 78)
    print("BASELINE RESULTS — RSR and GCR by corpus size")
    print("=" * 78)
    header = f"{'corpus':>8} {'docs':>6} {'RSR':>8} {'GCR(cond)':>11} {'GCR(e2e)':>10} {'retr/total':>12}"
    print(header)
    print("-" * 78)
    for r in results:
        gcr_c = f"{r['gcr_conditional']*100:6.1f}%" if do_generation else "   n/a"
        gcr_a = f"{r['gcr_absolute']*100:6.1f}%" if do_generation else "  n/a"
        size_label = str(r["effective_size"])
        if r["effective_size"] != r["requested_size"]:
            size_label = f"{r['effective_size']}*"
        print(f"{r['requested_size']:>8} {size_label:>6} "
              f"{r['rsr']*100:6.1f}%  {gcr_c:>10} {gcr_a:>10} "
              f"{str(r['n_retrieved'])+'/'+str(r['n_cases']):>12}")
    print("-" * 78)
    if any(r["effective_size"] != r["requested_size"] for r in results):
        print("* effective size smaller than requested: not enough legitimate docs.")
        print("  Grow it with: python attacks/generate_corpus.py --scale <N>")
    if not do_generation:
        print("GCR not measured (--no-generation). RSR is independent of Ollama.")
    print()
    print("Reading: RSR = poison retrievability; GCR(cond) = compromise among")
    print("retrieved cases; GCR(e2e) = end-to-end successful attack.")
    print("RSR is expected to fall as the corpus grows (more top-k competition).")
    print("=" * 78)


def main() -> None:
    repo_root = Path(__file__).parent.parent
    parser = argparse.ArgumentParser(description="Measure baseline RSR/GCR of the poisoned corpus")
    parser.add_argument("--attacks", type=Path,
                        default=repo_root / "attacks" / "corpus_attacks.yaml")
    parser.add_argument("--corpus", type=Path, default=repo_root / "corpus" / "legit")
    parser.add_argument("--sizes", type=int, nargs="+", default=[50, 200])
    parser.add_argument("--top-k", type=int, default=settings.top_k)
    parser.add_argument("--no-generation", action="store_true",
                        help="Measure RSR only (does not require Ollama)")
    parser.add_argument("--model", default=settings.llm_model)
    parser.add_argument("--ollama-url", default=settings.ollama_base_url)
    parser.add_argument("--embed-model", default=settings.embed_model)
    parser.add_argument("--temperature", type=float, default=settings.llm_temperature,
                        help="Generation temperature (default from .env; 0.0 = "
                             "deterministic, for reproducible GCR)")
    parser.add_argument("--chroma-path", default=settings.chroma_path,
                        help="Chroma backend to use (default: CHROMA_PATH from .env, "
                             "e.g. the docker-compose instance)")
    parser.add_argument("--in-memory", action="store_true",
                        help="Use an ephemeral in-process Chroma (no server required)")
    parser.add_argument("--json-out", type=Path, default=None,
                        help="Dump results to a JSON file")
    args = parser.parse_args()

    do_generation = not args.no_generation

    print("Loading attack cases...")
    cases = load_cases(args.attacks)
    print(f"  {len(cases)} cases: {', '.join(c['id'] for c in cases)}")
    print(f"Loading embedder '{args.embed_model}' (once)...")

    # Chroma client: by default the configured instance (docker-compose), or
    # ephemeral with --in-memory. Always on the 'baseline_measure' collection,
    # isolated from 'cocina_kb'.
    client, backend_label = make_chroma_client(args.in_memory, args.chroma_path)
    print(f"Chroma: {backend_label} (collection 'baseline_measure')")

    # Retriever and Generator are created once; the heavy embedder is reused.
    bootstrap = client.get_or_create_collection(name="baseline_measure")
    retriever = Retriever(collection=bootstrap, embed_model_name=args.embed_model)
    generator = Generator(model_name=args.model, base_url=args.ollama_url,
                          temperature=args.temperature)

    if do_generation:
        print(f"Generation: ON (model '{args.model}' via {args.ollama_url}, "
              f"temperature={args.temperature})")
    else:
        print("Generation: OFF (RSR only)")

    results = []
    for size in args.sizes:
        print(f"\n>>> Measuring at corpus size = {size} ...")
        r = measure_size(cases, args.corpus, repo_root, size, args.top_k,
                         retriever, generator, client, do_generation)
        if r["effective_size"] != r["requested_size"]:
            print(f"    warning: only {r['available']} legitimate docs available; "
                  f"measuring at {r['effective_size']}.")
        gcr_str = "n/a" if not do_generation else f"{r['gcr_conditional']*100:.1f}%"
        print(f"    RSR={r['rsr']*100:.1f}%  GCR(cond)={gcr_str}  "
              f"retrieved={r['n_retrieved']}/{r['n_cases']}")
        results.append(r)

    print_report(results, do_generation)

    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(results, indent=2, ensure_ascii=False),
                                 encoding="utf-8")
        print(f"JSON results -> {args.json_out}")

    # Cleanup: the measurement collection should not be left behind in the backend.
    try:
        client.delete_collection(name="baseline_measure")
    except Exception:
        pass


if __name__ == "__main__":
    main()
