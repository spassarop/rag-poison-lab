# Threat Model

What can go wrong and why it matters.

## The Scenario

**Cocina Cloud** is a fictional SaaS for meal planning, recipes, and smart shopping lists with a customer-support chatbot powered by RAG. The bot answers customer questions by retrieving relevant chunks from a knowledge base (recipes, guides, policies, FAQs) and generating responses with an LLM. The knowledge base is written in Spanish (Río de la Plata audience).

An attacker introduces a poisoned document into the knowledge base containing:
- Phishing URLs: `http://login-update.cocinacloud.test/login`
- Instruction injection: prompts that override the system's intended behavior
- Social engineering content disguised as legitimate documentation

The canary URL uses the `.test` TLD (RFC 6761) to ensure it never resolves to a real site.

## Adversary and Entry Point

The attacker does not need access to the model, the server, or the embedding pipeline. They only need to get a single document into the knowledge base: an archived support ticket, an imported community recipe, or a contributed help article. Once ingested, that document's text becomes part of the context retrieved for matching user queries.

## OWASP Mapping (2026)

**LLM01: Prompt Injection** is the primary category. In the 2026 list, LLM01 covers both direct and indirect prompt injection. This scenario is indirect injection: the malicious instructions arrive through retrieved data, not from the user. The payload rides in the corpus and is injected into the prompt at retrieval time. Every case in `corpus_attacks.yaml` is tagged `LLM01`.

The same scenario is closely related to three other 2026 categories:

- **LLM05: Data and Model Poisoning** is the act of introducing a malicious document into the knowledge base, which is corpus poisoning by definition.
- **LLM07: Misinformation** describes the outcome when the knowledge-corruption case leads the assistant to state a false fact with confidence.
- **LLM09: Vector and Embedding Weaknesses** captures how the attack succeeds by manipulating what the dense retriever surfaces from the embedding space.

## Attacker Goals

Two are demonstrated:

1. **Exfiltration and phishing:** Make the assistant hand the user an attacker-controlled URL (the inert `.test` canary).
2. **Knowledge corruption:** Make the assistant state a false fact with confidence.

## Why the Naive Defense Fails

The system prompt explicitly instructs the model not to follow instructions found in the context. However, the demo shows this is insufficient: the model still complies with a sufficiently well-framed injected instruction. Telling a model to ignore malicious data does not reliably separate data from instructions. That separation must be enforced by controls outside the prompt.

## Attack Ladder

Severity escalates across three tiers:

1. **Tier 1: Query-aligned injection.** The poisoned document is crafted to rank highly for likely user queries (echoing the words a user would use), enabling it to reach the top-k results even in a modest corpus.

2. **Tier 2: Stealth and obfuscation.** The same payload is hidden from human review using HTML comments, white-on-white text, zero-width characters, front-matter metadata, and base64 encoding. This approach is designed to survive manual content review.

3. **Tier 3: White-box gradient optimization.** An adversarial passage optimized directly against the embedding model so it retrieves even in large corpora without carrying human-suspicious strings. It is computed offline and injected as a precomputed case, demonstrating why static and signature-based ingestion filters alone are insufficient.

Tiers 1 and 2 are implemented in `corpus/poisoned/`. Tier 3 is run with separate white-box tooling and added as a precomputed passage.

See [Attack Tiers](ATTACKS/TIER1_QUERY_ALIGNED.md) for details on each technique.

## Key Insight: Retrieval is Not Generation

GASLITE (Tier 3) can win at retrieval (RSR = 100%) but fail at generation (GCR = 0%). Two reasons:

1. The gradient-optimized trigger is incoherent text, so the chunk reads as corrupted and the LLM trusts the coherent legitimate chunks.
2. The top-k also pulls the most authoritative legitimate docs on the target topic, which out-argue the poison.

This means:
- You need to measure **two metrics**, not one.
- Retrieval being "hard" is not a safety margin.
- Defense must cover both retrieval (keep poison out of top-k) and generation (don't obey retrieved instructions, scan output).

## References

- OWASP Top 10 for LLM Applications (2026)
- [PoisonedRAG](https://arxiv.org/abs/2402.07867) (USENIX Security 2025)
- [GASLITE](https://arxiv.org/abs/2412.20953) (ACM CCS 2025)
- [Spotlighting](https://arxiv.org/abs/2403.14720) (Microsoft Research)

## Next

- **See the architecture:** [Architecture](ARCHITECTURE.md)
- **Learn to measure it:** [Testing Methodology](TESTING.md)
- **How to defend:** [Defense Layers](DEFENSE_LAYERS.md)
