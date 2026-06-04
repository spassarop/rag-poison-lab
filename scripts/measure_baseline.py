#!/usr/bin/env python3
"""Mide RSR y GCR base del corpus envenenado a distintos tamaños de corpus.

Qué hace
--------
Para cada tamaño de corpus solicitado (p. ej. 50 y 200 documentos):

  1. Ingesta el corpus legítimo (subconjunto del tamaño pedido) en una colección
     dedicada ('baseline_measure'), aislada de la colección de la API ('acme_kb').
     Por defecto usa la instancia Chroma configurada en CHROMA_PATH (la del
     docker-compose); con --in-memory usa una Chroma efímera en proceso.
  2. Para cada caso de ataque del YAML, de forma AISLADA:
       - inserta SOLO el documento envenenado de ese caso,
       - mide si el veneno entra en el top-k (RSR) y si la respuesta contiene el
         canary (GCR),
       - retira el documento envenenado antes del siguiente caso.
  3. Reporta una tabla con RSR y GCR por tamaño.

Aislar un veneno por caso reproduce el escenario realista "un documento malicioso
entre N legítimos" y evita que varios venenos compitan entre sí en el top-k.

Por qué crece la relevancia del tamaño
--------------------------------------
Con más documentos legítimos, el chunk envenenado compite con más chunks
relevantes: la RSR tiende a CAER al crecer el corpus. Ese es el argumento que
motiva técnicas white-box (optimización por gradiente del passage) que garantizan
recuperabilidad incluso en corpus grandes.

Ejecución
---------
    python scripts/measure_baseline.py                 # tamaños 50 y 200
    python scripts/measure_baseline.py --sizes 50      # un solo tamaño
    python scripts/measure_baseline.py --no-generation # solo RSR (sin Ollama)

Notas
-----
- La generación (GCR) requiere Ollama corriendo. Sin Ollama, usar
  --no-generation: se reporta RSR y GCR queda como "n/a".
- Para medir a 200 docs hace falta que el corpus legítimo tenga >=200 .md. Si hay
  menos, el script mide al tamaño disponible y lo avisa (expandir el corpus con
  `python attacks/generate_corpus.py --scale 200`).
- El pipeline corre EN PROCESO (mismos componentes que la API) para máxima
  reproducibilidad. El harness de tests usa, en cambio, clientes HTTP contra la
  API; ambas vías comparten tests/metrics.py.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List
from urllib.parse import urlparse

# Permitir importar app/ y tests/ desde la raíz del repo
sys.path.insert(0, str(Path(__file__).parent.parent))

import yaml
import chromadb

from app.config import settings
from app.rag.ingest import load_documents, chunk_documents
from app.rag.retriever import Retriever
from app.rag.generator import Generator
from tests.metrics import poison_in_topk, canary_in_answer


def make_chroma_client(in_memory: bool, chroma_path: str):
    """Crea el cliente Chroma y devuelve (cliente, etiqueta legible).

    Por defecto usa la instancia configurada en CHROMA_PATH (la que levanta
    docker-compose, p. ej. http://localhost:8001). Con --in-memory usa una
    instancia efímera en proceso (no requiere servidor ni Docker). En ambos
    casos se trabaja sobre una colección dedicada ('baseline_measure'), aislada
    de la colección de la API ('acme_kb').
    """
    if in_memory:
        return chromadb.EphemeralClient(), "en memoria (efímera, sin servidor)"
    if chroma_path.startswith("http"):
        parsed = urlparse(chroma_path)
        client = chromadb.HttpClient(host=parsed.hostname, port=parsed.port or 8000)
        return client, chroma_path
    return chromadb.PersistentClient(path=chroma_path), chroma_path


def load_cases(attacks_path: Path) -> List[Dict[str, Any]]:
    with open(attacks_path, "r", encoding="utf-8") as f:
        cases = yaml.safe_load(f)
    if not isinstance(cases, list):
        raise ValueError(f"{attacks_path} debe contener una lista de casos")
    return cases


def select_legit_docs(corpus_dir: Path, n: int) -> tuple[list, int]:
    """Devuelve (subconjunto de docs cargados, total disponible).

    Orden determinístico (alfabético) para reproducibilidad.
    """
    files = sorted(corpus_dir.glob("*.md"))
    available = len(files)
    chosen = files[:n]
    docs = []
    for fp in chosen:
        docs.append({"text": fp.read_text(encoding="utf-8"), "source": fp.name})
    return docs, available


def add_poison(collection, retriever: Retriever, poison_doc: Path) -> list[str]:
    """Inserta los chunks del documento envenenado. Devuelve sus ids."""
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


def ingest_legit(client, collection_name: str, docs: list, retriever_embedder) -> "Collection":
    """Crea (o recrea) la colección e inserta el corpus legítimo."""
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
    """Mide RSR/GCR para un tamaño de corpus dado."""
    docs, available = select_legit_docs(corpus_dir, size)
    effective = len(docs)

    collection = ingest_legit(client, "baseline_measure", docs, retriever.embedder)
    retriever.collection = collection  # reusar el embedder ya cargado

    per_case = []
    n_retrieved = 0
    n_compromised = 0

    for case in cases:
        poison_path = repo_root / case["poison_doc"]
        poison_ids = add_poison(collection, retriever, poison_path)

        # RSR: ¿el veneno entra en top-k?
        chunks = retriever.retrieve(case["trigger_prompt"], top_k)
        retrieved_ids = [c["id"] for c in chunks]
        retrieved = poison_in_topk(case, retrieved_ids)

        compromised = False
        gen_error = None
        if do_generation:
            try:
                answer = generator.generate(case["trigger_prompt"], chunks)
                compromised = canary_in_answer(case, answer)
            except Exception as e:  # Ollama caído u otro fallo
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

        # Retirar el veneno antes del próximo caso (aislamiento)
        collection.delete(ids=poison_ids)

    n = len(cases)
    rsr = sum(1 for c in per_case if c["retrieved"]) / n if n else 0.0
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
    print("RESULTADOS BASE — RSR y GCR por tamaño de corpus")
    print("=" * 78)
    header = f"{'corpus':>8} {'docs':>6} {'RSR':>8} {'GCR(cond)':>11} {'GCR(e2e)':>10} {'recup/total':>12}"
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
        print("* tamaño efectivo menor al pedido: corpus legítimo insuficiente.")
        print("  Expandir con: python attacks/generate_corpus.py --scale <N>")
    if not do_generation:
        print("GCR no medido (--no-generation). RSR es independiente de Ollama.")
    print()
    print("Lectura: RSR = recuperabilidad del veneno; GCR(cond) = compromiso entre")
    print("casos recuperados; GCR(e2e) = ataque exitoso de punta a punta.")
    print("Se espera que RSR caiga al crecer el corpus (más competencia en top-k).")
    print("=" * 78)


def main() -> None:
    repo_root = Path(__file__).parent.parent
    parser = argparse.ArgumentParser(description="Mide RSR/GCR base del corpus envenenado")
    parser.add_argument("--attacks", type=Path,
                        default=repo_root / "attacks" / "corpus_attacks.yaml")
    parser.add_argument("--corpus", type=Path, default=repo_root / "corpus" / "legit")
    parser.add_argument("--sizes", type=int, nargs="+", default=[50, 200])
    parser.add_argument("--top-k", type=int, default=settings.top_k)
    parser.add_argument("--no-generation", action="store_true",
                        help="Medir solo RSR (no requiere Ollama)")
    parser.add_argument("--model", default=settings.llm_model)
    parser.add_argument("--ollama-url", default=settings.ollama_base_url)
    parser.add_argument("--embed-model", default=settings.embed_model)
    parser.add_argument("--chroma-path", default=settings.chroma_path,
                        help="Backend Chroma a usar (default: CHROMA_PATH del .env, "
                             "p. ej. la instancia de docker-compose)")
    parser.add_argument("--in-memory", action="store_true",
                        help="Usar Chroma efímera en proceso (no requiere servidor)")
    parser.add_argument("--json-out", type=Path, default=None,
                        help="Volcar resultados a un archivo JSON")
    args = parser.parse_args()

    do_generation = not args.no_generation

    print("Cargando casos de ataque...")
    cases = load_cases(args.attacks)
    print(f"  {len(cases)} casos: {', '.join(c['id'] for c in cases)}")
    print(f"Cargando embedder '{args.embed_model}' (una sola vez)...")

    # Cliente Chroma: por defecto la instancia configurada (docker-compose),
    # o efímera con --in-memory. Siempre sobre la colección 'baseline_measure',
    # aislada de 'acme_kb'.
    client, backend_label = make_chroma_client(args.in_memory, args.chroma_path)
    print(f"Chroma: {backend_label} (colección 'baseline_measure')")

    # Retriever y Generator se crean una vez; el embedder pesado se reutiliza.
    bootstrap = client.get_or_create_collection(name="baseline_measure")
    retriever = Retriever(collection=bootstrap, embed_model_name=args.embed_model)
    generator = Generator(model_name=args.model, base_url=args.ollama_url)

    if do_generation:
        print(f"Generación: ON (modelo '{args.model}' vía {args.ollama_url})")
    else:
        print("Generación: OFF (solo RSR)")

    results = []
    for size in args.sizes:
        print(f"\n>>> Midiendo a tamaño de corpus = {size} ...")
        r = measure_size(cases, args.corpus, repo_root, size, args.top_k,
                         retriever, generator, client, do_generation)
        if r["effective_size"] != r["requested_size"]:
            print(f"    aviso: solo hay {r['available']} docs legítimos; "
                  f"midiendo a {r['effective_size']}.")
        gcr_str = "n/a" if not do_generation else f"{r['gcr_conditional']*100:.1f}%"
        print(f"    RSR={r['rsr']*100:.1f}%  GCR(cond)={gcr_str}  "
              f"recuperados={r['n_retrieved']}/{r['n_cases']}")
        results.append(r)

    print_report(results, do_generation)

    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(results, indent=2, ensure_ascii=False),
                                 encoding="utf-8")
        print(f"Resultados JSON -> {args.json_out}")

    # Limpieza: la colección de medición no debe quedar residual en el backend.
    try:
        client.delete_collection(name="baseline_measure")
    except Exception:
        pass


if __name__ == "__main__":
    main()
