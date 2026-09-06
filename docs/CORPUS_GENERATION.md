# Corpus Generation

How to build and scale the knowledge base for testing.

## Why Two Corpora?

**Curated core:** Small, committed to git. Each document is a focused, realistic piece of content (a help article, FAQ, recipe guide). Signal-to-noise is high: the retriever reliably surfaces the right chunk.

**Generated bulk:** Optional, for scale testing. Filler documents to grow the corpus to test how poison RSR behaves at larger sizes.

## Curated Core

Located in `corpus/core/`.

No generation needed. The demo KB is committed to the repo:
- One **focused, realistic document** per support topic
- Payments, account management, meal planning, regional cuisine, food safety, allergens, etc.
- Each spans a few chunks like a real help article

**Why it's curated:**
A noisy corpus of near-duplicate variants would rank the wrong doc first, and the assistant would answer "no tengo esa información" before any poisoning. Legitimate KB hygiene, not prompt tuning.

**Use it for:**
- Demo runs
- Baseline measurements
- Quick tests

## Generated Bulk Filler

Located in `corpus/legit/`.

Generate realistic but bulk filler for scale testing: how does poison RSR degrade as the corpus grows?

### Generate Filler

```bash
# Generate up to 50 fresh documents (missing combinations only)
python attacks/generate_corpus.py --count 50 --output corpus/legit

# Grow corpus to a total of 200 documents (fills only missing combinations)
python attacks/generate_corpus.py --scale 200

# Use a different model
python attacks/generate_corpus.py --count 50 --model llama2:13b
```

**Time:** ~5 minutes for 50 docs with Ollama.

**Output:** `corpus/legit/*.md`: Unique combinations of (topic, document type).

### Topics and Types

There are 11 document types and 20 topics, so the corpus tops out at **220 unique documents**. The script is combination-aware: it only generates missing combinations and never regenerates existing ones.

**Document types:**
- FAQ
- Guide
- Troubleshooting
- Checklist
- Recipe
- Blog post
- Tutorial
- Policy
- Newsletter
- Reference
- Case study

**Topics:**
- Meal planning
- Recipes (regional, dietary, etc.)
- Shopping lists
- Subscriptions
- Account management
- Billing
- Customer support
- Food safety
- Allergen information
- Mobile app tips
- Regional cuisine
- Meal prep
- Nutrition
- Pantry organization
- Cooking techniques
- And more

### Seed with Bulk

```bash
# Generate bulk
python attacks/generate_corpus.py --scale 200

# Seed core + bulk + poison
python scripts/seed_db.py --with-poison --with-bulk
```

## Baseline Measurement

```bash
# Measure RSR + GCR at corpus sizes 50 and 200
python scripts/measure_baseline.py

# Custom sizes
python scripts/measure_baseline.py --sizes 50 100 200

# With JSON output
python scripts/measure_baseline.py --json-out reports/baseline.json

# In-memory ChromaDB (no Docker needed)
python scripts/measure_baseline.py --in-memory

# RSR only (no Ollama needed)
python scripts/measure_baseline.py --no-generation
```

**Expected pattern:**
- RSR drops as corpus grows (single poison competes with more docs)
- Conditional GCR stays high (model still complies when poison reaches it)
- This drop is why Tier 3 (GASLITE) matters: it's optimized to stay retrievable at scale

## Corpus Structure

```
corpus/
├── core/                          # CURATED committed
│   ├── account_faq.md
│   ├── refund_policy.md
│   ├── meal_planning_guide.md
│   └── ...
├── legit/                         # GENERATED bulk (git-ignored)
│   ├── recipe_regional_5.md
│   ├── faq_billing_3.md
│   └── ...
├── internal/                      # CONFIDENTIAL (role=internal only)
│   └── admin_procedures.md
└── poisoned/                      # POISONED docs (tiers 1-2 + precomputed tier 3)
    ├── poison_t1_refunds.md
    ├── poison_t2_stealth_html_comment.md
    └── poison_t3_gaslite_pwd_reset.md
```

## Reproducibility

Generation is **non-deterministic** (Ollama calls are non-deterministic). Each run produces different content.

**For reproducible measurements:**
- Commit the generated corpus snapshot to a branch
- Or use `--in-memory` and re-run with fresh data each time

## Configuration

See `.env.example` for chunking and storage settings:

```bash
CHUNK_SIZE=512          # Characters per chunk
CHUNK_OVERLAP=64        # Character overlap between chunks
TOP_K=6                 # Chunks to retrieve
```

Smaller chunks: more granular retrieval, more chunks per doc.
Larger chunks: fewer chunks, risk of unrelated content in one chunk.

## Cleanup

```bash
# Remove all generated bulk (keeps core)
rm -rf corpus/legit/

# Reseed with clean baseline
python scripts/seed_db.py
```

## Tips

- **For testing:** Use core only (fast, deterministic)
- **For scale experiments:** Generate bulk and measure at multiple sizes
- **For deployment:** Use curated core + your own knowledge base
- **For CI:** Pre-generate at a fixed size and commit, or use ephemeral in-memory

## Next

- **Run a baseline:** [Quick Start](QUICKSTART.md)
- **See attack impact at scale:** [Testing Methodology](TESTING.md#measuring-the-baseline)
- **Understand retrieval:** [Architecture](ARCHITECTURE.md)
