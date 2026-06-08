"""Shared loader for the attack-case contract (corpus_attacks.yaml).

Kept in one place so both the conftest fixtures and pytest_generate_tests load the
cases from the same path, regardless of the current working directory.
"""
from pathlib import Path

import yaml

ATTACKS_PATH = Path(__file__).parent.parent / "attacks" / "corpus_attacks.yaml"


def load_attack_cases():
    """Return the list of attack cases declared in corpus_attacks.yaml."""
    with open(ATTACKS_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)
