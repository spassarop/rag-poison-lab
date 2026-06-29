"""RAG pipeline: orchestrates retrieval and generation."""
from typing import Dict, Any, List


class RAGPipeline:
    """End-to-end RAG pipeline combining retrieval and generation."""

    def __init__(self, retriever, generator, top_k: int = 6):
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
            role: User role (for future role-based filtering at the retrieval layer)
            top_k: Number of chunks to retrieve (overrides default)

        Returns:
            Dict with keys:
                - answer: Generated answer text
                - sources: List of unique source filenames
                - retrieved_ids: List of chunk IDs that were retrieved
        """
        from app.config import settings

        k = top_k if top_k is not None else self.top_k

        # Retrieve relevant chunks (role drives the retrieval access-control filter)
        chunks = self.retriever.retrieve(query=question, top_k=k, role=role)

        # Generate answer from chunks
        answer_text = self.generator.generate(question=question, context_chunks=chunks)

        # Output guard (last line of defense): scan/sanitize before returning.
        if settings.defense_output == "on":
            from app.defenses.output_guard import scan_output
            _safe, answer_text = scan_output(answer_text)

        # Semantic output guard: LLM judge with a generic safety rubric — mitigates
        # knowledge corruption (false facts with no URL) the URL guard cannot see.
        if settings.defense_semantic_output == "on":
            from app.defenses.semantic_guard import scan_semantic
            _safe_sem, answer_text = scan_semantic(question, answer_text)

        # Extract unique sources and chunk IDs
        sources = sorted(set(chunk["source"] for chunk in chunks))
        retrieved_ids = [chunk["id"] for chunk in chunks]

        return {
            "answer": answer_text,
            "sources": sources,
            "retrieved_ids": retrieved_ids
        }
