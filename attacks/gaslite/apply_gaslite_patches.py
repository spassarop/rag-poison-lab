"""Apply the lab's edits to a fresh GASLITE clone — idempotent.

The added files (builders, _device.py, configs, scripts) are copied by
setup_gaslite.sh from `overlay/`. THIS script applies the in-place edits to
GASLITE's own source files (which we can't just overwrite without losing upstream
context). Every edit is guarded so re-running is safe.

Edits (see ../README.md §3 for the rationale):
  1. src/_device.py-based device selection: rewrite ~40 hardcoded `.cuda()` /
     `device='cuda'` to use DEVICE (CPU/MPS/CUDA).
  2. src/data_utils.py: add a local `dataset_name == 'cocina'` branch (no download).
  3. hydra_entrypoint.py: handle list `query_choice`; `.get(...)` fallback for
     non-paper model names.
  4. src/full_attack.py: guard `startswith` for list `query_choice`; make
     `_get_best_query_emb` single-query-safe and tolerant of <10/empty results.

Run from the repo dir:  python apply_gaslite_patches.py   (or via setup_gaslite.sh)
"""
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent / "repo"
if not REPO.exists():
    # When copied into repo/ by setup, REPO is the cwd's parent layout; fall back.
    REPO = Path.cwd()


def edit(relpath, transform, label):
    p = REPO / relpath
    if not p.exists():
        print(f"  [SKIP] {relpath} not found")
        return
    s = p.read_text(encoding="utf-8")
    new = transform(s)
    if new == s:
        print(f"  [ok]   {relpath}: {label} (already applied / no change)")
    else:
        p.write_text(new, encoding="utf-8")
        print(f"  [EDIT] {relpath}: {label}")


# --- 1. CUDA -> DEVICE sweep ------------------------------------------------
CUDA_FILES = [
    "src/models/retriever.py", "src/full_attack.py", "src/covering/covering.py",
    "src/attacks/rephraser.py", "src/attacks/gaslite.py",
    "src/attacks/fluency_scorer.py", "src/attacks/utils.py",
]
IMPORT = "from src._device import DEVICE  # patched: CPU/MPS/CUDA device selection\n"


def sweep_cuda(s):
    s = s.replace(".cuda()", ".to(DEVICE)")
    s = s.replace(".to('cuda')", ".to(DEVICE)").replace('.to("cuda")', ".to(DEVICE)")
    s = s.replace("device='cuda'", "device=DEVICE").replace('device="cuda"', "device=DEVICE")
    s = s.replace("device: str = 'cuda'", "device=DEVICE").replace('device: str = "cuda"', "device=DEVICE")
    s = s.replace("map_location='cuda'", "map_location=DEVICE").replace('map_location="cuda"', "map_location=DEVICE")
    if "from src._device import DEVICE" not in s:
        s = IMPORT + s
    return s


# --- 2. data_utils.py: local 'cocina' branch --------------------------------
COCINA_BRANCH = '''    if dataset_name == 'cocina':
        # --- Local custom BEIR dataset for the RAG-poisoning lab (Cocina Cloud). ---
        # Built by build_cocina_beir.py / build_cocina_concept.py; lives under data/cocina/.
        data_path = os.path.join(os.getcwd(), "data", "cocina")
        corpus, queries, qrels = GenericDataLoader(data_folder=data_path).load(split="test")
        corpus = {pid: {'text': (content.get('title', '') + ' ' + content['text']).strip()}
                  for pid, content in corpus.items()}
        if filter_in_qids:
            queries = {qid: q for qid, q in queries.items() if qid in filter_in_qids}
            qrels = {qid: r for qid, r in qrels.items() if qid in queries}
        logger.info(f"Loaded LOCAL data: dataset_name='cocina', {len(corpus)=}, "
                    f"{len(queries)=}, {len(qrels)=}")
        qp_pairs_dataset = _build_hf_dataset(corpus, queries, qrels)
        return corpus, queries, qrels, qp_pairs_dataset

    if dataset_name == 'msmarco' and data_split == 'gen_qs':'''


def patch_data_utils(s):
    if "dataset_name == 'cocina'" in s:
        return s
    anchor = "    if dataset_name == 'msmarco' and data_split == 'gen_qs':"
    return s.replace(anchor, COCINA_BRANCH, 1)


# --- 3. hydra_entrypoint.py -------------------------------------------------
def patch_hydra(s):
    # 3a. list-safe query_choice in result path
    old_qc = "    query_choice = cfg['query_choice'].split('/')[-1]"
    new_qc = ("    qc = cfg['query_choice']\n"
              "    if isinstance(qc, (list, tuple)):  # e.g. query_choice=[q1] (explicit query-ids)\n"
              "        query_choice = \"-\".join(map(str, qc))\n"
              "    else:\n"
              "        query_choice = str(qc).split('/')[-1]")
    if old_qc in s:
        s = s.replace(old_qc, new_qc, 1)
    # 3b. model_code dict -> .get fallback
    old_m = "    }[cfg['model_hf_name']]"
    new_m = "    }.get(cfg['model_hf_name'], cfg['model_hf_name'].split('/')[-1])  # fallback: short model name"
    if old_m in s:
        s = s.replace(old_m, new_m, 1)
    return s


# --- 4. full_attack.py ------------------------------------------------------
def patch_full_attack(s):
    # 4a. guard startswith for list query_choice
    old_sw = "    elif query_choice.startswith('from_file__') and '3rd_party' in query_choice:"
    new_sw = "    elif isinstance(query_choice, str) and query_choice.startswith('from_file__') and '3rd_party' in query_choice:"
    if old_sw in s:
        s = s.replace(old_sw, new_sw, 1)
    # 4b. _get_best_query_emb: single-query + tolerant
    old_b = ("    attacked_q_embs = torch.stack([qid_to_emb[q] for q in attacked_qids])\n"
             "    sim_matrix = torch.matmul(attacked_q_embs, attacked_q_embs.T)\n"
             "    top_10_score_per_q = []\n"
             "    for q_cand in attacked_qids:\n"
             "        top_10_score_per_q.append(list(results[q_cand].items())[9][-1])")
    new_b = ("    # Single-query attack: \"best query in the cluster\" is trivially that one query.\n"
             "    if len(attacked_qids) == 1:\n"
             "        return qid_to_emb[attacked_qids[0]]\n"
             "    attacked_q_embs = torch.stack([qid_to_emb[q] for q in attacked_qids])\n"
             "    sim_matrix = torch.matmul(attacked_q_embs, attacked_q_embs.T)\n"
             "    top_10_score_per_q = []\n"
             "    for q_cand in attacked_qids:\n"
             "        items = list(results.get(q_cand, {}).items())\n"
             "        if not items:  # no clean results retrieved for this query\n"
             "            top_10_score_per_q.append(float('-inf'))\n"
             "            continue\n"
             "        idx = min(9, len(items) - 1)  # tiny corpora may return <10 results\n"
             "        top_10_score_per_q.append(items[idx][-1])")
    if old_b in s:
        s = s.replace(old_b, new_b, 1)
    return s


# --- 5. fluency_scorer.py: multilingual MLM scorer (xlm-roberta) ------------
_XLMR_CLASS = '''class MultilingualMLMFluencyScorer(BertMLMFluencyScorer):
    """MLM fluency scorer on an arbitrary HF masked-LM, loaded generically so its
    tokenizer/vocab can MATCH a non-English retriever. Defaults to xlm-roberta-base,
    whose XLM-R tokenizer matches `paraphrase-multilingual-MiniLM-L12-v2` (the SUT
    retriever) — so the tokenizer-class check passes, the trigger token-ids index the
    right embedding table, and fluency is scored MULTILINGUALLY (incl. Spanish).
    Reuses all scoring logic from BertMLMFluencyScorer; only the model load differs.
    """
    def __init__(self, batch_size: int = 128, model_name: str = "xlm-roberta-base",
                 target_num_embeddings: int = None, **kwargs):
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForMaskedLM.from_pretrained(model_name)
        # The retriever's embedding matrix may be padded beyond the tokenizer vocab
        # (e.g. paraphrase-multilingual-MiniLM-L12-v2 has 250037 rows vs xlm-r's 250002).
        # The trigger one-hot is built over the retriever's embedding width, so resize to
        # match — extra rows map to never-emitted padding ids, so they don't affect scoring.
        if target_num_embeddings and target_num_embeddings != self.model.get_input_embeddings().num_embeddings:
            self.model.resize_token_embeddings(target_num_embeddings)
        self.model = self.model.to(DEVICE)
        self.input_embedding = self.model.get_input_embeddings()  # AFTER resize; generic, model-agnostic
        self.batch_size = batch_size
        self.model.eval()
        for param in self.model.parameters():
            param.requires_grad = False


class GPT2FluencyScorer:'''


def patch_fluency(s):
    if "MultilingualMLMFluencyScorer" in s:
        return s
    # 5a. import AutoModelForMaskedLM
    s = s.replace(
        "from transformers import DistilBertTokenizer, DistilBertForMaskedLM, AutoTokenizer, AutoModelForCausalLM",
        "from transformers import DistilBertTokenizer, DistilBertForMaskedLM, AutoTokenizer, AutoModelForCausalLM, AutoModelForMaskedLM",
        1)
    # 5b. insert the class before GPT2FluencyScorer
    s = s.replace("class GPT2FluencyScorer:", _XLMR_CLASS, 1)
    # 5c. register in initialize_fluency_model
    s = s.replace(
        "    elif fluency_model_name == 'bert_mlm':\n        return BertMLMFluencyScorer(**kwargs)",
        "    elif fluency_model_name == 'bert_mlm':\n        return BertMLMFluencyScorer(**kwargs)\n"
        "    elif fluency_model_name == 'xlmr_mlm':\n"
        "        # Multilingual MLM (xlm-roberta-base) — matches the XLM-R tokenizer of\n"
        "        # paraphrase-multilingual-MiniLM-L12-v2. See MultilingualMLMFluencyScorer.\n"
        "        return MultilingualMLMFluencyScorer(**kwargs)",
        1)
    return s


# --- 6. gaslite.py: relax fluency tokenizer check (class -> vocab) ----------
def patch_gaslite_check(s):
    # 6c. ensure `import os` (used by the fluency-batch env override below)
    if "\nimport os\n" not in s:
        s = s.replace("import math\nimport random", "import math\nimport os\nimport random", 1)
    # 6b. pass the retriever's embedding width to the fluency scorer (resize alignment)
    #     + use a small fluency batch by default (xlm-r 250k-vocab logits OOM the CPU).
    call_old = "    flu_model = initialize_fluency_model(fluency_model_name, batch_size=128)  # TODO generalize"
    call_new = ('    flu_model = initialize_fluency_model(\n'
                '        fluency_model_name, batch_size=int(os.environ.get("GASLITE_FLU_BATCH", "16")),\n'
                '        target_num_embeddings=model.get_input_embeddings().num_embeddings)  # patched: align width + small flu batch (CPU OOM)')
    if call_old in s:
        s = s.replace(call_old, call_new, 1)
    # 6a. relax tokenizer check (class -> vocab)
    old = ("            and model.tokenizer.__class__ != flu_model.tokenizer.__class__  # and we have tokenizer mismatch\n"
           "    ):\n"
           '        raise ValueError("Fluency model\'s tokenizer and the model\'s tokenizer must match.")')
    new = ("            and model.tokenizer.get_vocab() != flu_model.tokenizer.get_vocab()  # VOCAB mismatch (not just class)\n"
           "    ):\n"
           "        # The real requirement is that token id -> token string agrees between the two\n"
           "        # tokenizers (trigger ids from the retriever index the fluency model's embedding).\n"
           "        # Comparing classes is too strict (fast/slow or wrapper differences); compare vocab.\n"
           "        raise ValueError(\n"
           '            "Fluency model\'s tokenizer and the model\'s tokenizer must match (vocab differs). "\n'
           '            f"retriever={model.tokenizer.__class__.__name__}(vocab={model.tokenizer.vocab_size}) "\n'
           '            f"fluency={flu_model.tokenizer.__class__.__name__}(vocab={flu_model.tokenizer.vocab_size})."\n'
           "        )")
    if "get_vocab() != flu_model" in s:
        return s
    return s.replace(old, new, 1)


def main():
    print(f"Applying GASLITE lab patches under: {REPO}")
    for f in CUDA_FILES:
        edit(f, sweep_cuda, "cuda->DEVICE sweep")
    edit("src/data_utils.py", patch_data_utils, "local 'cocina' dataset branch")
    edit("hydra_entrypoint.py", patch_hydra, "list query_choice + model fallback")
    edit("src/full_attack.py", patch_full_attack, "query_choice/list + _get_best_query_emb guards")
    edit("src/attacks/fluency_scorer.py", patch_fluency, "multilingual (xlm-roberta) MLM fluency scorer")
    edit("src/attacks/gaslite.py", patch_gaslite_check, "relax fluency tokenizer check (class -> vocab)")
    # sanity: every cuda file must end up importing DEVICE
    bad = [f for f in CUDA_FILES if "from src._device import DEVICE" not in (REPO / f).read_text(encoding="utf-8")]
    if bad:
        print(f"  [WARN] missing DEVICE import in: {bad}", file=sys.stderr)
    print("Done.")


if __name__ == "__main__":
    main()
