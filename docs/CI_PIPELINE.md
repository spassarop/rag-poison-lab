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
- Requires the full system under test plus Ollama
- Generates JSON for dashboard consumption, not a pass/fail
- Red by design (current state without defenses)

**Run locally to track posture:**
```bash
python scripts/security_report.py        # Current state (off defenses)
DEFENSE_INGESTION=signatures python scripts/security_report.py  # With defense
```

### Corpus Signature Scan (Informational)

Prints which poisons the signature layer catches vs misses. Informational only, since the whole point is that fluent/GASLITE slip past static scanning.

## Adding the Dynamic Gates (needs a live environment)

The live harness is out of the default CI because it needs a running, seeded API plus Ollama, which vanilla runners do not have. That does not mean it cannot be a reliable gate. It can, once you have an environment, and the trick is to run it against your defended system.

Run the harness with your defenses turned on. In that configuration the canary tests (L1 and L2) are deterministic and safe to block on. A green run means the defenses held, and a red run is a real regression that let a poison reach the user. The semantic judge (L3) is not deterministic, so keep it non-blocking, and treat the L4 posture report as an artifact you track over time rather than a pass/fail.

A ready-to-copy template lives at `.github/dynamic-gates.example.yml`. It sits outside `.github/workflows/` on purpose, so Actions does not run it. Copy it into `.github/workflows/`, point it at your Chroma and Ollama, and pick a runner (a self-hosted runner with Ollama and its models is the realistic option). The template seeds with poison, brings up the API with the defense flags on, runs `pytest -m "l1 or l2"` as the blocking gate, runs `pytest -m l3` as non-blocking, and uploads the posture report.

## What CI Regenerates

**Poisoned corpus:** The contract in `attacks/corpus_attacks.yaml` is deterministic. `generate_poisoned_corpus.py` runs in the job and regenerates all poison docs from it. No randomness.

## Workflow Structure

The real workflow is `.github/workflows/ci.yml`. It runs on every push and pull request and has two jobs:

- `deterministic-tests` (blocking): installs dependencies, regenerates the poisoned corpus from the contract, and runs `pytest tests/test_defenses.py tests/test_metrics.py`.
- `corpus-scan` (non-blocking, `continue-on-error: true`): runs the signature scanner over `corpus/poisoned/` and prints what it catches versus what it misses. It is informational, because fluent and GASLITE poisons are expected to slip past static signatures.

Read the file for the exact steps and action versions.

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

- **Testing framework:** [Testing Methodology](TESTING.md)
- **Adding attack cases:** [CONTRIBUTING.md](../CONTRIBUTING.md)
- **Dynamic gates template:** `.github/dynamic-gates.example.yml`
