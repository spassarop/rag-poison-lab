# Reproduction artifacts

Save here the **exact** configuration you used to craft the passage (so the result is
reproducible) — not the whole GASLITE repo. Suggested contents:

- The Hydra config / CLI overrides used (target model, target query, attack variant,
  number of optimization steps, batch size, seed).
- The attack variant script name (e.g. `attack0_know-all.sh`) and its commit hash of
  the GASLITE repo.
- Any deviation from the defaults.

Example (`repro/config.txt`):

```
repo_commit: <git rev-parse HEAD of the GASLITE clone>
attack: attack0 (knows-all, single query)
model.sentence_transformer: sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
attack.target_query: "¿Cómo recupero mi contraseña?"
steps: <N>
seed: <N>
hardware: <GPU>
```
