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

import urllib3, warnings
# Suppress only the specific urllib3 Insecure Request Warning
warnings.filterwarnings("ignore", category=urllib3.exceptions.InsecureRequestWarning)



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
    print(f"Embedding model: {settings.embed_model}")
    print(f"Chunk size: {settings.chunk_size}, overlap: {settings.chunk_overlap}")
    print()

    # Check corpus exists
    if not args.corpus.exists():
        print(f"❌ Corpus directory not found: {args.corpus}", file=sys.stderr)
        print(f"   Run scripts/generate_static_corpus.py first", file=sys.stderr)
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
