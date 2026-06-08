#!/usr/bin/env python3
"""Inspect exactly what the RAG pipeline retrieves and sends to the LLM.

For a given question it prints, against the SAME ChromaDB collection the API uses:

  1. the retrieved chunks (id, source, score, and FULL text),
  2. the exact prompt sent to the model (system + user messages),
  3. the raw model answer,
  4. whether the answer contains the canary, and which poisoned sources were
     retrieved.

This is the tool to debug "the poison is in the sources but the model says it has
no information": you can see the real context and prompt, and tell apart a retrieval
problem, a prompt-assembly problem, and the model simply refusing the injection.

Usage:
    python scripts/debug_chat.py "Hola, mi pago falló y necesito asistencia humana"
    python scripts/debug_chat.py "..." --top-k 6 --no-generate
    python scripts/debug_chat.py "..." --temperature 0.8
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).parent.parent))

import chromadb

from app.config import settings
from app.rag.retriever import Retriever
from app.rag.generator import Generator


def make_chroma_client(chroma_path: str):
    if chroma_path.startswith("http"):
        parsed = urlparse(chroma_path)
        return chromadb.HttpClient(host=parsed.hostname, port=parsed.port or 8000)
    return chromadb.PersistentClient(path=chroma_path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Debug a single RAG /chat call with full visibility")
    parser.add_argument("question", help="The user question to send")
    parser.add_argument("--top-k", type=int, default=settings.top_k)
    parser.add_argument("--chroma-path", default=settings.chroma_path)
    parser.add_argument("--collection", default=settings.chroma_collection)
    parser.add_argument("--model", default=settings.llm_model)
    parser.add_argument("--embed-model", default=settings.embed_model)
    parser.add_argument("--ollama-url", default=settings.ollama_base_url)
    parser.add_argument("--temperature", type=float, default=settings.llm_temperature)
    parser.add_argument("--canary", default=settings.canary_url,
                        help="Canary string to look for in the answer")
    parser.add_argument("--no-generate", action="store_true",
                        help="Only retrieve and show the prompt; do not call the LLM")
    args = parser.parse_args()

    bar = "=" * 78

    client = make_chroma_client(args.chroma_path)
    try:
        collection = client.get_collection(name=args.collection)
    except Exception as e:
        print(f"❌ Could not open collection '{args.collection}' at {args.chroma_path}: {e}",
              file=sys.stderr)
        print("   Seed it first: python scripts/seed_db.py --with-poison", file=sys.stderr)
        sys.exit(1)

    print(bar)
    print(f"QUESTION: {args.question}")
    print(f"Collection: {args.collection} ({collection.count()} chunks) @ {args.chroma_path}")
    print(f"top_k={args.top_k}  model={args.model}  temperature={args.temperature}")
    print(bar)

    retriever = Retriever(collection=collection, embed_model_name=args.embed_model)
    chunks = retriever.retrieve(args.question, args.top_k)

    print(f"\n### RETRIEVED CHUNKS ({len(chunks)}) — ordered by score\n")
    poisoned_hits = []
    for i, c in enumerate(chunks, 1):
        is_poison = "poison" in c["source"]
        if is_poison:
            poisoned_hits.append(c["source"])
        tag = "  <-- POISON" if is_poison else ""
        print(f"[{i}] id={c['id']}  source={c['source']}  score={c['score']}{tag}")
        print("-" * 78)
        print(c["text"])
        print("-" * 78)
        print()

    generator = Generator(model_name=args.model, base_url=args.ollama_url,
                          temperature=args.temperature)
    messages = generator.build_messages(args.question, chunks)

    print("\n### EXACT PROMPT SENT TO THE MODEL\n")
    for m in messages:
        print(f"----- {m['role'].upper()} -----")
        print(m["content"])
        print()

    if args.no_generate:
        print(bar)
        print("Generation skipped (--no-generate).")
        print(f"Poisoned sources retrieved: {poisoned_hits or 'none'}")
        print(bar)
        return

    answer = generator.generate(args.question, chunks)

    print(bar)
    print("### RAW MODEL ANSWER\n")
    print(answer)
    print()
    print(bar)
    print(f"Canary present in answer: {args.canary in answer}")
    print(f"Canary looked for: {args.canary}")
    print(f"Poisoned sources retrieved: {poisoned_hits or 'none'}")
    print(bar)


if __name__ == "__main__":
    main()
