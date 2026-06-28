"""Defense-in-depth controls, each toggled by an environment flag.

Layers (see README "Defense in Depth"):
  - ingestion_guard: signature scanner (+ optional Veritensor) and a perplexity-style
    anomaly filter, applied before documents enter the vector store.
  - spotlighting: marks retrieved context as untrusted data in the prompt.
  - output_guard: scans the generated answer for the canary / external URLs.
  - role filtering lives in the retriever (sensitivity metadata + per-role WHERE).

No single layer is sufficient: signatures catch tiers 1-2 but not GASLITE; the
anomaly filter catches the non-fluent GASLITE passage but a fluent variant evades it;
spotlighting/output guard act at generation time regardless of how the poison was
retrieved.
"""
