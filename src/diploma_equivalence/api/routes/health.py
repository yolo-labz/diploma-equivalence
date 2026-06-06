"""Health and version endpoints.

`/health` is consumed by the Dokku zero-downtime healthcheck (CHECKS file +
app.json) and any external uptime probe. It deliberately does no I/O and
returns immediately so healthchecks aren't gated on downstream dependencies.

`/version` exposes build provenance for ops debugging — populated at image
build time via Docker `--build-arg` and injected as env vars.
"""

from __future__ import annotations

import os

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/version")
async def version() -> dict[str, str]:
    return {
        "version": os.getenv("APP_VERSION", "0.1.0"),
        "git_sha": os.getenv("GIT_SHA", "unknown"),
        "build_date": os.getenv("BUILD_DATE", "unknown"),
    }
