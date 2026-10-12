"""Tests for the demo app.

test_flaky_when_injected only misbehaves when chaos/flaky.on exists (committed by the
chaos workflow). pytest-rerunfailures (see pytest.ini) retries it, demonstrating
healing layer 1: transient/flaky failures absorbed without human action.
"""

import pathlib
import random

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
FLAKY_FLAG = pathlib.Path("chaos/flaky.on")


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_greet_default():
    r = client.get("/greet")
    assert r.status_code == 200
    assert r.json()["message"] == "hello, world"


def test_greet_named():
    r = client.get("/greet", params={"name": "demo"})
    assert r.json()["message"] == "hello, demo"


def test_flaky_when_injected():
    if FLAKY_FLAG.exists():
        # 60% failure per attempt; reruns make eventual pass overwhelmingly likely.
        assert random.random() > 0.6, "simulated flaky failure (chaos/flaky.on present)"
    assert True
