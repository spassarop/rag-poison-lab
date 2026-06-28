#! /bin/sh
# GASLITE "Knows What" (concept) attack — FLUENT variant (RAG-poisoning lab, budget=1).
#
# Same as attack_cocina_knows-what.sh but with a fluency constraint
# (constraints=as-suffix-tox-and-flu): the trigger is penalized for low fluency
# (flu_alpha>0), producing more human-readable text. Use it:
#   - for a believable poisoned passage on a slide, and
#   - to test a perplexity / fluency-control INGESTION DEFENSE (paper §7): the
#     toxic-simple variant is caught by such a filter; this one is built to evade it.
#
# FLUENCY MODEL = `xlmr_mlm` (xlm-roberta-base), set via the override below.
# WHY: gaslite.py asserts the fluency model's tokenizer CLASS matches the retriever's.
# The retriever (paraphrase-multilingual-MiniLM-L12-v2) uses the XLM-R tokenizer, so the
# stock scorers ('gpt2' = nanoGPT/e5 English BERT, 'bert_mlm' = DistilBERT English) make
# it CRASH ("tokenizer must match") and their vocab wouldn't align anyway. We added
# `MultilingualMLMFluencyScorer` (src/attacks/fluency_scorer.py) on xlm-roberta-base:
# same XLM-R tokenizer/vocab as the retriever AND multilingual → fluent SPANISH.
#
# Prereqs:
#   - xlm-roberta-base downloads on first run (~1.1 GB). (nanoGPT submodule NOT needed.)
#   - Fluency optimization is SLOWER (extra MLM forward per trigger token). Prefer GPU/Colab.

MODEL=sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
SIM_FUNC=cos_sim
BATCH_SIZE=2048

python hydra_entrypoint.py --config-name default \
  "model.model_hf_name=${MODEL}" model.sim_func_name=${SIM_FUNC} \
  dataset=cocina \
  core_objective=covering \
  cover_alg=concept-cocina cover_alg.n_clusters=1 \
  core_objective.cluster_idx=0 \
  constraints=as-suffix-tox-and-flu constraints.fluency_model_name=xlmr_mlm \
  batch_size=${BATCH_SIZE} random_seed=0 \
  log_to_wandb=False skip_if_cached=False \
  exp_tag=cocina_knows-what-fluent "$@"

# Run:            bash scripts/attack_cocina_knows-what-fluent.sh
# CPU (safe):     GASLITE_DEVICE=cpu bash scripts/attack_cocina_knows-what-fluent.sh
# Smoke (1 iter): bash scripts/attack_cocina_knows-what-fluent.sh attack.attack_n_iter=1
#
# Output: results/results__*cocina_knows-what-fluent*.json
# Compare vs the toxic-simple run (same concept/budget): fluency/visibility trade-off
# and defense evasion. The trigger may still mix languages (no hard language constraint),
# but xlm-roberta scores Spanish fluency, so it reads far more naturally than the toxic one.
