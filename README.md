# RAG Poisoning Lab

[![CI](https://github.com/spassarop/rag-poison-lab/actions/workflows/ci.yml/badge.svg)](https://github.com/spassarop/rag-poison-lab/actions/workflows/ci.yml)

Production-grade demonstration of **RAG poisoning attacks** and **defensive testing methodologies** for retrieval-augmented generation systems.

> Last version of slides presenting the project and topic: [Google Slides](https://docs.google.com/presentation/d/1mtZcIQFM3ocxwbwhDOykA_kSbJWwcCeU/), made for *testear.la* testing conference.

## What is this?

A single poisoned document can hijack a RAG system. This lab shows you how, and more importantly, gives you the tools and methodology to test whether your own RAG is vulnerable.

**See it in one command:**
```bash
bash scripts/run_demo.sh
```

This walks the whole arc: a clean assistant, a single poisoned document that hijacks it, the two metrics that expose the damage, and the defense layers that walk it back.

Want to adapt it to your own RAG? See [CONTRIBUTING.md](CONTRIBUTING.md).

## Quick Links

- **First time?** Start with [Quick Start](docs/QUICKSTART.md) (5 minutes)
- **Understanding the threat:** [Threat Model](docs/THREAT_MODEL.md)
- **How to test:** [Testing Methodology](docs/TESTING.md)
- **How to defend:** [Defense Layers](docs/DEFENSE_LAYERS.md)
- **Deep dive:** [Full Documentation Index](docs/INDEX.md)

## The Problem

**Scenario:** Cocina Cloud is a meal-planning chatbot with a knowledge base (recipes, policies, FAQs). An attacker adds one poisoned document containing phishing URLs and instruction injection. The chatbot now hands users the attacker's link or states false information with confidence.

**Why it matters:** The attacker doesn't need server access. They only need one document in the corpus.

## The Lab

| Component | What you get |
|-----------|--------------|
| **Production stack** | FastAPI, ChromaDB, Ollama, sentence-transformers |
| **Attack tiers** | Query-aligned → stealth obfuscation → gradient-optimized (GASLITE) |
| **Dual metrics** | RSR (retrieval success) + GCR (generation compromise) |
| **Defense in depth** | 6 controls across ingestion, retrieval, prompt, and output |
| **Test harness** | Pytest-based, point it at your own RAG |

## Installation (2 minutes)

```bash
# Clone and setup
git clone https://github.com/spassarop/rag-poison-lab.git
cd rag-poison-lab
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt

# Get the model
ollama pull llama3.1:8b-instruct-q4_K_M

# Run the demo
bash scripts/run_demo.sh
```

See [Quick Start](docs/QUICKSTART.md) for detailed steps and Docker setup.

## Project Structure

```
rag-poison-lab/
├── README.md                          # This file
├── docs/
│   ├── INDEX.md                       # Full documentation map
│   ├── QUICKSTART.md                  # Installation & first run
│   ├── THREAT_MODEL.md                # What can go wrong & why
│   ├── ARCHITECTURE.md                # System design & data flow
│   ├── API_REFERENCE.md               # Endpoint docs
│   ├── TESTING.md                     # L1-L4 testing framework
│   ├── DEFENSE_LAYERS.md              # What each control catches
│   ├── ATTACKS/
│   │   ├── TIER1_QUERY_ALIGNED.md
│   │   ├── TIER2_STEALTH.md
│   │   └── TIER3_GASLITE.md
│   ├── CORPUS_GENERATION.md
│   └── CI_PIPELINE.md
├── CONTRIBUTING.md                    # Add your own attack case
├── app/                               # FastAPI application
├── corpus/                            # Knowledge base (curated + generated)
├── attacks/                           # Attack tooling & contracts
├── tests/                             # Test harness
└── scripts/                           # Utilities
```

## Key Concepts in 30 Seconds

- **RSR (Retrieval Success Rate):** Does the poisoned document rank in top-k?
- **GCR (Generation Compromise Rate):** Does the model obey the poison when it sees it?
- **Dual metrics matter:** You can have RSR=100% and GCR=0%. Both stages need defense.
- **Attack tiers:** From simple query-matching, to hidden text, to gradient-optimized passages.
- **Defense layers:** Ingestion guards, retrieval filters, prompt spotlighting, output guards.

## Next Steps

1. **See it work:** `bash scripts/run_demo.sh`
2. **Understand why:** Read [Threat Model](docs/THREAT_MODEL.md)
3. **Learn to test:** Follow [Testing Methodology](docs/TESTING.md)
4. **Add your own:** See [CONTRIBUTING.md](CONTRIBUTING.md)

## References

- **OWASP Top 10 for LLM (2026):** LLM01 (Prompt Injection, direct & indirect), LLM05 (Poisoning), LLM07 (Misinformation), LLM09 (Embedding Weaknesses)
- **Research papers:** [PoisonedRAG](https://arxiv.org/abs/2402.07867), [GASLITE](https://arxiv.org/abs/2412.20953), [Spotlighting](https://arxiv.org/abs/2403.14720)

## License

MIT. See [LICENSE](LICENSE).

## Disclaimers

- **Educational and research purposes only.** This demonstrates vulnerabilities to help you build safer systems.
- **Fictional scenario:** Cocina Cloud and all data are fictional. Phishing URLs use the reserved `.test` TLD.
- **Poisoned documents are inert:** They carry only the harmless canary URL and benign instruction strings.
- **Responsible use:** Only test on systems you own or have explicit authorization to test.

---

**Remember:** This is an educational tool. Use responsibly.
