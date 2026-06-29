#!/usr/bin/env python3
"""Generate the security posture report (L4) as machine-readable JSON.

This is the *posture* artifact (not the CI gate): it runs every attack case against
the live API, computes RSR/GCR, maps results to OWASP / technique / tier, records
the current defense configuration, and writes reports/security_report.json. Re-run
it with defenses on vs off to show the red→green improvement.

It reuses tests/metrics.evaluate_cases (the same metrics the harness uses, so the
numbers match) and tests/judge.majority_safe for canary-less semantic cases.

The human-readable HTML report is produced separately by pytest:
    pytest --html=reports/report.html --self-contained-html

Prerequisites: the API running and seeded (with --with-poison to see the attack).

Usage:
    python scripts/security_report.py
    python scripts/security_report.py --no-judge        # skip semantic cases
    python scripts/security_report.py --out reports/security_report.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import httpx

from app.config import settings
from tests.cases import load_attack_cases
from tests.metrics import evaluate_cases
from tests.judge import majority_safe


def _group(per_case, key):
    """Aggregate per-case results by a key: {value: {cases, retrieved, compromised}}."""
    out = defaultdict(lambda: {"cases": 0, "retrieved": 0, "compromised": 0})
    for c in per_case:
        bucket = out[c.get(key)]
        bucket["cases"] += 1
        bucket["retrieved"] += int(bool(c["retrieved"]))
        bucket["compromised"] += int(bool(c["compromised"]))
    return dict(out)


def main() -> None:
    parser = argparse.ArgumentParser(description="Write the security posture report (security_report.json)")
    parser.add_argument("--api-base-url", default=os.getenv("API_BASE_URL", "http://localhost:8000"))
    parser.add_argument("--top-k", type=int, default=settings.top_k)
    parser.add_argument("--no-judge", action="store_true",
                        help="Skip semantic (judge) cases; only deterministic canary cases")
    parser.add_argument("--out", type=Path,
                        default=Path(__file__).parent.parent / "reports" / "security_report.json")
    args = parser.parse_args()

    cases = load_attack_cases()
    print(f"Loaded {len(cases)} cases. API={args.api_base_url} top_k={args.top_k} "
          f"judge={'off' if args.no_judge else 'on'}")

    with httpx.Client(base_url=args.api_base_url, timeout=180) as client:
        # Fail fast with a clear message if the API is down.
        try:
            client.get("/health").raise_for_status()
        except Exception as e:
            print(f"❌ API not reachable at {args.api_base_url} ({e}). "
                  f"Seed (--with-poison) and start it first.", file=sys.stderr)
            sys.exit(1)

        def retrieve_fn(query, k):
            return client.post("/retrieve", json={"query": query, "top_k": k}).json()["chunks"]

        def chat_fn(question):
            return client.post("/chat", json={"question": question, "role": "customer"}).json()

        judge_fn = None if args.no_judge else (lambda q, a: majority_safe(q, a))

        result = evaluate_cases(cases, retrieve_fn, chat_fn, top_k=args.top_k, judge_fn=judge_fn)

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "api_base_url": args.api_base_url,
        "model": settings.llm_model,
        "judge_model": settings.judge_model if not args.no_judge else None,
        "top_k": args.top_k,
        "temperature": settings.llm_temperature,
        "defenses": {
            "ingestion": settings.defense_ingestion,
            "spotlighting": settings.defense_spotlighting,
            "output": settings.defense_output,
        },
        "summary": {
            "total_cases": result["n_cases"],
            "n_retrieved": result["n_retrieved"],
            "n_compromised": result["n_compromised"],
            "rsr": round(result["rsr"], 4),
            "gcr_conditional": round(result["gcr_conditional"], 4),
            "gcr_absolute": round(result["gcr_absolute"], 4),
        },
        "by_owasp": _group(result["per_case"], "owasp"),
        "by_technique": _group(result["per_case"], "technique"),
        "by_tier": _group(result["per_case"], "tier"),
        "by_layer": _group(result["per_case"], "layer"),
        "cases": result["per_case"],
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    s = report["summary"]
    print(f"RSR={s['rsr']*100:.1f}%  GCR(cond)={s['gcr_conditional']*100:.1f}%  "
          f"GCR(e2e)={s['gcr_absolute']*100:.1f}%  "
          f"compromised={s['n_compromised']}/{s['total_cases']}")
    print(f"Defenses: {report['defenses']}")
    print(f"Report -> {args.out}")


if __name__ == "__main__":
    main()
