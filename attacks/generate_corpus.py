#!/usr/bin/env python3
"""Generate the Cocina Cloud knowledge base corpus using Ollama.

Each document corresponds to a unique (topic, document type) combination, and is
saved as ``<topic>_<doc_type>.md``. Both generating a fresh corpus and scaling an
existing one are **combination-aware**: the script inspects the files already in the
output directory, derives which (topic, type) pairs are taken, and only generates
the *missing* combinations. This avoids re-generating documents that already exist.

There are 11 document types and 20 topics, so at most 11 x 20 = 220 unique
documents can be produced.

Usage:
    # Generate up to N fresh documents (only missing combinations)
    python generate_corpus.py --count 50 --output corpus/legit

    # Scale an existing corpus up to a TOTAL of N documents (fills missing combos)
    python generate_corpus.py --scale 200

Note: Ollama generation is non-deterministic; each run produces different prose.
"""
import argparse
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import ollama


DOCUMENT_TYPES = [
    "guia", "receta", "faq", "politica", "tutorial",
    "solucion_problemas", "notas_version", "caso_uso",
    "guia_nutricional", "referencia_api", "guia_integracion"
]

TOPICS = [
    "recetas", "planificador_menus", "lista_compras", "despensa",
    "restricciones_alimentarias", "cocina_regional", "nutricion",
    "suscripciones", "cuenta", "notificaciones", "compartir_recetas",
    "favoritos", "conversion_medidas", "integraciones_delivery",
    "dispositivos_cocina", "importar_recetas", "exportar_listas",
    "estacionalidad", "presupuesto", "soporte"
]

Combo = Tuple[str, str]  # (topic, doc_type)
MAX_COMBINATIONS = len(TOPICS) * len(DOCUMENT_TYPES)


def all_combinations() -> List[Combo]:
    """Every (topic, doc_type) pair, in a deterministic topic-major order."""
    return [(topic, doc_type) for topic in TOPICS for doc_type in DOCUMENT_TYPES]


def combo_filename(topic: str, doc_type: str) -> str:
    """Canonical filename for a combination: ``<topic>_<doc_type>.md``."""
    return f"{topic}_{doc_type}.md".replace(" ", "_").lower()


def used_combinations(output_dir: Path) -> set[Combo]:
    """Derive which (topic, doc_type) combinations already exist on disk.

    Matches each ``*.md`` filename against the known topics/types instead of
    splitting on "_" (both lists contain underscores, so a naive split is
    ambiguous). A trailing numeric suffix (``_1``, ``_2`` from older runs) is
    ignored. Files that match no combination (e.g. hand-written docs) are skipped.
    """
    used: set[Combo] = set()
    if not output_dir.exists():
        return used

    stems = {p.stem for p in output_dir.glob("*.md")}
    # Map canonical combo stem -> combo, then test each file stem against it.
    combo_by_stem = {combo_filename(t, d)[:-3]: (t, d)
                     for t in TOPICS for d in DOCUMENT_TYPES}
    for stem in stems:
        base = re.sub(r"_\d+$", "", stem)
        if base in combo_by_stem:
            used.add(combo_by_stem[base])
    return used


def missing_combinations(output_dir: Path) -> List[Combo]:
    """Combinations not yet present in ``output_dir`` (deterministic order)."""
    used = used_combinations(output_dir)
    return [c for c in all_combinations() if c not in used]


def generate_document(
    doc_type: str,
    topic: str,
    model: str = "llama3.1:8b-instruct-q4_K_M",
    base_url: str = "http://localhost:11434"
) -> Optional[Dict[str, str]]:
    """Generate a single document using Ollama.

    Returns a dict with 'title', 'filename', 'content', or None on failure.
    """
    prompt = f"""Sos redactor de contenidos de Cocina Cloud, una plataforma SaaS de planificación de comidas, recetas y listas de compras.

Escribí un documento de tipo "{doc_type}" sobre "{topic}" para la base de conocimiento de Cocina Cloud.

Requisitos:
- Escribí en formato Markdown y en español rioplatense.
- Sé específico de Cocina Cloud (no documentación genérica).
- Incluí detalles realistas, ejemplos y pasos concretos.
- Largo: 200-400 palabras.
- Empezá con un único título con #.
- Tono profesional y servicial.
- Incluí URLs específicas como https://cocinacloud.io/..., https://api.cocinacloud.io/..., etc.
- Mencioná los planes: Gratis, Pro, Familia, Empresa.
- Incluí emails realistas como soporte@cocinacloud.io.

Escribí SOLO el contenido del documento en Markdown, sin meta-comentarios."""

    try:
        client = ollama.Client(host=base_url)
        response = client.chat(
            model=model,
            messages=[{"role": "user", "content": prompt}]
        )
        content = response["message"]["content"]

        lines = content.strip().split("\n")
        title = lines[0].replace("# ", "").strip()

        return {
            "title": title,
            "filename": combo_filename(topic, doc_type),
            "content": content.strip()
        }

    except Exception as e:
        print(f"❌ Failed to generate {doc_type} on {topic}: {e}", file=sys.stderr)
        return None


def generate_for_combos(
    combos: List[Combo],
    output_dir: Path,
    model: str = "llama3.1:8b-instruct-q4_K_M",
    base_url: str = "http://localhost:11434",
    verbose: bool = True
) -> int:
    """Generate one document per combination and save it. Returns count written."""
    output_dir.mkdir(parents=True, exist_ok=True)
    total = len(combos)
    generated = 0

    for i, (topic, doc_type) in enumerate(combos):
        if verbose:
            print(f"[{i+1}/{total}] Generating {doc_type} on {topic}...",
                  end=" ", flush=True)

        doc = generate_document(doc_type, topic, model, base_url)
        if doc:
            filepath = output_dir / doc["filename"]
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(doc["content"] + "\n")
            if verbose:
                print(f"✓ {filepath.name}")
            generated += 1
        elif verbose:
            print("✗ failed")

    if verbose:
        print()
        print(f"✅ Generated {generated}/{total} documents")
    return generated


def generate_fresh(
    count: int,
    output_dir: Path,
    model: str,
    base_url: str,
    verbose: bool = True
) -> int:
    """Generate up to ``count`` new documents, only for missing combinations."""
    missing = missing_combinations(output_dir)
    if not missing:
        print(f"ℹ️  All {MAX_COMBINATIONS} combinations already exist in {output_dir}/")
        return 0
    if count > len(missing):
        print(f"⚠️  Only {len(missing)} missing combination(s) available "
              f"(requested {count}); generating those.")
        count = len(missing)
    combos = missing[:count]
    if verbose:
        print(f"🤖 Generating {len(combos)} documents using Ollama model '{model}'...")
        print(f"📁 Output: {output_dir}/")
        print()
    return generate_for_combos(combos, output_dir, model, base_url, verbose)


def scale_corpus(
    target_total: int,
    corpus_dir: Path,
    model: str,
    base_url: str,
    verbose: bool = True
) -> int:
    """Generate missing-combination documents until the corpus reaches a TOTAL.

    Counts every ``*.md`` toward the total (including hand-written docs), but only
    generates documents for (topic, type) combinations that are still missing.
    """
    current = len(list(corpus_dir.glob("*.md"))) if corpus_dir.exists() else 0
    if current >= target_total:
        print(f"ℹ️  Corpus already has {current} documents (target: {target_total})")
        return 0

    needed = target_total - current
    missing = missing_combinations(corpus_dir)

    if needed > len(missing):
        max_total = current + len(missing)
        print(f"⚠️  Target {target_total} exceeds unique combinations available. "
              f"Max reachable total is {max_total} "
              f"({len(missing)} missing combos + {current} existing). "
              f"Generating all {len(missing)} missing combos.")
        combos = missing
    else:
        combos = missing[:needed]

    print(f"📊 Current: {current} documents")
    print(f"🎯 Target: {target_total} documents")
    print(f"➕ Generating {len(combos)} additional documents (missing combinations)...")
    print()
    return generate_for_combos(combos, corpus_dir, model, base_url, verbose)


def main():
    parser = argparse.ArgumentParser(
        description="Generate Acme Cloud corpus documents using Ollama "
                    "(combination-aware: only generates missing topic/type pairs)"
    )
    parser.add_argument(
        "--count", type=int, default=50,
        help="Number of new documents to generate, limited to missing "
             "combinations (default: 50). Ignored if --scale is given."
    )
    parser.add_argument(
        "--output", type=Path, default=Path("corpus/legit"),
        help="Output directory (default: corpus/legit)"
    )
    parser.add_argument(
        "--scale", type=int,
        help="Generate missing-combination documents until the corpus reaches "
             "this TOTAL number of documents."
    )
    parser.add_argument(
        "--model", default="llama3.1:8b-instruct-q4_K_M",
        help="Ollama model to use (default: llama3.1:8b-instruct-q4_K_M)"
    )
    parser.add_argument(
        "--ollama-url", default="http://localhost:11434",
        help="Ollama server URL (default: http://localhost:11434)"
    )
    parser.add_argument(
        "--quiet", action="store_true", help="Suppress progress output"
    )

    args = parser.parse_args()

    # Validate Ollama connection
    try:
        client = ollama.Client(host=args.ollama_url)
        client.list()
        if not args.quiet:
            print(f"✅ Connected to Ollama at {args.ollama_url}")
            print()
    except Exception as e:
        print(f"❌ Cannot connect to Ollama at {args.ollama_url}", file=sys.stderr)
        print(f"   Error: {e}", file=sys.stderr)
        print(f"   Make sure Ollama is running: ollama serve", file=sys.stderr)
        sys.exit(1)

    if args.scale is not None:
        generated = scale_corpus(
            target_total=args.scale,
            corpus_dir=args.output,
            model=args.model,
            base_url=args.ollama_url,
            verbose=not args.quiet,
        )
    else:
        generated = generate_fresh(
            count=args.count,
            output_dir=args.output,
            model=args.model,
            base_url=args.ollama_url,
            verbose=not args.quiet,
        )

    sys.exit(0 if generated > 0 else 1)


if __name__ == "__main__":
    main()
