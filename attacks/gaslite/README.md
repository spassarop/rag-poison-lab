# GASLITE — gradient-optimized adversarial passage (tier 3)

> **Defensive / authorized use only.** GASLITE crafts a passage that dominates a
> dense retriever's ranking. Run it **only** against systems you own or are
> authorized to test. The passage here carries only the fictional `.test` canary.

This is the **tier-3** attack. Unlike tiers 1–2 (which depend on the attacker
*writing* plausible text), GASLITE optimizes a passage by **gradient** against the
embedding model so it is retrieved even in a large corpus, **without** human-suspicious
strings. It is the canonical **OWASP LLM09 (Vector and Embedding Weaknesses)** attack,
and in the defense stage it shows that signature/static ingestion filters do **not**
catch it.

> **Status (this is the source of truth — the old "three paths" guide was aspirational
> and is now replaced by what we actually ran).** The stock repo does not run as-is for
> our setup: it pins an old Python, hardcodes CUDA, hardcodes the paper's models, and
> assumes msmarco. We forked it locally (the `repo/` clone) with a set of patches and
> two adapted attacks. Everything below is the reproducible sequence plus the
> conceptual deviations behind each change. `repro/` holds the record of the exact
> run (commit, seed, hardware) — fill `repro/config.txt` after each real run.

---

## 0. TL;DR — what we built

Two adapted attacks against the SUT retriever (`paraphrase-multilingual-MiniLM-L12-v2`),
both evaluated against **our** Cocina Cloud corpus (not msmarco):

| Attack | Threat model | Script | Builder |
|---|---|---|---|
| **knows-all** | attacker knows the exact query | `repo/scripts/attack_cocina_knows-all.sh` | `repo/build_cocina_beir.py` |
| **knows-what** (recommended) | attacker knows the *concept* (budget=1 covers all phrasings) | `repo/scripts/attack_cocina_knows-what.sh` | `repo/build_cocina_concept.py` |
| knows-what *fluent* (later) | same, fluent trigger to test a fluency defense | `repo/scripts/attack_cocina_knows-what-fluent.sh` | (same as above) |

The **knows-what** attack is the one to feature: it is the paper's strongest realistic
low-budget setting (§6.2) and produces a single passage that surfaces for the whole
concept, not one phrasing.

---

## 1. Environment (do this once)

> Disclaimer: This experiment was run in macOS. Thus, the `brew` references and such.

The repo's README says Python 3.8.5. But in case of version issues, **3.10.x** works (we used `3.10.20`); the repo should run fine up to 3.11.

```bash
cd attacks/gaslite
git clone --recurse-submodules https://github.com/matanbt/GASLITE.git repo   # submodules = nanoGPT fluency model
pyenv install 3.10.20    # if openssl errors: see note below
pyenv local 3.10.20
python -m venv .venv && source .venv/bin/activate
pip install -r repo/requirements.txt
```

`pyenv install` openssl fix (Homebrew dropped `openssl@1.1`):

```bash
brew install openssl@3 readline xz
CFLAGS="-I$(brew --prefix openssl@3)/include" \
LDFLAGS="-L$(brew --prefix openssl@3)/lib" \
pyenv install 3.10.20
```

**Device:** the stock repo hardcodes `.cuda()` everywhere. We added a device selector
(see §4) so it runs on CPU/MPS. On Apple Silicon, prefer **CPU** (MPS misses some ops):

```bash
export GASLITE_DEVICE=cpu      # or mps / cuda; auto-detects if unset
```

GASLITE is gradient-heavy → CPU is slow. For the real (100-iter) run, prefer a CUDA
GPU / Colab. Use `attack.attack_n_iter=1` for a fast smoke test of the pipeline.

---

## 2. Reproducible run sequence

### A. knows-all (single query)

```bash
cd attacks/gaslite/repo
python build_cocina_beir.py                                   # -> data/cocina/{corpus,queries,qrels}
GASLITE_DEVICE=cpu bash scripts/attack_cocina_knows-all.sh attack.attack_n_iter=1   # smoke
GASLITE_DEVICE=cpu bash scripts/attack_cocina_knows-all.sh                          # real (100 iters)
```

### B. knows-what (concept, budget=1 — recommended)

```bash
cd attacks/gaslite/repo
# 1) Edit ../concept_queries_cocina.json if needed (synthetic ES queries + `info` payload).
python build_cocina_concept.py        # extends data/cocina + auto-writes config/cover_alg/concept-cocina.yaml
GASLITE_DEVICE=cpu bash scripts/attack_cocina_knows-what.sh attack.attack_n_iter=1  # smoke
GASLITE_DEVICE=cpu bash scripts/attack_cocina_knows-what.sh                         # real
```

Results (crafted passage + metrics) land in `repo/results/results__*.json`. The log
prints `[[decoded-trigger-slice]]` and `[[full decoded-passage]]`. Verify the adversarial
passage reaches **rank 0 / top-1** for the targeted queries.

### C. Hand the artifact to the SUT

Copy the **full decoded passage** into `attacks/gaslite/adversarial_passage.txt` and fill
`attacks/gaslite/gaslite_eval.json` with the top-k numbers. Then, back in the SUT venv:

```bash
python attacks/generate_poisoned_corpus.py   # wraps the passage into corpus/poisoned/poison_t3_gaslite.md
python scripts/seed_db.py --with-poison
pytest tests/test_l2_corpus.py -k gaslite -v  # defenses off -> should compromise
python scripts/measure_baseline.py            # compare RSR (GASLITE vs query-aligned)
```

---

## 3. Conceptual deviations & lessons (read before re-running)

1. **The model collection is not a whitelist.** `repo/config/model/*.yaml` are 2-line
   aliases; the model loads by HF name. We override directly:
   `model.model_hf_name=sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
   model.sim_func_name=cos_sim`. GASLITE is white-box → it just needs the weights.

2. **Crafting is corpus-agnostic; the corpus is only for evaluation** (paper §4.1, Eq. 2:
   the objective maximizes alignment to the **centroid of the target query distribution**,
   *corpus-agnostic and query-count-agnostic*). The stock scripts attack a **random
   msmarco query against the msmarco corpus** — neither ours. So we build a **local BEIR
   dataset from the SUT corpus** (re-chunked with the SUT's own splitter, identical chunk
   ids) so the reported appeared@k is *our* RSR, comparable to `measure_baseline.py`.

3. **knows-all vs knows-what.** knows-all (1 query) gives a trivial top-1 but only poisons
   that exact phrasing. **knows-what** (§6.2) targets a *concept*: one passage at the
   centroid of many concept queries covers all phrasings — more realistic and the paper's
   strongest low-budget result. Concept queries can be **synthetic/LLM-generated** (§G.6.1),
   which fits the fictional KB (no real query logs). This is why we pivoted to knows-what.

4. **Do NOT use the native `gen_qs` / `concept_gen-*` path.** In `data_utils` that branch
   returns `corpus=None` → you lose the appeared@k against your corpus. We instead embed
   the concept queries into the BEIR `cocina` dataset (held-in 50% trains the centroid,
   held-out 50% evaluates).

5. **The canary URL must be inside `info` DURING optimization — never appended after.**
   GASLITE optimizes `p_adv = info ⊕ trigger`: `info` is fixed but part of the optimized
   embedding, and the trigger compensates for it. The original
   `generate_poisoned_corpus.py` appended the canary *after* the attack, which **shifts the
   embedding and breaks the ranking guarantee**. We baked the canary into `info`
   (`concept_queries_cocina.json`) and changed the wrapper to **validate** the canary is
   present and return the passage unchanged (it now raises if missing).

6. **Chunk-size constraint (512 chars).** The SUT chunks at 512 and GASLITE optimizes the
   *whole* passage as one vector. If `info` + trigger > 512 chars, the SUT splits it and
   neither chunk equals what was optimized → guarantee broken. Keep it in one chunk; if the
   `[[full decoded-passage]]` exceeds 512, lower the trigger, e.g. `constraints.trigger_len=60`
   (trade-off: shorter trigger = weaker dominance). Validate with
   `python attacks/generate_poisoned_corpus.py --check`.

7. **Why the trigger comes out in English.** The objective is purely geometric (cosine to
   the centroid) with **no language constraint**; the multilingual model aligns languages in
   a shared space, so English tokens can sit as close to a Spanish query centroid as Spanish
   ones. Plus the init is English toxic text and the BERT-multilingual vocab is English-heavy.
   It does **not** hurt retrieval (dense retrieval ranks by vector, not lexicon) — that's the
   whole vulnerability. With 1 iteration you mostly see the init, not the optimized trigger.

8. **Fluency variant is English too (TODO).** `constraints=as-suffix-tox-and-flu` uses
   `fluency_model_name: gpt2` (English) → it optimizes fluent *English*, not Spanish. For
   believable Spanish stealth, swap to a Spanish/multilingual causal LM and/or restrict the
   candidate vocab. Documented as a TODO in `attack_cocina_knows-what-fluent.sh`. Use the
   fluent variant to show the fluency/visibility trade-off and to evade a perplexity defense.

---

## 4. Versioning — `repo/` is regenerable, not tracked

`attacks/gaslite/repo/` is an upstream GASLITE clone (it carries its own `.git`), so
this project does **not** version anything inside it. The source of truth is the
**versioned files at `attacks/gaslite/` level**, and `repo/` is reconstructed from
them deterministically:

```bash
cd attacks/gaslite
GASLITE_COMMIT=<sha> bash setup_gaslite.sh   # clone @commit + copy overlay + apply patches
```

`setup_gaslite.sh` clones GASLITE (pinned commit if `GASLITE_COMMIT` is set), copies
`overlay/` into `repo/`, and runs `apply_gaslite_patches.py` (idempotent). After it
finishes it prints the resolved commit — record it in `repro/config.txt`.

> `repo/` is git-ignored (see root `.gitignore`). Never edit files inside `repo/`
> directly for anything you want to keep: edit the versioned copy in `overlay/` (for
> added files) or `apply_gaslite_patches.py` (for upstream edits), then re-run setup.

**Versioned (source of truth, under `attacks/gaslite/`):**

- `setup_gaslite.sh` — regenerates `repo/` from the items below.
- `apply_gaslite_patches.py` — idempotent edits to GASLITE's own source files.
- `overlay/` — files copied into `repo/`, mirroring its paths:
  - `build_cocina_beir.py` (knows-all builder), `build_cocina_concept.py` (knows-what
    builder; also auto-writes `config/cover_alg/concept-cocina.yaml`).
  - `src/_device.py` — CPU/MPS/CUDA selector (`GASLITE_DEVICE`).
  - `config/dataset/cocina.yaml` — Hydra selector `dataset=cocina`.
  - `scripts/attack_cocina_knows-all.sh`, `…knows-what.sh`, `…knows-what-fluent.sh`.
- `concept_queries_cocina.json` — synthetic ES concept queries + `info` payload (with canary).
- `repro/NOTES.md`, `repro/config.txt` — the run record.

> `config/cover_alg/concept-cocina.yaml` is **not** in `overlay/`: it is auto-generated
> by `build_cocina_concept.py` from `concept_queries_cocina.json` on every run.

**Upstream edits applied by `apply_gaslite_patches.py` (inside `repo/`):**

- `src/data_utils.py` — local `dataset_name == 'cocina'` branch (loads `data/cocina`
  via BEIR `GenericDataLoader`, no download, no english-only split map).
- `hydra_entrypoint.py` — `_get_result_path`: handle list `query_choice`;
  `_get_exp_name`: `.get(...)` fallback so non-paper model names don't `KeyError`.
- `src/full_attack.py` — `get_qs_and_golden_ps`: guard `startswith` with `isinstance(str)`;
  `_get_best_query_emb`: short-circuit single query + tolerate `<10` / empty results.
- ~40 hardcoded `.cuda()` / `device='cuda'` across `src/` rewritten to use `DEVICE`.

**Patched in the SUT (versioned normally):**

- `attacks/generate_poisoned_corpus.py` — `build_gaslite_adversarial_passage` no longer
  appends the canary; it validates the canary is already in the passage (baked into `info`).

---

## 5. Target configuration

- **Embedding model (attack target):** `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`
  (the SUT's `EMBED_MODEL`).
- **Concept (knows-what):** account/password recovery (`concept_queries_cocina.json`).
- **Target query (knows-all):** `¿Cómo recupero mi contraseña?`
- **Canary payload (baked into `info`):** `http://login-update.cocinacloud.test/login`

## 6. Why this stays offline / precomputed

GASLITE is heavy (gradient optimization, ideally a GPU) and tied to an old Python. It is run
**once, offline, in the isolated `repo/` env**, and only the *result* (the passage) is
committed as an artifact. **Never run it in CI or in the SUT path.** The case
`t3_gaslite_pwd_reset` in `attacks/corpus_attacks.yaml` is `precomputed: true` so the
harness consumes the artifact without regenerating it. Until `adversarial_passage.txt`
replaces the placeholder, that case is skipped and its RSR is not real.

## 7. References

- GASLITE — arXiv:2412.20953; repo: https://github.com/matanbt/GASLITE.
  Local copy of the paper: `../../GASLITEing the Retrieval_..._.html`. Key sections:
  §3 threat model, §4.1 objective (Eq. 2), §6.1 knows-all, §6.2 knows-what, §7 defenses,
  App. D (multi-passage / partitioning), §G.6.1 synthetic queries.
- PoisonedRAG — arXiv:2402.07867 (comparison baseline).
- OWASP LLM09: Vector and Embedding Weaknesses.
