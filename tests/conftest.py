"""Pytest fixtures for the black-box attack harness.

The tests run against the live HTTP API (a realistic black box), not by importing
internal functions. Two prerequisites, both done BEFORE running pytest:

  1. Seed the knowledge base WITH the poisoned documents:
         python scripts/seed_db.py --with-poison
  2. Start the API:
         uvicorn app.main:app

Re-seeding from within the test session is intentionally avoided: the API caches
its ChromaDB collection at startup, so deleting/recreating it under a running API
would leave a stale handle. Seeding is therefore an explicit prerequisite.
"""
import os

import httpx
import pytest

from tests.cases import load_attack_cases

API = os.getenv("API_BASE_URL", "http://localhost:8000")


@pytest.fixture(scope="session")
def client():
    """Session HTTP client against the running API. Exits clearly if unreachable."""
    try:
        c = httpx.Client(base_url=API, timeout=120)
        c.get("/health").raise_for_status()
    except Exception as e:
        pytest.exit(
            f"API not reachable at {API} ({e}).\n"
            f"Start it first:\n"
            f"  python scripts/seed_db.py --with-poison\n"
            f"  uvicorn app.main:app",
            returncode=2,
        )
    yield c
    c.close()


@pytest.fixture(scope="session")
def attack_cases():
    """All attack cases from corpus_attacks.yaml."""
    return load_attack_cases()


@pytest.fixture
def chat_fn(client):
    """chat_fn(question, role="customer") -> dict {answer, sources, retrieved_ids}."""
    return lambda q, role="customer": client.post(
        "/chat", json={"question": q, "role": role}
    ).json()


@pytest.fixture
def retrieve_fn(client):
    """retrieve_fn(query, top_k=6) -> list[chunk dict] (each with id/text/source/score)."""
    return lambda q, k=6: client.post(
        "/retrieve", json={"query": q, "top_k": k}
    ).json()["chunks"]
