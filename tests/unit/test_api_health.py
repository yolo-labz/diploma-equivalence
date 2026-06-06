"""Smoke tests for /health and /version endpoints."""

from __future__ import annotations

from fastapi.testclient import TestClient

from diploma_equivalence.main import create_app


def _client() -> TestClient:
    return TestClient(create_app())


class TestHealth:
    def test_health_returns_ok(self):
        with _client() as c:
            r = c.get("/health")
        assert r.status_code == 200
        assert r.json() == {"status": "ok"}


class TestVersion:
    def test_version_returns_defaults_when_env_unset(self, monkeypatch):
        for k in ("APP_VERSION", "GIT_SHA", "BUILD_DATE"):
            monkeypatch.delenv(k, raising=False)
        with _client() as c:
            r = c.get("/version")
        assert r.status_code == 200
        body = r.json()
        assert body["version"] == "0.1.0"
        assert body["git_sha"] == "unknown"
        assert body["build_date"] == "unknown"

    def test_version_reflects_build_args(self, monkeypatch):
        monkeypatch.setenv("APP_VERSION", "1.2.3")
        monkeypatch.setenv("GIT_SHA", "deadbeef")
        monkeypatch.setenv("BUILD_DATE", "2026-05-08T21:00:00Z")
        with _client() as c:
            r = c.get("/version")
        assert r.status_code == 200
        body = r.json()
        assert body == {
            "version": "1.2.3",
            "git_sha": "deadbeef",
            "build_date": "2026-05-08T21:00:00Z",
        }
