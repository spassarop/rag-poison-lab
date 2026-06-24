#! /bin/sh
# GASLITE "Knows What" (concept) attack — RAG-poisoning lab, budget = 1.
#
# Paper §6.2: one adversarial passage targets the CENTROID of a concept's query
# distribution, so it surfaces for ALL phrasings of the topic (not one query).
# Concept queries are synthetic (§G.6.1) — no real query logs needed.
#
# Prereqs (run ONCE, from the repo dir, in the gaslite venv):
#   python build_cocina_concept.py     # writes data/cocina/* + config/cover_alg/concept-cocina.yaml
#   git submodule update --init        # nanoGPT fluency model (constraints=as-suffix-tox)
#
# Run:            bash scripts/attack_cocina_knows-what.sh
# CPU (safe):     GASLITE_DEVICE=cpu bash scripts/attack_cocina_knows-what.sh
# Smoke (1 iter): bash scripts/attack_cocina_knows-what.sh attack.attack_n_iter=1
#
# Extra CLI args are forwarded to Hydra (e.g. the smoke override above).

# CHUNK-SIZE CAVEAT: the SUT chunks at 512 chars and GASLITE optimizes the WHOLE
# passage (info ⊕ trigger). The canary URL is now baked into `info` (~185 chars),
# so keep info+trigger <= 512 chars or the SUT will split it and the ranking chunk
# won't match what was optimized. If the decoded passage exceeds 512 chars, lower the
# trigger length, e.g. add:  constraints.trigger_len=60  (trade-off: weaker dominance).
# Validate the wrapped doc size afterward with: python ../../generate_poisoned_corpus.py --check
MODEL=sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
SIM_FUNC=cos_sim
BATCH_SIZE=2048   # lower (e.g. 256) on CPU/low memory

python hydra_entrypoint.py --config-name default \
  "model.model_hf_name=${MODEL}" model.sim_func_name=${SIM_FUNC} \
  dataset=cocina \
  core_objective=covering \
  cover_alg=concept-cocina cover_alg.n_clusters=1 \
  core_objective.cluster_idx=0 \
  constraints=as-suffix-tox \
  batch_size=${BATCH_SIZE} random_seed=0 \
  log_to_wandb=False skip_if_cached=False \
  exp_tag=cocina_knows-what "$@"

# Budget=1 -> a single passage covering the concept centroid.
# Output: results/results__*cocina_knows-what*.json (passage + appeared@k on held-out queries).
# Copy the crafted passage into ../adversarial_passage.txt; the canary URL is added
# by ../../generate_poisoned_corpus.py. The 'info' prefix is your Spanish lure
# (from concept_queries_cocina.json -> toxic_passage), NOT the paper's toxic text.
