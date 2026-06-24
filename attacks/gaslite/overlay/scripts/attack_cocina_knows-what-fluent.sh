#! /bin/sh
# GASLITE "Knows What" (concept) attack — FLUENT variant (RAG-poisoning lab, budget=1).
#
# Same as attack_cocina_knows-what.sh but with a fluency constraint
# (constraints=as-suffix-tox-and-flu): the trigger is penalized for low fluency
# (flu_alpha>0), producing more human-readable text. This is the variant to use:
#   - for a believable poisoned passage on a slide, and
#   - to test a perplexity / fluency-control INGESTION DEFENSE (paper §7): the
#     toxic-simple variant is caught by such a filter; this one is built to evade it.
#
# EXTRA prereqs vs the toxic variant:
#   - nanoGPT fluency submodule + weights:  git submodule update --init
#   - the fluency model (gpt2) downloads on first run.
# Fluency optimization is SLOWER; on CPU expect a long run. Prefer a GPU/Colab here.
#
# TODO (language mismatch): the fluency scorer is `fluency_model_name: gpt2`, an
# ENGLISH GPT-2. So this variant optimizes toward fluent ENGLISH, not Spanish — in a
# Spanish KB the trigger still looks off, and a Spanish perplexity/fluency DEFENSE
# would still flag it. To get believable fluent SPANISH:
#   1) set a Spanish/multilingual causal LM as the fluency model, e.g. add the Hydra
#      override:  constraints.fluency_model_name=DeepESP/gpt2-spanish
#      (or another es/multilingual CausalLM; verify src/attacks/fluency_scorer.py
#       loads it correctly — it may assume a GPT-2-style tokenizer/head).
#   2) optionally restrict the candidate token set to Spanish subwords (code change
#      in the trigger candidate generation) so the optimizer can't pick English/
#      Latin high-frequency tokens. Stock GASLITE has no language constraint.
# Until this is done, treat the "fluent" output as fluent-English, useful mainly to
# show the fluency/visibility trade-off vs the toxic variant, NOT as Spanish stealth.
#
# Run:            bash scripts/attack_cocina_knows-what-fluent.sh
# CPU (safe):     GASLITE_DEVICE=cpu bash scripts/attack_cocina_knows-what-fluent.sh
# Smoke (1 iter): bash scripts/attack_cocina_knows-what-fluent.sh attack.attack_n_iter=1

MODEL=sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
SIM_FUNC=cos_sim
BATCH_SIZE=2048

python hydra_entrypoint.py --config-name default \
  "model.model_hf_name=${MODEL}" model.sim_func_name=${SIM_FUNC} \
  dataset=cocina \
  core_objective=covering \
  cover_alg=concept-cocina cover_alg.n_clusters=1 \
  core_objective.cluster_idx=0 \
  constraints=as-suffix-tox-and-flu \
  batch_size=${BATCH_SIZE} random_seed=0 \
  log_to_wandb=False skip_if_cached=False \
  exp_tag=cocina_knows-what-fluent "$@"

# Output: results/results__*cocina_knows-what-fluent*.json
# Compare against the toxic-simple run (same concept/budget) to show the fluency/
# visibility trade-off and defense evasion.
