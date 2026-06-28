"""Retrieval module: semantic search over ChromaDB using dense embeddings."""
from typing import List, Dict, Any, Optional
from sentence_transformers import SentenceTransformer


def role_where(role: str, enabled: bool) -> Optional[Dict[str, str]]:
    """ChromaDB `where` clause for retrieval-time access control.

    With the filter enabled, the public-facing "customer" role is restricted to
    chunks marked sensitivity="public"; privileged roles (anything else) see all.
    Pure function so it can be unit-tested without ChromaDB.
    """
    if enabled and role == "customer":
        return {"sensitivity": "public"}
    return None


class Retriever:
    """Dense retrieval using sentence-transformers embeddings and ChromaDB."""

    def __init__(self, collection, embed_model_name: str = "paraphrase-multilingual-MiniLM-L12-v2"):
        """Initialize retriever with ChromaDB collection and embedding model.

        Args:
            collection: ChromaDB collection instance
            embed_model_name: Name of sentence-transformers model
        """
        self.collection = collection
        self.embedder = SentenceTransformer(embed_model_name)

    def retrieve(self, query: str, top_k: int = 6, role: str = "customer") -> List[Dict[str, Any]]:
        """Retrieve top-k most relevant chunks for a query.

        Args:
            query: User query string
            top_k: Number of chunks to retrieve
            role: Caller role. With DEFENSE_RETRIEVAL_FILTER=on, a "customer" only
                  retrieves chunks marked sensitivity="public" (access control —
                  "the WHERE clause nobody writes"). Privileged roles see everything.

        Returns:
            List of dicts with keys: 'id', 'text', 'source', 'score'
            Sorted by descending relevance (cosine similarity)
        """
        from app.config import settings

        # Generate query embedding
        query_embedding = self.embedder.encode([query])[0]

        # Retrieval-time access control: restrict customers to public chunks.
        where = role_where(role, settings.defense_retrieval_filter == "on")

        # Query ChromaDB
        results = self.collection.query(
            query_embeddings=[query_embedding.tolist()],
            n_results=top_k,
            where=where,
            include=["documents", "metadatas", "distances"]
        )

        # Parse results into structured format
        chunks = []
        if results["ids"] and len(results["ids"]) > 0:
            for i in range(len(results["ids"][0])):
                chunk_id = results["ids"][0][i]
                document = results["documents"][0][i]
                metadata = results["metadatas"][0][i]
                distance = results["distances"][0][i]

                # ChromaDB returns distance (lower = better); convert to similarity score
                # For cosine distance: similarity = 1 - distance
                score = 1.0 - distance

                chunks.append({
                    "id": chunk_id,
                    "text": document,
                    "source": metadata.get("source", "unknown"),
                    "score": round(score, 4)
                })

        # TODO: Apply retrieval-time defenses here
        # - Role-based filtering (if user role doesn't have access to certain sources)
        # - Similarity threshold filtering (reject low-score chunks)
        # filtered_chunks = apply_retrieval_filters(chunks, role, threshold)

        return chunks
