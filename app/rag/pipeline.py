"""RAG pipeline: orchestrates retrieval and generation."""
from typing import Dict, Any, List


class RAGPipeline:
    """End-to-end RAG pipeline combining retrieval and generation."""

    def __init__(self, retriever, generator, top_k: int = 4):
        """Initialize pipeline with retriever and generator.

        Args:
            retriever: Retriever instance
            generator: Generator instance
            top_k: Default number of chunks to retrieve
        """
        self.retriever = retriever
        self.generator = generator
        self.top_k = top_k

    def answer(
        self,
        question: str,
        role: str = "customer",
        top_k: int = None
    ) -> Dict[str, Any]:
        """Answer a question using RAG pipeline.

        Args:
            question: User's question
            role: User role (for future role-based filtering in Fase 6)
            top_k: Number of chunks to retrieve (overrides default)

        Returns:
            Dict with keys:
                - answer: Generated answer text
                - sources: List of unique source filenames
                - retrieved_ids: List of chunk IDs that were retrieved
        """
        k = top_k if top_k is not None else self.top_k

        # Retrieve relevant chunks
        chunks = self.retriever.retrieve(query=question, top_k=k)

        # Generate answer from chunks
        answer_text = self.generator.generate(question=question, context_chunks=chunks)

        # Extract unique sources and chunk IDs
        sources = sorted(set(chunk["source"] for chunk in chunks))
        retrieved_ids = [chunk["id"] for chunk in chunks]

        return {
            "answer": answer_text,
            "sources": sources,
            "retrieved_ids": retrieved_ids
        }
