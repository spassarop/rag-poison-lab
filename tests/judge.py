"""L3 LLM-as-judge — thin re-export of the shared judge in app.defenses.llm_judge.

The core lives in app/ so the runtime semantic guard can use it too; the test harness
(tests/test_l3_llm_judge.py) and scripts/security_report.py import it from here.
"""
from app.defenses.llm_judge import (  # noqa: F401
    JudgeVerdict,
    JUDGE_SYSTEM,
    judge,
    majority_safe,
)
