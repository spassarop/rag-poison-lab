"""FastAPI application for RAG Poisoning Lab.

Exposes three endpoints:
- GET /health: Health check
- POST /retrieve: White-box retrieval endpoint (for testing)
- POST /chat: Main Q&A endpoint
"""
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional
import time
from urllib.parse import urlparse
import chromadb
from contextlib import asynccontextmanager

from app.config import settings
from app.rag.retriever import Retriever
from app.rag.generator import Generator
from app.rag.pipeline import RAGPipeline


# Pydantic models for request/response
class RetrieveRequest(BaseModel):
    query: str = Field(..., description="Search query")
    top_k: int = Field(default=4, ge=1, le=20, description="Number of chunks to retrieve")


class RetrieveChunk(BaseModel):
    id: str
    text: str
    source: str
    score: float


class RetrieveResponse(BaseModel):
    chunks: List[RetrieveChunk]


class ChatRequest(BaseModel):
    question: str = Field(..., description="User's question")
    role: str = Field(default="customer", description="User role (for future filtering)")


class ChatResponse(BaseModel):
    answer: str
    sources: List[str]
    retrieved_ids: List[str]


class HealthResponse(BaseModel):
    status: str


# Global state for RAG components (initialized at startup)
rag_pipeline: Optional[RAGPipeline] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle manager."""
    global rag_pipeline

    # Startup: Initialize RAG components
    print("🚀 Initializing RAG components...")

    # Connect to ChromaDB
    if settings.chroma_path.startswith("http"):
        # Remote Chroma (Docker). Parsear host+port: HttpClient espera host SIN
        # esquema y el puerto por separado. Antes se pasaba "chroma:8000" como
        # host -> URL malformada. urlparse lo separa bien.
        parsed = urlparse(settings.chroma_path)
        chroma_client = chromadb.HttpClient(
            host=parsed.hostname,
            port=parsed.port or 8000,
        )
    else:
        # Local persistent Chroma
        chroma_client = chromadb.PersistentClient(path=settings.chroma_path)

    # Get collection (must already exist from seed_db.py).
    # Retry con backoff: el contenedor chroma puede tardar en aceptar conexiones
    # aunque el healthcheck ya pase. App-level retry = robusto en produccion.
    last_err = None
    for attempt in range(1, 11):
        try:
            collection = chroma_client.get_collection(name=settings.chroma_collection)
            count = collection.count()
            print(f"✅ Connected to ChromaDB collection '{settings.chroma_collection}' ({count} chunks)")
            last_err = None
            break
        except Exception as e:
            last_err = e
            print(f"⏳ Chroma no listo (intento {attempt}/10): {e}")
            time.sleep(2)
    if last_err is not None:
        print(f"❌ Failed to get collection '{settings.chroma_collection}': {last_err}")
        print("   Run 'python scripts/seed_db.py' first to create and populate the collection.")
        raise last_err

    # Initialize retriever
    retriever = Retriever(
        collection=collection,
        embed_model_name=settings.embed_model
    )
    print(f"✅ Retriever initialized with model '{settings.embed_model}'")

    # Initialize generator
    generator = Generator(
        model_name=settings.llm_model,
        base_url=settings.ollama_base_url
    )
    print(f"✅ Generator initialized with model '{settings.llm_model}'")

    # Initialize pipeline
    rag_pipeline = RAGPipeline(
        retriever=retriever,
        generator=generator,
        top_k=settings.top_k
    )
    print(f"✅ RAG pipeline ready (top_k={settings.top_k})")

    yield

    # Shutdown: cleanup if needed
    print("👋 Shutting down...")


# Create FastAPI app
app = FastAPI(
    title="RAG Poisoning Lab API",
    description="Educational demo of RAG poisoning attacks and defenses",
    version="0.1.0",
    lifespan=lifespan
)


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    return {"status": "ok"}


@app.post("/retrieve", response_model=RetrieveResponse)
async def retrieve_chunks(request: RetrieveRequest):
    """White-box retrieval endpoint for testing.

    This endpoint exposes the raw retrieval results, including chunk IDs,
    texts, sources, and similarity scores. It's designed for testing the
    Retrieval Success Rate (RSR) metric.

    NOTE: In production systems, exposing raw retrieval results is generally
    not recommended. This is a testing hook for educational purposes.
    """
    if rag_pipeline is None:
        raise HTTPException(status_code=503, detail="RAG pipeline not initialized")

    try:
        chunks = rag_pipeline.retriever.retrieve(
            query=request.query,
            top_k=request.top_k
        )
        return {"chunks": chunks}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Retrieval failed: {str(e)}")


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Main Q&A endpoint using RAG pipeline.

    Retrieves relevant context from the knowledge base and generates an answer
    using the LLM. Returns the answer along with source documents and retrieved
    chunk IDs (for testing purposes).
    """
    if rag_pipeline is None:
        raise HTTPException(status_code=503, detail="RAG pipeline not initialized")

    try:
        result = rag_pipeline.answer(
            question=request.question,
            role=request.role
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chat failed: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
