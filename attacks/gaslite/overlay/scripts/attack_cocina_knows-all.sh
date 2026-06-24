#! /bin/sh
# GASLITE single-query ("knows-all") attack adapted to the RAG-poisoning lab.
#
# Target model = the exact SUT retriever (multilingual MiniLM).
# Target query = the password-reset pretext (lives in data/cocina as qid 'q1').
# Eval pool / Pgold = the Cocina Cloud corpus (so the reported RSR is OURS,
#                      not msmarco's).
#
# Prereqs (run ONCE, from the repo dir, in the gaslite venv):
#   python build_cocina_beir.py        # writes data/cocina/{corpus,queries,qrels}
#   git submodule update --init        # nanoGPT fluency model (constraints=as-suffix-tox)
#
# Run from the repo root:  bash scripts/attack_cocina_knows-all.sh

MODEL=sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
SIM_FUNC=cos_sim
RANDOM_SEED=0
BATCH_SIZE=2048   # lower (e.g. 256) if you hit OOM; raise on a big GPU

python hydra_entrypoint.py --config-name default \
  "model.model_hf_name=${MODEL}" model.sim_func_name=${SIM_FUNC} \
  dataset=cocina \
  core_objective=single-query \
  'core_objective.query_choice=[q1]' \
  cover_alg=kmeans cover_alg.data_split=test cover_alg.n_clusters=1 cover_alg.data_portion=1.0 \
  batch_size=${BATCH_SIZE} "random_seed=${RANDOM_SEED}" \
  log_to_wandb=False skip_if_cached=False \
  exp_tag=cocina_knows-all

# Output: the crafted passage + metrics under repo/results/results__*cocina_knows-all*.json
# Then copy the passage text into ../adversarial_passage.txt and fill ../gaslite_eval.json.
