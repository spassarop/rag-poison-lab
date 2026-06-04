# RAG Poisoning Lab

Production-grade demonstration of **RAG poisoning attacks** and **defensive testing methodologies** for retrieval-augmented generation systems.

## Overview

This project demonstrates how a single poisoned document can compromise a RAG system, and more importantly, provides a **replicable testing framework** that QA engineers can adapt to test RAG poisoning vulnerabilities in their own systems.

### The Scenario

**Acme Cloud** is a fictional SaaS platform with a support chatbot powered by RAG. The bot answers customer questions by retrieving relevant chunks from a knowledge base (policies, guides, FAQs) and generating responses with an LLM.

An attacker introduces a poisoned document into the knowledge base containing:
- Phishing URLs: `http://secure-login-update.acme-phish.test/login`
- Instruction injection: prompts that override the system's intended behavior
- Social engineering content disguised as legitimate documentation

The canary URL uses the `.test` TLD (RFC 6761) to ensure it never resolves to a real site.

### Key Features

- **Production-grade RAG stack**: FastAPI, ChromaDB, sentence-transformers, Ollama
- **Dual-metric testing**: Separate measurement of retrieval success and generation compromise
- **Attack escalation**: From query-aligned poisoning to stealth techniques to white-box gradient optimization
- **Defense in depth**: Layered controls at ingestion, retrieval, prompt, and output stages
- **Automated test harness**: pytest-based framework with multiple testing levels

## ⚠️ Disclaimers

- **Educational and research purposes only**. This project demonstrates security vulnerabilities to help developers and testers build more secure RAG systems.
- **Fictional scenario**: "Acme Cloud" and all associated data are fictional. The phishing URL uses the reserved `.test` TLD and does not point to any real site.
- **Testing hooks exposed**: The API exposes retrieval internals (chunk IDs, scores) as white-box testing hooks. This is **not** recommended for production systems but is essential for measuring attack success rates.
- **Responsible use**: Attack techniques (especially GASLITE gradient-based poisoning) should only be used on systems you own or have explicit authorization to test.
- **No real payloads**: Do not modify this project to include actual malicious content that could harm real systems.

## Technology Stack

| Component | Technology | Version/Notes |
|-----------|-----------|---------------|
| Language | Python | 3.10+ (3.11 recommended) |
| Dependencies | pip + venv | `requirements.txt` |
| API Framework | FastAPI | REST API with Pydantic models |
| ASGI Server | uvicorn | Development and production |
| Vector Database | ChromaDB | Persistent storage, cosine similarity |
| Embeddings | sentence-transformers | `all-MiniLM-L6-v2` (384 dim) |
| Text Chunking | langchain-text-splitters | Recursive character splitter |
| LLM | Ollama | `llama3.1:8b-instruct-q4_K_M` (local) |
| Testing | pytest | Test harness with HTML reports |
| Containerization | Docker Compose | ChromaDB containerized (optional) |
| Defense Library | Veritensor | RAG firewall (`veritensor[rag]`) |

### Infrastructure Setup

For efficient model management:
- **Ollama**: Runs natively on the host (models already downloaded, no re-download on container restart)
- **ChromaDB**: Runs in Docker container with persistent volume
- **API**: Can run natively or in Docker (connects to host Ollama via `host.docker.internal`)

## Project Structure

```
rag-poison-lab/
├── README.md                   # This file
├── LICENSE                     # Apache 2.0
├── .gitignore
├── .env.example                # Environment template
├── requirements.txt            # Python dependencies
├── requirements-dev.txt        # Dev/test dependencies
├── docker-compose.yml          # Container orchestration
├── Dockerfile                  # API container image
│
├── app/                        # FastAPI application
│   ├── __init__.py
│   ├── config.py               # Settings from environment
│   ├── main.py                 # API endpoints: /health, /retrieve, /chat
│   └── rag/                    # RAG pipeline components
│       ├── __init__.py
│       ├── ingest.py           # Document loading, chunking, embedding, storage
│       ├── retriever.py        # Semantic search over ChromaDB
│       ├── generator.py        # LLM-based answer generation
│       └── pipeline.py         # Orchestrates retrieval + generation
│
├── corpus/                     # Knowledge base documents
│   ├── legit/                  # 50 legitimate Acme Cloud docs (.md)
│   └── poisoned/               # Attack documents (created in later phases)
│
├── attacks/                    # Attack tooling
│   ├── generate_corpus.py      # Ollama-based corpus generator
│   └── corpus_attacks.yaml     # Parameterized attack cases (later)
│
├── scripts/                    # Utility scripts
│   ├── seed_db.py              # Ingest corpus into ChromaDB
│   ├── generate_static_corpus.py    # Static corpus generator
│   ├── expand_static_corpus.py      # Corpus expansion (phase 1)
│   └── finalize_corpus.py           # Final corpus completion
│
└── tests/                      # Test harness (created in later phases)
    ├── conftest.py             # pytest fixtures
    └── metrics.py              # RSR and GCR metrics
```

## Installation

### Prerequisites

- **Python 3.10+** (3.11 recommended)
- **Ollama** with `llama3.1:8b-instruct-q4_K_M` model downloaded
- **Docker** (optional, for ChromaDB container)
- **Git**

### Quick Start

```bash
# 1. Clone the repository
git clone https://github.com/yourusername/rag-poison-lab.git
cd rag-poison-lab

# 2. Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt -r requirements-dev.txt

# 4. Pull Ollama model (if not already downloaded)
ollama pull llama3.1:8b-instruct-q4_K_M

# 5. Configure environment
cp .env.example .env
# Edit .env if needed (defaults should work for local development)

# 6. Generate knowledge base corpus (50 documents using Ollama)
python attacks/generate_corpus.py --count 50 --output corpus/legit
# Takes ~5 minutes. Generates realistic Acme Cloud documentation.

# 7. Seed the database
python scripts/seed_db.py

# 8. Start the API
uvicorn app.main:app --reload

# 9. Test the API
curl http://localhost:8000/health
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"question": "How do I request a refund?"}'
```

### Docker Setup (Optional)

To run ChromaDB and the API in containers:

```bash
# Generate corpus first (from host, before Docker)
python attacks/generate_corpus.py --count 50 --output corpus/legit

# Start services
docker compose up -d

# Seed database (run from host, connects to containerized Chroma)
python scripts/seed_db.py --chroma-path http://localhost:8001

# API will be available at http://localhost:8000
```

## API Reference

### Endpoints

#### `GET /health`

Health check.

**Response:**
```json
{
  "status": "ok"
}
```

#### `POST /retrieve`

White-box retrieval endpoint (for testing).

Exposes raw retrieval results including chunk IDs, texts, sources, and similarity scores. Used to measure **Retrieval Success Rate (RSR)** in tests.

**Request:**
```json
{
  "query": "How do I reset my password?",
  "top_k": 4
}
```

**Response:**
```json
{
  "chunks": [
    {
      "id": "faq.md::0",
      "text": "Go to the login page and click 'Forgot Password'...",
      "source": "faq.md",
      "score": 0.8234
    },
    ...
  ]
}
```

#### `POST /chat`

Main Q&A endpoint.

Retrieves relevant context and generates an answer using the RAG pipeline.

**Request:**
```json
{
  "question": "What regions are available?",
  "role": "customer"
}
```

**Response:**
```json
{
  "answer": "Acme Cloud operates in four regions: US-East (Virginia), US-West (Oregon), EU-West (Ireland), and AP-South (Mumbai).",
  "sources": ["regions.md", "faq.md"],
  "retrieved_ids": ["regions.md::0", "regions.md::1", "faq.md::3", "faq.md::5"]
}
```

**Note:** The `role` parameter and `retrieved_ids` field are hooks for future testing features (role-based filtering, retrieval verification).

## Environment Variables

Copy `.env.example` to `.env` and configure:

| Variable | Default | Description |
|----------|---------|-------------|
| `LLM_MODEL` | `llama3.1:8b-instruct-q4_K_M` | Ollama model for generation |
| `JUDGE_MODEL` | `llama3.1:8b-instruct-q4_K_M` | Model for LLM-as-judge evaluation (later) |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server URL |
| `EMBED_MODEL` | `all-MiniLM-L6-v2` | Sentence-transformers embedding model |
| `TOP_K` | `4` | Number of chunks to retrieve |
| `CHROMA_PATH` | `http://localhost:8001` | ChromaDB storage path (or HTTP URL) |
| `CHROMA_COLLECTION` | `acme_kb` | Collection name |
| `CHUNK_SIZE` | `512` | Text chunk size (characters) |
| `CHUNK_OVERLAP` | `64` | Chunk overlap (characters) |
| `CANARY_URL` | `http://secure-login-update.acme-phish.test/login` | Canary token for attack detection |
| `DEFENSE_INGESTION` | `off` | Ingestion defense (`off` or `veritensor`) |
| `DEFENSE_SPOTLIGHTING` | `off` | Prompt spotlighting defense |
| `DEFENSE_OUTPUT` | `off` | Output scanning defense |

Defense flags are set to `off` initially to demonstrate attacks, then activated to show mitigation.

## Testing Methodology

This project provides a systematic approach to testing RAG poisoning:

### Dual Metrics

1. **Retrieval Success Rate (RSR)**: Fraction of attack cases where the poisoned chunk appears in the top-k retrieved results. Measures whether the attack can reach the LLM.

2. **Generation Compromise Rate (GCR)**: Fraction of attack cases where the final answer contains the malicious payload (e.g., canary URL). Measures actual user-facing impact.

A low RSR with high GCR would indicate the retrieval defense is weak. A high RSR with low GCR means the generation defense is working. Both metrics are needed to avoid false negatives.

### Attack Tiers

1. **Query-aligned poisoning**: Documents crafted to rank highly for likely user queries
2. **Stealth/obfuscation**: Hidden text (white-on-white, zero-width chars, HTML comments, base64)
3. **GASLITE**: Gradient-optimized adversarial passages (white-box attack on the embedding model)

## Corpus Generation

The knowledge base must be generated using Ollama before first use (see Quick Start step 6).

### Generate Base Corpus (50 documents)

```bash
python attacks/generate_corpus.py --count 50 --output corpus/legit
```

Creates 50 realistic Acme Cloud documentation files (policies, guides, FAQs, troubleshooting, etc.).

**Time:** ~5 minutes  
**Output:** `corpus/legit/*.md`

### Expand Corpus (Optional)

For stress testing at scale:

```bash
# Expand 50 → 200 documents
python attacks/generate_corpus.py --expand --scale 200

# Use different model
python attacks/generate_corpus.py --count 50 --model llama2:13b
```

**Note:** Ollama generation is non-deterministic. Each run produces different content.

## Development

### Running Tests

Tests will be created in later phases. To run them:

```bash
pytest tests/ -v
pytest tests/test_l1_canary.py --html=reports/report.html
```

### Code Style

```bash
# Format code
black app/ tests/ scripts/

# Lint
flake8 app/ tests/ scripts/
```

## References and Credits

### Research Papers

- **OWASP Top 10 for LLM Applications** - LLM01 (Prompt Injection), LLM02 (Indirect Prompt Injection)
- **PoisonedRAG** (USENIX Security 2025) - arXiv:2402.07867, GitHub: `sleeepeer/PoisonedRAG`
- **GASLITE** (ACM CCS 2025) - arXiv:2412.20953, GitHub: `matanbt/GASLITE`
- **Spotlighting** (Microsoft Research) - arXiv:2403.14720
- **mumoRAG-attacks** (Alan Turing Institute) - "Hidden in the Metadata"

### Inspiration

- `deconvolute-labs/trojan-rag-demo`
- `prompt-security/RAG_Poisoning_POC`

### Defense Tools

- **Veritensor**: `arsbr/Veritensor` (Apache 2.0) - RAG firewall for ChromaDB

## License

Apache 2.0 - See [LICENSE](LICENSE) file.

## Contributing

Contributions welcome! Please:
- Follow existing code style
- Add tests for new features
- Update documentation
- Submit PRs against `main` branch

For major changes, open an issue first to discuss.

## Contact

Questions, issues, or suggestions? Open a GitHub issue or contact the maintainers.

---

**Remember**: This is an educational tool for security research. Use responsibly and only on systems you own or have permission to test.
