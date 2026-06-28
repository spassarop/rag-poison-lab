#!/usr/bin/env python3
"""Seed ChromaDB with the Cocina Cloud knowledge base corpus.

This script loads documents from the corpus directory, chunks them, generates
embeddings, and stores everything in ChromaDB. It's the first step before
running the API or tests.

Usage:
    python scripts/seed_db.py
    python scripts/seed_db.py --corpus corpus/legit --reset
    python scripts/seed_db.py --no-reset  # Add to existing collection
"""
import argparse
import sys
from pathlib import Path

# Add app directory to path so we can import modules
sys.path.insert(0, str(Path(__file__).parent.parent))

import chromadb
from app.config import settings
from app.rag.ingest import ingest

def main():
    parser = argparse.ArgumentParser(
        description="Seed ChromaDB with Cocina Cloud knowledge base"
    )
    parser.add_argument(
        "--corpus",
        type=Path,
        default=Path("corpus/legit"),
        help="Path to corpus directory (default: corpus/legit)"
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        default=True,
        help="Reset collection before ingesting (default: True)"
    )
    parser.add_argument(
        "--no-reset",
        action="store_true",
        help="Do NOT reset collection (append to existing data)"
    )
    parser.add_argument(
        "--chroma-path",
        default=None,
        help=f"ChromaDB path (default: from .env or {settings.chroma_path})"
    )
    parser.add_argument(
        "--collection",
        default=None,
        help=f"Collection name (default: from .env or {settings.chroma_collection})"
    )
    parser.add_argument(
        "--with-poison",
        action="store_true",
        help="Also ingest the poisoned documents into the SAME collection. This "
             "makes the live knowledge base vulnerable (used for the demo and the "
             "test harness, where the assertions are expected to fail red)."
    )
    parser.add_argument(
        "--poison-corpus",
        type=Path,
        default=Path("corpus/poisoned"),
        help="Path to the poisoned corpus (default: corpus/poisoned)"
    )
    parser.add_argument(
        "--internal-corpus",
        type=Path,
        default=Path("corpus/internal"),
        help="Confidential docs ingested with sensitivity=internal (default: corpus/internal)"
    )

    args = parser.parse_args()

    # Resolve reset flag
    reset = args.reset and not args.no_reset

    # Use settings or override from args
    chroma_path = args.chroma_path or settings.chroma_path
    collection_name = args.collection or settings.chroma_collection

    print("=" * 70)
    print("🌱 Seeding ChromaDB with Cocina Cloud Knowledge Base")
    print("=" * 70)
    print(f"Corpus: {args.corpus}")
    print(f"ChromaDB: {chroma_path}")
    print(f"Collection: {collection_name}")
    print(f"Reset: {'Yes (delete existing)' if reset else 'No (append)'}")
    print(f"Poison: {'Yes (--with-poison)' if args.with_poison else 'No'}")
    print(f"Embedding model: {settings.embed_model}")
    print(f"Chunk size: {settings.chunk_size}, overlap: {settings.chunk_overlap}")
    print()

    # Check corpus exists
    if not args.corpus.exists():
        print(f"❌ Corpus directory not found: {args.corpus}", file=sys.stderr)
        print(f"   Run: python attacks/generate_corpus.py --count 50 first", file=sys.stderr)
        sys.exit(1)

    doc_count = len(list(args.corpus.glob("*.md")))
    if doc_count == 0:
        print(f"❌ No .md files found in {args.corpus}", file=sys.stderr)
        sys.exit(1)

    print(f"📚 Found {doc_count} documents in corpus")
    print()

    # Connect to ChromaDB
    print("🔌 Connecting to ChromaDB...", end=" ", flush=True)
    try:
        if chroma_path.startswith("http"):
            # Remote ChromaDB (e.g., in Docker)
            host_port = chroma_path.replace("http://", "").replace("https://", "")
            if ":" in host_port:
                host, port = host_port.split(":")
                chroma_client = chromadb.HttpClient(host=host, port=int(port))
            else:
                chroma_client = chromadb.HttpClient(host=host_port)
        else:
            # Local persistent ChromaDB
            chroma_client = chromadb.PersistentClient(path=chroma_path)

        print("✅")
    except Exception as e:
        print(f"❌\n   Error: {e}", file=sys.stderr)
        sys.exit(1)

    # Run ingestion
    print()
    print("📥 Starting ingestion...")
    print()

    try:
        result = ingest(
            corpus_path=str(args.corpus),
            chroma_client=chroma_client,
            collection_name=collection_name,
            chunk_size=settings.chunk_size,
            chunk_overlap=settings.chunk_overlap,
            embed_model=settings.embed_model,
            reset=reset
        )

        print()
        print("=" * 70)
        print("✅ Ingestion Complete!")
        print("=" * 70)
        print(f"Documents loaded: {result['docs_loaded']}")
        print(f"Chunks created: {result['chunks_created']}")
        print(f"Chunks stored: {result['chunks_stored']}")
        if result.get("chunks_blocked"):
            print(f"🛡️  Chunks blocked by ingestion defense: {result['chunks_blocked']}")
        print()

        # Ingest internal/confidential docs with sensitivity=internal (appended), so
        # the retrieval role filter can keep them away from the customer role.
        if args.internal_corpus.exists() and any(args.internal_corpus.glob("*.md")):
            n_int = len(list(args.internal_corpus.glob("*.md")))
            print(f"🔒 Ingesting {n_int} internal document(s) from {args.internal_corpus} "
                  f"(sensitivity=internal) ...")
            internal_result = ingest(
                corpus_path=str(args.internal_corpus),
                chroma_client=chroma_client,
                collection_name=collection_name,
                chunk_size=settings.chunk_size,
                chunk_overlap=settings.chunk_overlap,
                embed_model=settings.embed_model,
                reset=False,
                sensitivity="internal",
            )
            print(f"🔒 Internal chunks stored: {internal_result['chunks_stored']}")
            print()

        # Optionally ingest the poisoned documents into the SAME collection,
        # appending (reset=False) so the legitimate corpus is preserved. This is
        # what makes the live KB vulnerable for the demo and the test harness.
        if args.with_poison:
            if not args.poison_corpus.exists():
                print(f"❌ Poison corpus not found: {args.poison_corpus}", file=sys.stderr)
                print("   Run: python attacks/generate_poisoned_corpus.py", file=sys.stderr)
                sys.exit(1)
            poison_count = len(list(args.poison_corpus.glob("*.md")))
            print(f"☠️  Ingesting {poison_count} poisoned documents from {args.poison_corpus} ...")
            poison_result = ingest(
                corpus_path=str(args.poison_corpus),
                chroma_client=chroma_client,
                collection_name=collection_name,
                chunk_size=settings.chunk_size,
                chunk_overlap=settings.chunk_overlap,
                embed_model=settings.embed_model,
                reset=False,  # append; do NOT wipe the legitimate corpus
            )
            print(f"☠️  Poison documents loaded: {poison_result['docs_loaded']}, "
                  f"chunks stored: {poison_result['chunks_stored']}")
            print()

        # Verify collection
        collection = chroma_client.get_collection(name=collection_name)
        total_count = collection.count()
        print(f"📊 Collection '{collection_name}' now contains {total_count} chunks")
        print()
        print("🚀 Ready to start the API:")
        print(f"   uvicorn app.main:app --reload")
        print()

    except Exception as e:
        print()
        print(f"❌ Ingestion failed: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
