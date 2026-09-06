# CI Pipeline

How GitHub Actions gates the project and what CI deliberately does NOT gate.

## Overview

CI runs on every push and pull request. It consists of **blocking gates** (deterministic) and **non-blocking scans** (informational).

**File:** `.github/workflows/ci.yml`

## What CI Gates (Blocking)

These must pass for the PR to merge.

### Deterministic Unit Tests

```bash
pytest tests/test_defenses.py tests/test_metrics.py -v
```

**What it tests:**
- Defense logic: which layer catches what (signatures vs fluent+GASLITE, anomaly flags only GASLITE, output guard stops canary, role filter blocks customer)
- Metric math: RSR/GCR calculations are correct

**Why it's deterministic:**
- No system under test required
- No API running
- No Ollama needed
- Poisoned corpus is regenerated from the contract (no randomness)
- Benign reference for anomaly tests comes from committed fixture (`tests/fixtures/legit/`)

**Run locally:**
```bash
pytest tests/test_defenses.py tests/test_metrics.py -v
```

## What CI Does NOT Gate (Non-Blocking)

These run but don't fail the PR. They're informational.

### Live Black-Box Harness (L1/L2/L3)

```bash
pytest tests/test_l1_canary.py tests/test_l2_corpus.py -v  # L1/L2 (deterministic)
pytest -m l3 -v                                             # L3 (non-blocking)
```

**Why it's not blocked:**
- Requires seeded, poisoned API + Ollama
- Requires running services
- Is red by design (demonstrates the attack)

**Run locally when you need to:**
```bash
python scripts/seed_db.py --with-poison
uvicorn app.main:app &
pytest tests/test_l1_canary.py tests/test_l2_corpus.py -v
pytest -m l3 -v
```

### L4 Posture Report

```bash
python scripts/security_report.py
```

**Why it's not blocked:**
- Requires full sUT + Ollama
- Generates JSON for dashboard consumption, not a pass/fail
- Red by design (current state without defenses)

**Run locally to track posture:**
```bash
python scripts/security_report.py        # Current state (off defenses)
DEFENSE_INGESTION=signatures python scripts/security_report.py  # With defense
```

### Corpus Signature Scan (Informational)

Prints which poisons the signature layer catches vs misses. Informational only, since the whole point is that fluent/GASLITE slip past static scanning.

## What CI Regenerates

**Poisoned corpus:** The contract in `attacks/corpus_attacks.yaml` is deterministic. `generate_poisoned_corpus.py` runs in the job and regenerates all poison docs from it. No randomness.

## Workflow Structure

```yaml
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Setup Python
        uses: actions/setup-python@v4
      - name: Install deps
        run: pip install -r requirements.txt -r requirements-dev.txt
      - name: Generate poisoned corpus
        run: python attacks/generate_poisoned_corpus.py
      - name: Unit tests (BLOCKING)
        run: pytest tests/test_defenses.py tests/test_metrics.py -v
      - name: Corpus signature scan (INFO)
        run: python scripts/corpus_scan.py
      - name: Upload reports
        if: always()
        uses: actions/upload-artifact@v3
```

## Local Equivalents

**Run the full blocking gate locally:**
```bash
pytest tests/test_defenses.py tests/test_metrics.py -v
```

**Run everything locally (including non-blocking):**
```bash
# Generate poison
python attacks/generate_poisoned_corpus.py

# Seed and start API
python scripts/seed_db.py --with-poison
uvicorn app.main:app &

# Full harness (L1-L3)
pytest tests/ -v

# Posture report
python scripts/security_report.py

# HTML report
pytest tests/ --html=reports/report.html
```

## Typical PR Workflow

1. Make changes to `app/` or tests
2. Push to your branch
3. GitHub Actions runs the deterministic gate
4. Deterministic gate passes/fails immediately
5. Non-blocking jobs run in parallel (informational only)
6. You can merge if the deterministic gate passes

## Customizing CI

To modify what's tested or gated:

1. Edit `.github/workflows/ci.yml`
2. Update pytest markers if changing test categorization
3. Re-run locally to verify: `pytest --markers` shows all markers

**Current markers:**
- `l1`: L1 end-to-end tests
- `l2`: L2 per-case tests
- `l3`: L3 semantic evaluation (non-blocking)

## Performance

**Typical run time:**
- Deterministic gate: 30-60 seconds (no network, no LLM)
- Non-blocking corpus scan: 10-20 seconds
- Full run: ~1 minute

**Cost:**
- Free tier is plenty for this project
- No GPU needed in CI (only CPU for Python)
- GASLITE is precomputed offline, never regenerated in CI

## Debugging CI Failures

If the deterministic gate fails:

```bash
# Reproduce locally
pytest tests/test_defenses.py tests/test_metrics.py -v

# Check specific test
pytest tests/test_defenses.py::test_signature_scanner_catches_overt -v

# Verbose output
pytest tests/test_defenses.py -vv -s
```

Common issues:
- Metrics math off: check `tests/metrics.py`
- Defense logic broken: check `app/defenses/*.py`
- Test data stale: re-run `python attacks/generate_poisoned_corpus.py`

## Next Steps

- **Local development:** [DEVELOPMENT.md](../DEVELOPMENT.md)
- **Testing framework:** [Testing Methodology](TESTING.md)
- **Code style:** [DEVELOPMENT.md](../DEVELOPMENT.md)
