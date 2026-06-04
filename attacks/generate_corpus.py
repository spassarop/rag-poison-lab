#!/usr/bin/env python3
"""Generate or expand Acme Cloud corpus using Ollama for dynamic content.

This script uses Ollama to generate realistic knowledge base documents for
Acme Cloud. Can be used to:
- Replace the static corpus with LLM-generated content
- Expand the existing corpus to 200+ documents for stress testing
- Generate documents in different styles or topics

Usage:
    python generate_corpus.py --count 50 --output corpus/legit
    python generate_corpus.py --expand --scale 200
"""
import argparse
import json
import sys
from pathlib import Path
from typing import List, Dict
import ollama


DOCUMENT_TYPES = [
    "policy", "guide", "faq", "troubleshooting", "release_notes",
    "tutorial", "api_reference", "integration_guide", "use_case",
    "security_guide", "compliance_doc"
]

TOPICS = [
    "authentication", "data_ingestion", "querying", "webhooks", "billing",
    "security", "performance", "monitoring", "deployments", "integrations",
    "sdks", "cli_tools", "backups", "exports", "compliance", "regions",
    "rate_limiting", "error_handling", "best_practices", "migrations"
]


def generate_document(
    doc_type: str,
    topic: str,
    model: str = "llama3.1:8b-instruct-q4_K_M",
    base_url: str = "http://localhost:11434"
) -> Dict[str, str]:
    """Generate a single document using Ollama.

    Args:
        doc_type: Type of document (policy, guide, faq, etc.)
        topic: Topic area (authentication, billing, etc.)
        model: Ollama model name
        base_url: Ollama server URL

    Returns:
        Dict with 'title', 'filename', 'content'
    """
    prompt = f"""You are a technical writer for Acme Cloud, a SaaS platform API service.

Write a {doc_type} document about {topic} for Acme Cloud's knowledge base.

Requirements:
- Write in Markdown format
- Be specific to Acme Cloud (not generic cloud docs)
- Include realistic technical details, code examples, and specifics
- Length: 200-400 words
- Start with a single # title
- Use professional, helpful tone
- Include specific URLs like https://acmecloud.io/..., https://api.acmecloud.io/..., etc.
- Reference specific plan tiers: Free, Pro, Business, Enterprise
- Include realistic email addresses: support@acmecloud.io, etc.

Write ONLY the Markdown document content, no meta-commentary."""

    try:
        client = ollama.Client(host=base_url)
        response = client.chat(
            model=model,
            messages=[{"role": "user", "content": prompt}]
        )
        content = response["message"]["content"]

        # Extract title from first line
        lines = content.strip().split('\n')
        title = lines[0].replace('# ', '').strip()

        # Generate filename
        filename = f"{topic}_{doc_type}.md".replace(' ', '_').lower()

        return {
            "title": title,
            "filename": filename,
            "content": content.strip()
        }

    except Exception as e:
        print(f"❌ Failed to generate {doc_type} on {topic}: {e}", file=sys.stderr)
        return None


def generate_corpus(
    count: int,
    output_dir: Path,
    model: str = "llama3.1:8b-instruct-q4_K_M",
    base_url: str = "http://localhost:11434",
    verbose: bool = True
) -> int:
    """Generate multiple documents and save to output directory.

    Args:
        count: Number of documents to generate
        output_dir: Output directory path
        model: Ollama model name
        base_url: Ollama server URL
        verbose: Print progress

    Returns:
        Number of documents successfully generated
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    if verbose:
        print(f"🤖 Generating {count} documents using Ollama model '{model}'...")
        print(f"📁 Output: {output_dir}/")
        print()

    generated = 0

    # Cycle through topics and types to get variety
    for i in range(count):
        doc_type = DOCUMENT_TYPES[i % len(DOCUMENT_TYPES)]
        topic = TOPICS[i % len(TOPICS)]

        if verbose:
            print(f"[{i+1}/{count}] Generating {doc_type} on {topic}...", end=" ", flush=True)

        doc = generate_document(doc_type, topic, model, base_url)

        if doc:
            filepath = output_dir / doc["filename"]

            # Avoid overwriting - add counter if file exists
            if filepath.exists():
                base = filepath.stem
                ext = filepath.suffix
                counter = 1
                while filepath.exists():
                    filepath = output_dir / f"{base}_{counter}{ext}"
                    counter += 1

            with open(filepath, "w", encoding="utf-8") as f:
                f.write(doc["content"] + "\n")

            if verbose:
                print(f"✓ {filepath.name}")

            generated += 1
        else:
            if verbose:
                print("✗ failed")

    if verbose:
        print()
        print(f"✅ Generated {generated}/{count} documents")

    return generated


def expand_existing_corpus(
    target_count: int,
    corpus_dir: Path,
    model: str = "llama3.1:8b-instruct-q4_K_M",
    base_url: str = "http://localhost:11434"
) -> int:
    """Expand existing corpus to reach target count.

    Args:
        target_count: Target total number of documents
        corpus_dir: Corpus directory path
        model: Ollama model name
        base_url: Ollama server URL

    Returns:
        Number of new documents generated
    """
    existing = list(corpus_dir.glob("*.md"))
    current_count = len(existing)

    if current_count >= target_count:
        print(f"ℹ️  Corpus already has {current_count} documents (target: {target_count})")
        return 0

    needed = target_count - current_count
    print(f"📊 Current: {current_count} documents")
    print(f"🎯 Target: {target_count} documents")
    print(f"➕ Generating {needed} additional documents...")
    print()

    return generate_corpus(needed, corpus_dir, model, base_url)


def main():
    parser = argparse.ArgumentParser(
        description="Generate Acme Cloud corpus documents using Ollama"
    )
    parser.add_argument(
        "--count",
        type=int,
        default=50,
        help="Number of documents to generate (default: 50)"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("corpus/legit"),
        help="Output directory (default: corpus/legit)"
    )
    parser.add_argument(
        "--expand",
        action="store_true",
        help="Expand existing corpus instead of replacing it"
    )
    parser.add_argument(
        "--scale",
        type=int,
        help="Scale corpus to this total size (implies --expand)"
    )
    parser.add_argument(
        "--model",
        default="llama3.1:8b-instruct-q4_K_M",
        help="Ollama model to use (default: llama3.1:8b-instruct-q4_K_M)"
    )
    parser.add_argument(
        "--ollama-url",
        default="http://localhost:11434",
        help="Ollama server URL (default: http://localhost:11434)"
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress progress output"
    )

    args = parser.parse_args()

    # Validate Ollama connection
    try:
        client = ollama.Client(host=args.ollama_url)
        client.list()  # Test connection
        if not args.quiet:
            print(f"✅ Connected to Ollama at {args.ollama_url}")
            print()
    except Exception as e:
        print(f"❌ Cannot connect to Ollama at {args.ollama_url}", file=sys.stderr)
        print(f"   Error: {e}", file=sys.stderr)
        print(f"   Make sure Ollama is running: ollama serve", file=sys.stderr)
        sys.exit(1)

    # Determine mode
    if args.scale:
        generated = expand_existing_corpus(
            target_count=args.scale,
            corpus_dir=args.output,
            model=args.model,
            base_url=args.ollama_url
        )
    elif args.expand:
        # Expand to double the current size by default
        existing_count = len(list(args.output.glob("*.md")))
        target = max(existing_count * 2, args.count)
        generated = expand_existing_corpus(
            target_count=target,
            corpus_dir=args.output,
            model=args.model,
            base_url=args.ollama_url
        )
    else:
        # Generate fresh corpus
        generated = generate_corpus(
            count=args.count,
            output_dir=args.output,
            model=args.model,
            base_url=args.ollama_url,
            verbose=not args.quiet
        )

    sys.exit(0 if generated > 0 else 1)


if __name__ == "__main__":
    main()
