# Documentation Index

Complete map of all documentation. Pick your entry point based on what you want to learn.

## First Time?

1. Start: [README.md](../README.md) (overview + quick links)
2. Run: [Quick Start](QUICKSTART.md) (5 minutes)
3. Understand: [Threat Model](THREAT_MODEL.md) (what can go wrong)

## I Want to Understand the System

- [Threat Model](THREAT_MODEL.md): Adversary, attack ladder, OWASP mapping
- [Architecture](ARCHITECTURE.md): Data flow, component roles, design choices
- [Attack Tiers](ATTACKS/): Details on each attack technique
  - [Tier 1: Query-aligned Injection](ATTACKS/TIER1_QUERY_ALIGNED.md)
  - [Tier 2: Stealth and Obfuscation](ATTACKS/TIER2_STEALTH.md)
  - [Tier 3: GASLITE Gradient Optimization](ATTACKS/TIER3_GASLITE.md)

## I Want to Test My RAG

- [Testing Methodology](TESTING.md): Metrics (RSR/GCR), test harness (L1-L4), contract-based cases
- [API Reference](API_REFERENCE.md): Endpoints, examples, test workflow
- [Quick Start](QUICKSTART.md): Installation and first run

## I Want to Defend My RAG

- [Defense Layers](DEFENSE_LAYERS.md): What each control catches, trade-offs, red-to-green story
- [Architecture](ARCHITECTURE.md): Where defenses land in the pipeline
- [CI Pipeline](CI_PIPELINE.md): CI gates and regression testing

## I Want to Add My Own Attack

- [CONTRIBUTING.md](../CONTRIBUTING.md): Case schema, step-by-step guide
- [Testing Methodology](TESTING.md#attack-cases-contract): How cases become tests
- [Quick Start](QUICKSTART.md#run-tests): Run your tests

## I Want to Deploy to Production

- [Defense Layers](DEFENSE_LAYERS.md): Controls to enable
- [Architecture](ARCHITECTURE.md#environment-configuration): Configuration variables
- [CI Pipeline](CI_PIPELINE.md): Wiring the tests into your pipeline as gates

## Reference

- [API Reference](API_REFERENCE.md): All endpoints
- [Threat Model](THREAT_MODEL.md): OWASP categories, research papers
- [Architecture](ARCHITECTURE.md): Component breakdown
- [Testing Methodology](TESTING.md): Metrics definitions, test harness details

## Document Overview

### Core Docs

| Doc | Purpose | Audience |
|-----|---------|----------|
| [QUICKSTART.md](QUICKSTART.md) | Installation + first run | Everyone |
| [THREAT_MODEL.md](THREAT_MODEL.md) | What/why of attacks | Security engineers, testers |
| [ARCHITECTURE.md](ARCHITECTURE.md) | System design | Developers, architects |
| [TESTING.md](TESTING.md) | How to measure attacks | QA engineers, security teams |
| [DEFENSE_LAYERS.md](DEFENSE_LAYERS.md) | How to defend | Defenders, system owners |
| [API_REFERENCE.md](API_REFERENCE.md) | Endpoint docs | Developers, integrators |

### Deep Dives

| Doc | Purpose |
|-----|---------|
| [ATTACKS/TIER1_QUERY_ALIGNED.md](ATTACKS/TIER1_QUERY_ALIGNED.md) | Query-aligned injection technique |
| [ATTACKS/TIER2_STEALTH.md](ATTACKS/TIER2_STEALTH.md) | Stealth and obfuscation techniques |
| [ATTACKS/TIER3_GASLITE.md](ATTACKS/TIER3_GASLITE.md) | GASLITE gradient-based attack |
| [CORPUS_GENERATION.md](CORPUS_GENERATION.md) | Generating legitimate filler corpus |
| [CI_PIPELINE.md](CI_PIPELINE.md) | GitHub Actions setup and gates |

### Contributing

| Doc | Purpose |
|-----|---------|
| [../CONTRIBUTING.md](../CONTRIBUTING.md) | Add attack cases |

## Recommended Reading Paths

### Path 1: I Have 30 Minutes

1. [README.md](../README.md) (5 min)
2. [Threat Model](THREAT_MODEL.md) (15 min)
3. Run: [Quick Start](QUICKSTART.md) installation (10 min)

### Path 2: I'm a Tester

1. [Quick Start](QUICKSTART.md) (10 min)
2. [Testing Methodology](TESTING.md) (20 min)
3. [API Reference](API_REFERENCE.md) (10 min)
4. Run: `bash scripts/run_demo.sh` (5 min)
5. [CONTRIBUTING.md](../CONTRIBUTING.md) (5 min)

### Path 3: I'm a Security Architect

1. [Threat Model](THREAT_MODEL.md) (20 min)
2. [Architecture](ARCHITECTURE.md) (15 min)
3. [Defense Layers](DEFENSE_LAYERS.md) (15 min)
4. [Attack Tiers](ATTACKS/) (30 min)
5. [Testing Methodology](TESTING.md) (30 min)

### Path 4: I'm Integrating This Into My Pipeline

1. [API Reference](API_REFERENCE.md) (15 min)
2. [Testing Methodology](TESTING.md) (30 min)
3. [CI_PIPELINE.md](CI_PIPELINE.md) (15 min)
4. [CONTRIBUTING.md](../CONTRIBUTING.md) (15 min)
5. [Quick Start](QUICKSTART.md) (20 min)

## Key Concepts Glossary

- **RSR (Retrieval Success Rate):** % of attacks where poison appears in top-k
- **GCR (Generation Compromise Rate):** % of retrieved cases where model obeys poison
- **Canary:** Deterministic string proving compromise (usually a phishing URL)
- **Tier 1:** Query-aligned injection (attacks that match user queries)
- **Tier 2:** Stealth injection (hidden text: HTML comments, base64, zero-width chars)
- **Tier 3:** GASLITE (gradient-optimized adversarial passages)
- **OWASP LLM01:** Prompt injection (direct and indirect)
- **Spotlighting:** Tagging retrieved data to reduce instruction-following
- **Defense in depth:** Multiple layers, each catching what others miss

## Links to Research

- [OWASP Top 10 for LLM (2026)](https://owasp.org/www-project-top-10-for-large-language-model-applications/)
- [PoisonedRAG (USENIX Security 2025)](https://arxiv.org/abs/2402.07867)
- [GASLITE (ACM CCS 2025)](https://arxiv.org/abs/2412.20953)
- [Spotlighting (Microsoft Research)](https://arxiv.org/abs/2403.14720)

## FAQ

**Q: Can I use this against a system I don't own?**
A: No. Only test systems you own or have explicit authorization to test. See [Disclaimers](../README.md#disclaimers).

**Q: What if my RAG isn't in Spanish?**
A: The demo corpus is in Spanish, but you can replace it with your own knowledge base. [CONTRIBUTING.md](../CONTRIBUTING.md) shows how to add cases.

**Q: How do I integrate this into my CI pipeline?**
A: [CI_PIPELINE.md](CI_PIPELINE.md) covers this, including how to add the dynamic gates.

**Q: What if I want to use a different LLM?**
A: Edit `LLM_MODEL` and `JUDGE_MODEL` in `.env`. See [Architecture](ARCHITECTURE.md#environment-configuration).

**Q: Is the poisoned document actually dangerous?**
A: No. It carries only a harmless `.test` canary URL and benign instruction strings. See [Disclaimers](../README.md#disclaimers).

## Questions or Feedback?

- Open an issue on GitHub
- See [CONTRIBUTING.md](../CONTRIBUTING.md) for contribution guidelines
