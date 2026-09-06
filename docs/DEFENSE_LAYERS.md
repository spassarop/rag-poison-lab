# Defense Layers

Six controls across four stages. Each environment flag starts `off` so you can show each one flipping a test from red to green.

## Defense Table

| Stage | Control | Flag | Catches | Misses |
|-------|---------|------|---------|--------|
| Ingestion | Signature scanner (+ optional Veritensor) | `DEFENSE_INGESTION=signatures` | Overt injection + stealth (HTML, white text, zero-width, base64) | Fluent plausible injections, GASLITE |
| Ingestion | Perplexity anomaly filter | `DEFENSE_INGESTION=anomaly` | Non-fluent GASLITE | Fluent text, fluent GASLITE variant |
| Prompt | Spotlighting (datamarking) | `DEFENSE_SPOTLIGHTING=on` | Instruction-following from context (reduces GCR) | Does not eliminate |
| Output | Output guard (external-URL allowlist) | `DEFENSE_OUTPUT=on` | Non-official URLs reaching user | Knowledge corruption (no URL) |
| Output | Semantic output guard (LLM judge) | `DEFENSE_SEMANTIC_OUTPUT=on` | Knowledge corruption (false/unsafe facts) | Adds latency, non-determinism |
| Retrieval | Role filter (access control) | `DEFENSE_RETRIEVAL_FILTER=on` | Customer retrieving internal chunks | None |

`DEFENSE_INGESTION` takes a comma-set: `signatures,anomaly`

## The Key Chain: How Each Layer Fits

### 1. Signature and Pattern Scanner

Catches loud attacks (overt injection markers, obfuscation) but misses fluent plausible-content injections and GASLITE (no suspicious strings).

**What it does:**
- Scans for known patterns: "ignore previous instructions", "follow these rules", etc.
- Flags HTML comments, base64 blobs, zero-width characters

**What it misses:**
- Plausible refund support requests with phishing URLs hidden in the text
- Gradient-optimized passages with no human-suspicious strings

**Production option:** Veritensor (`github.com/arsbr/Veritensor`). A builtin `SignatureScanner` ships so the demo runs without it.

### 2. Anomaly Filter (Perplexity Proxy)

Catches the non-fluent GASLITE passage that signatures miss. The scorer is pluggable: you can drop in a real GPT-2 perplexity scorer (same interface) for higher fidelity.

**What it does:**
- Calibrates a unigram model on the benign corpus with a zero-false-positive threshold
- Flags documents that read as garbled or statistically improbable

**What it misses:**
- Fluent text (by definition, GASLITE-Flu would evade perplexity)

**Limitation:** Per the GASLITE paper, a fluent GASLITE variant would evade perplexity, so the arms race continues. Generation-stage controls still matter.

### 3. Spotlighting (Prompt Datamarking)

Acts at generation time. Tags retrieved chunks (e.g., `[RETRIEVED: source.md]`) to reduce instruction-following. Reduces but does not eliminate injection.

**What it does:**
- Marks all retrieved context as external data
- Instructs the model to treat it as reference, not commands

**What it misses:**
- Well-framed plausible injections that the model doesn't recognize as instructions
- Cannot eliminate injection on its own

**Key insight:** Spotlighting reduces GCR transversally (all techniques) but other controls are needed.

### 4. Output Guard (URL Allowlist)

Scans generated answers for external URLs and only allows official domains.

**What it does:**
- Intercepts any non-official URL (the phishing link, fake contact forms, etc.)
- Replaces it or blocks the answer

**What it misses:**
- Knowledge corruption (false facts with no URL)
- Safe-sounding false information (e.g., cooked chicken is safe out of the fridge for 8 hours)

**Configuration:** Set official domains in `DEFENSE_OUTPUT` settings.

### 5. Semantic Output Guard (LLM Judge)

Closes the gap left by the URL guard. Runs a universal LLM judge with a generic safety rubric on every answer.

**How it works:**
- Judge writes a free-text ANALYSIS of each claim
- Commits to verdict as `VEREDICTO: SEGURA|INSEGURA`
- For runtime mitigation: any model flagging it → unsafe (minority-alert)

**What it catches:**
- Knowledge corruption: false or unsafe facts even without URLs
- Food safety misinformation, allergen issues, medical claims

**Trade-offs:**
- Adds an LLM call per answer (latency)
- Non-deterministic on borderline facts
- Softer claims (trivia, disputed origins) are harder to catch than safety-critical corruption

### 6. Role Filter (Access Control)

The "WHERE clause nobody writes": with it on, `role=customer` cannot retrieve `sensitivity=internal` chunks.

**What it does:**
- Tags documents with `sensitivity` metadata
- Filters top-k by the user's role at retrieval time

**What it misses:**
- Nothing (it's a simple WHERE clause), but only works if documents are tagged

**Deployment:** Seed confidential docs in `corpus/internal/` and set `DEFENSE_RETRIEVAL_FILTER=on`.

## How to Enable and Compare

One control at a time (re-seed when toggling INGESTION controls):

```bash
DEFENSE_INGESTION=signatures,anomaly python scripts/seed_db.py --with-poison
DEFENSE_SPOTLIGHTING=on DEFENSE_OUTPUT=on uvicorn app.main:app

pytest tests/test_defenses.py -v                # Deterministic: which layer catches what
python scripts/compare_defenses.py              # Off-vs-on table (RSR/GCR), the closing slide
```

**Test framework:**
- `tests/test_defenses.py`: Asserts function-level logic (signatures catch loud, anomaly catches GASLITE, etc.)
- `scripts/compare_defenses.py`: Runs full corpus per defense config and prints RSR/GCR comparison

## The Story in Red→Green

**Start:** All defenses off. Tests are red.

**Add signature scanner:** Catches Tier 1 and 2 (overt injection), L2 tests go green.

**Add anomaly filter:** Catches Tier 3 non-fluent, more tests green.

**Add spotlighting:** Reduces GCR even for cases that get retrieved, more greens.

**Add output guard:** Stops phishing URLs (anything with `expected_canary` as a URL), hard gates pass.

**Add semantic guard:** Catches knowledge corruption (cases with `judge_rubric` instead of canary), L3 tests pass.

**Add role filter:** Blocks cross-role exfiltration, confidentiality is enforced.

## Disclaimers

- Spotlighting reduces, it does not eliminate, injection
- The anomaly filter here is a lightweight perplexity proxy (swap in GPT-2 for production fidelity)
- Veritensor is Apache-2.0 and optional
- No single layer is sufficient. Defense works in depth.

## Next Steps

- **How to test:** [Testing Methodology](TESTING.md)
- **See attacks it stops:** [Attack Tiers](ATTACKS/)
- **Setup:** [Quick Start](QUICKSTART.md)
