"""FastAPI application factory."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from diploma_equivalence.api.routes.health import router as health_router


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="diploma-equivalence",
        version="0.1.0",
        description="Brazil-Portugal diploma equivalence automation",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=os.getenv("CORS_ORIGINS", "*").split(","),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health_router)

    return app


def main() -> None:
    import uvicorn

    uvicorn.run(
        "diploma_equivalence.main:create_app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", "5000")),
        factory=True,
    )
