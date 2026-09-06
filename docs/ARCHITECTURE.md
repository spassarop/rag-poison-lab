# Architecture

System design and where attacks and defenses land.

## Data Flow

```
Documents (.md)
    ↓ chunk + embed
ChromaDB (cocina_kb)
    ↓
Retriever (semantic search, top-k)
    ↓
Prompt builder (adds context)
    ↓
LLM (Ollama)
    ↓
Answer
```

## Attack and Defense Placement

```
Documents (.md) → Ingestion Guard (signatures, anomaly) → ChromaDB
                                                           ↓
User Query ──────────────────────────→ Retriever + Role Filter ──→ Prompt Builder (Spotlighting)
                                                                         ↓
                                                                       LLM
                                                                         ↓
                                                         Output Guard (URL + Semantic Judge)
                                                                         ↓
                                                                       Answer
```

**Attacker's foothold:** A poisoned document enters the knowledge base.

**Measurement points:**
- **RSR (Retrieval Success Rate):** Measured at the Retriever. Is the poison in top-k?
- **GCR (Generation Compromise Rate):** Measured at the Answer. Does the model obey the poison?

**Defense stages:**
1. **Ingestion:** Signature scanner, optional Veritensor, perplexity anomaly filter
2. **Retrieval:** Role-based access control (prevent `customer` from seeing `internal` chunks)
3. **Prompt:** Spotlighting/datamarking (tag retrieved data to reduce instruction-following)
4. **Output:** URL allowlist guard (official domains only) + semantic LLM judge (catch false facts)

## Core Components

### app/
FastAPI application with two modes:

- **Black-box:** `/health`, `/chat`, `/retrieve` (what end-users see)
- **White-box testing:** `/retrieve` exposes chunk IDs and scores for measuring RSR

### app/rag/
RAG pipeline:
- `ingest.py`: Document loading, chunking, embedding, ChromaDB storage
- `retriever.py`: Semantic search plus role filter
- `generator.py`: LLM-based answer generation plus spotlighting
- `pipeline.py`: Orchestrates retrieval plus generation plus output guard

### app/defenses/
Environment-toggled controls:
- `ingestion_guard.py`: Signature scanner
- `anomaly.py`: Perplexity proxy (catches non-fluent GASLITE)
- `spotlighting.py`: Prompt datamarking
- `output_guard.py`: External-URL output scan
- `semantic_guard.py`: LLM-judge output guard (mitigates knowledge corruption)
- `llm_judge.py`: Shared LLM-as-judge core

### corpus/
Knowledge base documents:
- `core/`: CURATED committed demo KB (concise, correct, high retrieval signal-to-noise)
- `legit/`: Generated BULK filler for scale (optional)
- `internal/`: Confidential docs (role=customer cannot retrieve)
- `poisoned/`: Poisoned docs: tiers 1-2 (generated) + tier 3 GASLITE (precomputed)

### attacks/
Attack tooling:
- `generate_corpus.py`: Ollama-based legitimate corpus generator
- `generate_poisoned_corpus.py`: Builds poisoned docs from the contract
- `corpus_attacks.yaml`: Parameterized attack cases (the test contract)
- `gaslite/`: Tier 3 gradient-optimized passage (precomputed offline)

### tests/
Test harness:
- `metrics.py`: RSR/GCR metrics with injectable functions
- `test_metrics.py`: Unit tests for the metrics
- `test_l1_canary.py`: End-to-end invariant: answer must not contain canary
- `test_l2_corpus.py`: Per-case generation compromise gate
- `test_l3_llm_judge.py`: Semantic evaluation (non-blocking)
- `test_defenses.py`: Which layer catches what

## Key Design Choices

**Dual metrics (RSR + GCR):** Separates retrieval success from generation compliance. An attack can win retrieval but lose generation.

**Attack cases as a contract:** `corpus_attacks.yaml` defines what to test. The same contract feeds the metrics, the baseline script, and the test harness. Change the canary, regenerate, re-measure.

**Precomputed Tier 3:** GASLITE is run offline once (GPU/Colab), then the resulting passage is committed as an artifact. Never run in CI or against the system under test (it would make CI non-deterministic and slow).

**Black-box test harness:** Tests call `/chat` and `/retrieve` over HTTP. No system under test imports. A tester can point it at any RAG system.

**Role filter as access control:** Documents tagged `sensitivity=internal` are invisible to `role=customer`. A simple example of least-privilege in RAG.

**Spotlighting at prompt time:** Tags retrieved chunks (e.g., `[RETRIEVED: source.md]`) to reduce injection success. Reduces but doesn't eliminate—other controls still needed.

## Environment Configuration

See [Configuration](../docs/QUICKSTART.md#4-configure-environment) for all variables. Key ones:

- `DEFENSE_INGESTION`: Turn on/off signature scanner, anomaly filter
- `DEFENSE_SPOTLIGHTING`: Prompt datamarking
- `DEFENSE_OUTPUT`: URL allowlist guard
- `DEFENSE_SEMANTIC_OUTPUT`: LLM-judge output guard
- `DEFENSE_RETRIEVAL_FILTER`: Role-based access control

All default to `off` so you can show each control flipping a test from red to green.

## Next

- **How to measure attacks:** [Testing Methodology](TESTING.md)
- **What each defense does:** [Defense Layers](DEFENSE_LAYERS.md)
- **API details:** [API Reference](API_REFERENCE.md)
