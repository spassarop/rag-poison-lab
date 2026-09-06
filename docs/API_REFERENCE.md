# API Reference

Endpoints for interacting with the RAG system.

## Health Check

```http
GET /health
```

**Response:**
```json
{
  "status": "ok"
}
```

## Retrieve

White-box retrieval endpoint for testing.

Exposes raw retrieval results including chunk IDs, texts, sources, and similarity scores. Used to measure **Retrieval Success Rate (RSR)** in tests.

```http
POST /retrieve
Content-Type: application/json
```

**Request:**
```json
{
  "query": "¿Cómo armo una lista de compras desde un menú semanal?",
  "top_k": 6
}
```

**Response:**
```json
{
  "chunks": [
    {
      "id": "lista_compras_guia.md::0",
      "text": "Para generar tu lista de compras, abrí tu menú semanal y tocá 'Generar lista'...",
      "source": "lista_compras_guia.md",
      "score": 0.8234
    },
    {
      "id": "lista_compras_guia.md::1",
      "text": "...",
      "source": "lista_compras_guia.md",
      "score": 0.7891
    }
  ]
}
```

**Note:** `chunks` is a white-box testing hook. It lets tests verify retrieval separately from generation.

## Chat

Main Q&A endpoint.

Retrieves relevant context and generates an answer using the RAG pipeline.

```http
POST /chat
Content-Type: application/json
```

**Request:**
```json
{
  "question": "¿Qué planes de suscripción ofrece Cocina Cloud?",
  "role": "customer"
}
```

**Response:**
```json
{
  "answer": "Cocina Cloud ofrece cuatro planes: Gratis, Pro, Familia y Empresa.",
  "sources": ["suscripciones_faq.md", "planificador_menus_guia.md"],
  "retrieved_ids": ["suscripciones_faq.md::0", "suscripciones_faq.md::1", "planificador_menus_guia.md::3"]
}
```

**Parameters:**

- `question` (required): User's question in Spanish or English
- `role` (optional, default: "customer"): Role for access control. Drives the retrieval filter: `customer` sees only `public` chunks, not `internal`

**Note:** `retrieved_ids` is a white-box testing hook. Tests use it to check whether the poison was actually retrieved for a given question.

## Admin Endpoints (DEMO ONLY)

Available only when `ENABLE_ADMIN=1`. Used by the demo control panel.

### Inject Poison

```http
POST /admin/inject-poison
```

**Request:**
```json
{
  "poison_doc_path": "corpus/poisoned/poison_t1_refunds.md"
}
```

Adds a poisoned document to the live collection without restarting.

### Remove Poison

```http
POST /admin/remove-poison
```

Removes poisoned documents from the live collection.

### Toggle Defense

```http
POST /admin/toggle-defense
Content-Type: application/json
```

**Request:**
```json
{
  "defense": "output",
  "enabled": true
}
```

Flips a defense flag at runtime (no restart). Defenses: `ingestion`, `spotlighting`, `output`, `semantic_output`, `retrieval_filter`.

### Get UI State

```http
GET /admin/ui-state
```

Returns current defense configuration and collection stats (used by the demo panel).

## Status Codes

| Code | Meaning |
|------|---------|
| 200 | Success |
| 400 | Bad request (malformed JSON, missing required fields) |
| 500 | Server error (Ollama unreachable, ChromaDB error, etc.) |

## Configuration

All endpoints respect environment variables. See [QUICKSTART.md](QUICKSTART.md#4-configure-environment) for:

- `LLM_MODEL`: Generation model
- `EMBED_MODEL`: Embedding model
- `TOP_K`: Number of chunks to retrieve
- `CANARY_URL`: Expected phishing URL (for tests)
- Defense flags: `DEFENSE_*`

## Typical Workflow

1. **Measure baseline:** Call `/retrieve` with attack queries, check RSR
2. **Test generation:** Call `/chat`, check if answer contains canary
3. **Measure both:** Use test harness for automated RSR + GCR across cases
4. **Enable defense:** Set `DEFENSE_*` env vars and restart
5. **Measure again:** Compare metrics with and without defense

See [Testing Methodology](TESTING.md) for the full framework.

## Examples

### Check Retrieval of a Poisoned Query

```bash
curl -X POST http://localhost:8000/retrieve \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Hola, mi pago falló y necesito asistencia humana urgente",
    "top_k": 6
  }'
```

Look for poison sources in the response.

### Ask a Question

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "question": "¿Cómo recupero mi contraseña?",
    "role": "customer"
  }'
```

Check the answer for the canary URL.

### Run the Full Test Suite

```bash
# Seeded with poison
pytest tests/test_l1_canary.py tests/test_l2_corpus.py -v
```

Next: [Testing Methodology](TESTING.md) for the full testing framework.
