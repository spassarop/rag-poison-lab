"""Document ingestion: loading, chunking, embedding, and storage to ChromaDB.

This module provides the ONLY entry point for documents into the vector database.
Defense mechanisms (when active) are applied here before storage.
"""
import os
from pathlib import Path
from typing import List, Dict, Any
from langchain_text_splitters import RecursiveCharacterTextSplitter
from sentence_transformers import SentenceTransformer
import chromadb


def load_documents(corpus_path: str = "corpus/legit") -> List[Dict[str, str]]:
    """Load all Markdown documents from the specified directory.

    Args:
        corpus_path: Path to directory containing .md files

    Returns:
        List of dicts with keys: 'text' (content), 'source' (filename)
    """
    documents = []
    corpus_dir = Path(corpus_path)

    if not corpus_dir.exists():
        raise FileNotFoundError(f"Corpus directory not found: {corpus_path}")

    for md_file in corpus_dir.glob("*.md"):
        with open(md_file, "r", encoding="utf-8") as f:
            content = f.read()
            documents.append({
                "text": content,
                "source": md_file.name
            })

    return documents


def chunk_documents(
    documents: List[Dict[str, str]],
    chunk_size: int = 512,
    chunk_overlap: int = 64
) -> List[Dict[str, Any]]:
    """Split documents into chunks using RecursiveCharacterTextSplitter.

    Args:
        documents: List of documents with 'text' and 'source'
        chunk_size: Maximum size of each chunk in characters
        chunk_overlap: Number of overlapping characters between chunks

    Returns:
        List of chunks with keys: 'id', 'text', 'source'
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=len,
        is_separator_regex=False,
    )

    chunks = []
    for doc in documents:
        text_chunks = splitter.split_text(doc["text"])
        for i, chunk_text in enumerate(text_chunks):
            chunks.append({
                "id": f"{doc['source']}::{i}",
                "text": chunk_text,
                "source": doc["source"]
            })

    return chunks


def embed_and_store(
    chunks: List[Dict[str, Any]],
    collection,
    embed_model_name: str = "all-MiniLM-L6-v2"
) -> int:
    """Generate embeddings and store chunks in ChromaDB collection.

    Args:
        chunks: List of chunks with 'id', 'text', 'source'
        collection: ChromaDB collection instance
        embed_model_name: Name of sentence-transformers model

    Returns:
        Number of chunks stored
    """
    if not chunks:
        return 0

    # Load embedding model
    embedder = SentenceTransformer(embed_model_name)

    # Extract texts and generate embeddings
    texts = [chunk["text"] for chunk in chunks]
    embeddings = embedder.encode(texts, show_progress_bar=True)

    # Prepare data for ChromaDB
    ids = [chunk["id"] for chunk in chunks]
    documents = texts
    metadatas = [{"source": chunk["source"]} for chunk in chunks]

    # Store in collection
    collection.add(
        ids=ids,
        documents=documents,
        embeddings=embeddings.tolist(),
        metadatas=metadatas
    )

    return len(chunks)


def ingest(
    corpus_path: str,
    chroma_client,
    collection_name: str,
    chunk_size: int = 512,
    chunk_overlap: int = 64,
    embed_model: str = "all-MiniLM-L6-v2",
    reset: bool = True
) -> Dict[str, Any]:
    """Main ingestion pipeline: load → chunk → embed → store.

    This is the SINGLE entry point for document ingestion. Defense mechanisms
    will be applied here when activated (Fase 6).

    Args:
        corpus_path: Path to corpus directory
        chroma_client: ChromaDB client instance
        collection_name: Name of the collection
        chunk_size: Size of text chunks
        chunk_overlap: Overlap between chunks
        embed_model: Embedding model name
        reset: If True, delete and recreate collection (idempotent)

    Returns:
        Dict with 'docs_loaded', 'chunks_created', 'chunks_stored'
    """
    # Reset collection if requested (for idempotency)
    if reset:
        try:
            chroma_client.delete_collection(name=collection_name)
        except Exception:
            pass  # Collection might not exist yet

    # Get or create collection
    collection = chroma_client.get_or_create_collection(
        name=collection_name,
        metadata={"hnsw:space": "cosine"}
    )

    # Load documents
    documents = load_documents(corpus_path)

    # Chunk documents
    chunks = chunk_documents(documents, chunk_size, chunk_overlap)

    # TODO (Fase 6): Apply ingestion defense here if DEFENSE_INGESTION is active
    # filtered_chunks = apply_ingestion_defense(chunks) if defense_active else chunks

    # Embed and store
    chunks_stored = embed_and_store(chunks, collection, embed_model)

    return {
        "docs_loaded": len(documents),
        "chunks_created": len(chunks),
        "chunks_stored": chunks_stored
    }
