# Quick Start

Get RAG Poisoning Lab running in 5 minutes.

## Prerequisites

- **Python 3.10+** (3.11 recommended)
- **Ollama** with `llama3.1:8b-instruct-q4_K_M` model downloaded
- **Docker** (optional, for ChromaDB container)
- **Git**

## Local Setup

### 1. Clone and Create Virtual Environment

```bash
git clone https://github.com/spassarop/rag-poison-lab.git
cd rag-poison-lab
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt -r requirements-dev.txt
```

### 3. Pull the Model

```bash
ollama pull llama3.1:8b-instruct-q4_K_M
```

### 4. Configure Environment

```bash
cp .env.example .env
# Edit .env if needed (defaults work for local development)
```

### 5. Generate Poisoned Documents

```bash
python attacks/generate_poisoned_corpus.py
```

### 6. Seed the Database

```bash
# Clean baseline (no poison):
python scripts/seed_db.py

# Or with poison for the demo:
python scripts/seed_db.py --with-poison
```

### 7. Start the API

```bash
uvicorn app.main:app --reload
```

### 8. Test the API

```bash
curl http://localhost:8000/health
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"question": "¿Cómo pido un reembolso de mi suscripción?"}'
```

## Docker Setup (Optional)

To run ChromaDB and the API in containers:

```bash
# Generate corpus first (from host, before Docker)
python attacks/generate_corpus.py --count 50 --output corpus/legit

# Start services
docker compose up -d

# Seed database (connects to containerized Chroma)
python scripts/seed_db.py --chroma-path http://localhost:8001

# Restart API after seeding
docker compose restart api

# API available at http://localhost:8000
```

**Editing app code with Docker:** The `api` image bakes `app/` at build time, with only `corpus/` and `attacks/` mounted. After changing code under `app/`, rebuild with `docker compose up -d --build api`. A plain `restart` reruns the old image.

## Run the Demo

```bash
bash scripts/run_demo.sh
```

This narrates the full arc: clean assistant → poisoned → metrics that expose damage → defenses that fix it.

## API Quick Reference

### Health Check
```bash
GET /health
```

### Retrieve Chunks
```bash
POST /retrieve
Content-Type: application/json

{
  "query": "¿Cómo armo una lista de compras?",
  "top_k": 6
}
```

### Chat
```bash
POST /chat
Content-Type: application/json

{
  "question": "¿Qué planes ofrece Cocina Cloud?",
  "role": "customer"
}
```

See [API Reference](API_REFERENCE.md) for full details.

## Run Tests

```bash
# Unit tests (no API needed)
pytest tests/test_metrics.py -v

# Full harness (seeded API required)
pytest tests/test_l1_canary.py -v
pytest tests/test_l2_corpus.py -v

# HTML report
pytest tests/ --html=reports/report.html
```

## Next Steps

- **Understand the threat:** [Threat Model](THREAT_MODEL.md)
- **Learn how to test:** [Testing Methodology](TESTING.md)
- **See defense details:** [Defense Layers](DEFENSE_LAYERS.md)
- **Add your own attack:** [Contributing](../CONTRIBUTING.md)
