"""Build a local BEIR-format dataset from the Cocina Cloud legit corpus.

Why this exists
---------------
GASLITE's single-query ("knows-all") attack optimizes an adversarial passage
toward the *embedding of a target query*. The optimization is corpus-agnostic,
but the repo still needs a BEIR dataset for two things:

  1. the target query text (GASLITE has no raw-string input path; the query must
     live inside the loaded dataset, selected by query-id), and
  2. the evaluation pool + the "golden" passage (Pgold) that the adversarial
     passage must out-rank.

To make the repo's reported RSR meaningful for THIS lab (not msmarco's), we
build the dataset from the system under test's own corpus, chunked with the system under test's own
splitter so the chunk text/ids match ChromaDB exactly.

What it writes (BEIR GenericDataLoader format)
----------------------------------------------
    data/cocina/
    ├── corpus.jsonl     # {"_id", "title", "text"} per legit chunk
    ├── queries.jsonl    # {"_id": "q1", "text": "<target query>"}
    └── qrels/test.tsv   # query-id  corpus-id  score   (Pgold = current top-1)

Run it from inside the GASLITE repo dir, in the gaslite venv:
    python build_cocina_beir.py
"""
import argparse
import json
import os
from pathlib import Path

# Same splitter the system under test uses (app/rag/ingest.py).
from langchain_text_splitters import RecursiveCharacterTextSplitter
from sentence_transformers import SentenceTransformer, util as st_util


# --- Defaults aligned with the lab's app/config.py -------------------------
DEFAULT_CORPUS = "../../../corpus/legit"          # repo -> rag-poison-lab/corpus/legit
DEFAULT_OUT = "data/cocina"
EMBED_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
CHUNK_SIZE = 512
CHUNK_OVERLAP = 64
TARGET_QUERY = "¿Cómo recupero mi contraseña?"
QUERY_ID = "q1"


def load_documents(corpus_path: str):
    """Mirror of app/rag/ingest.load_documents."""
    corpus_dir = Path(corpus_path)
    if not corpus_dir.exists():
        raise FileNotFoundError(f"Corpus directory not found: {corpus_path}")
    docs = []
    for md_file in sorted(corpus_dir.glob("*.md")):
        docs.append({"text": md_file.read_text(encoding="utf-8"),
                     "source": md_file.name})
    return docs


def chunk_documents(documents, chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP):
    """Mirror of app/rag/ingest.chunk_documents — SAME splitter, params and id format
    so the pids here equal the ChromaDB ids ({source}::{i})."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=len,
        is_separator_regex=False,
    )
    chunks = []
    for doc in documents:
        for i, chunk_text in enumerate(splitter.split_text(doc["text"])):
            chunks.append({"id": f"{doc['source']}::{i}",
                           "text": chunk_text,
                           "source": doc["source"]})
    return chunks


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", default=DEFAULT_CORPUS)
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("--model", default=EMBED_MODEL)
    ap.add_argument("--query", default=TARGET_QUERY)
    ap.add_argument("--query-id", default=QUERY_ID)
    args = ap.parse_args()

    docs = load_documents(args.corpus)
    chunks = chunk_documents(docs)
    print(f"Loaded {len(docs)} docs -> {len(chunks)} chunks")

    # Embed query + all chunks; pick the legit chunk that ranks #1 today (Pgold).
    model = SentenceTransformer(args.model)
    chunk_texts = [c["text"] for c in chunks]
    chunk_emb = model.encode(chunk_texts, normalize_embeddings=True,
                             show_progress_bar=True, convert_to_tensor=True)
    q_emb = model.encode([args.query], normalize_embeddings=True,
                         convert_to_tensor=True)
    sims = st_util.cos_sim(q_emb, chunk_emb)[0]
    top_idx = int(sims.argmax())
    pgold = chunks[top_idx]
    print(f"\nPgold (current top-1 for query): {pgold['id']}  "
          f"cos={float(sims[top_idx]):.4f}")
    print(f"  preview: {pgold['text'][:120].replace(chr(10),' ')}...")

    # --- Write BEIR files ---
    out = Path(args.out)
    (out / "qrels").mkdir(parents=True, exist_ok=True)

    with open(out / "corpus.jsonl", "w", encoding="utf-8") as f:
        for c in chunks:
            f.write(json.dumps({"_id": c["id"], "title": "", "text": c["text"]},
                               ensure_ascii=False) + "\n")

    with open(out / "queries.jsonl", "w", encoding="utf-8") as f:
        f.write(json.dumps({"_id": args.query_id, "text": args.query},
                           ensure_ascii=False) + "\n")

    with open(out / "qrels" / "test.tsv", "w", encoding="utf-8") as f:
        f.write("query-id\tcorpus-id\tscore\n")
        f.write(f"{args.query_id}\t{pgold['id']}\t1\n")

    print(f"\nWrote BEIR dataset to {out.resolve()}")
    print("  corpus.jsonl, queries.jsonl, qrels/test.tsv")


if __name__ == "__main__":
    main()
