"""Smoke tests for the web UI. Skipped if the optional `web` extra is absent."""

import pytest

pytest.importorskip("fastapi")
from starlette.testclient import TestClient  # noqa: E402

from gradekeys.webapp import app  # noqa: E402

client = TestClient(app)


def test_index_serves_the_app():
    r = client.get("/")
    assert r.status_code == 200
    assert "GradeKeys" in r.text


def test_song_requires_input():
    r = client.post("/api/song")
    assert r.status_code == 400


def test_arrange_rejects_unknown_job():
    r = client.post("/api/arrange", data={"job_id": "nope", "grade": "3"})
    assert r.status_code == 404
