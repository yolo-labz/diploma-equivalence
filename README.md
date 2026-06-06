# Diploma Equivalence

Brazil-Portugal diploma equivalence automation: scrape, embed, match, and
explain course-unit-to-discipline mappings for the Brazilian regulatory
equivalence process.

**Live:** (pending Dokku deploy)

## Architecture

```
ports (domain) ← adapters (infrastructure) ← services (application) ← API (presentation)
```

| Layer | Concern |
|---|---|
| `domain/models.py` | CourseUnit, MatchResult — what the system IS |
| `domain/models.py` (Protocols) | EmbeddingPort, VectorStorePort, IngestPort — contract interfaces |
| `application/embed/` | EmbeddingService — orchestrate vector generation |
| `application/match/` | MatchService — nearest-neighbor equivalence scoring |
| `infrastructure/ingest/` | Scrapers and parsers for UC + UFPE ementas |
| `api/routes/` | FastAPI REST endpoints |

## Quick Start

```bash
# Install deps
uv sync --dev

# Run lints + typecheck
uv run ruff check && uv run ruff format --check && uv run pyright

# Run tests
uv run pytest

# Ingest ementa data
uv run diploma-ingest --help

# Serve API
uv run diploma-serve
```

## Tech Stack

| Component | Technology |
|---|---|
| API | FastAPI + Uvicorn |
| Embeddings | sentence-transformers (bge-m3) |
| Vector store | pgvector (Postgres) |
| Matching | cosine similarity + CH-weighted ranking |
| Ingest | httpx + beautifulsoup4 + pdftotext |
| CI | GitHub Actions + SonarQube |
| Deploy | Dokku (Dockerfile multi-stage) |
| Future (Rust) | match-core (distance calc), embed (ONNX inference) |

## Environment Variables

See [`.env.example`](.env.example) for the full reference. Summary:

| Variable | Default | Notes |
|---|---|---|
| `PORT` | `5000` | HTTP listen port — Dokku injects this automatically |
| `CORS_ORIGINS` | `*` | Comma-separated allowed origins |
| `APP_VERSION` / `GIT_SHA` / `BUILD_DATE` | build args | Surfaced at `/version`; set via `docker build --build-arg` (CI does this) |
| `HF_HOME` | `~/.cache/huggingface` | Embedding-model cache dir; only consumed by the offline match CLI |
| `DIPLOMA_VAULT_ROOT` | `~/Documents/Notes/1. Projects/Diploma-Equivalence` | Vault location for the offline match CLI |
| `POSTGRES_DSN` | — | Postgres + pgvector connection string (skeleton — not yet wired) |
| `QDRANT_URL` | — | Qdrant endpoint (skeleton — not yet wired) |

## API Endpoints

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/health` | Liveness probe — used by Dokku `app.json` and the container `HEALTHCHECK` |
| `GET` | `/version` | Reports `APP_VERSION`, `GIT_SHA`, `BUILD_DATE` injected at image build time |

The full match service (POST `/match`, GET `/reports/...`) is intentionally
not yet exposed on the HTTP surface — the offline CLI (`python -m
diploma_equivalence.cli`) is the canonical batch path while Joao's
calibration loop is open.

## Deploy (Dokku)

The image is built from `Dockerfile.dokku`. CI (`docker-build.yml`)
verifies the build and the `/health` + `/version` smoke endpoints on
every PR. Pedro pushes to Dokku from his laptop:

```bash
# One-time on the Dokku host
ssh dokku@dokku.home301server.com.br -- apps:create diploma-equivalence
ssh dokku@dokku.home301server.com.br -- domains:add diploma-equivalence \
    diploma-equivalence.home301server.com.br
ssh dokku@dokku.home301server.com.br -- letsencrypt:enable diploma-equivalence
ssh dokku@dokku.home301server.com.br -- builder-dockerfile:set diploma-equivalence dockerfile-path Dockerfile.dokku
ssh dokku@dokku.home301server.com.br -- config:set diploma-equivalence \
    CORS_ORIGINS="https://diploma-equivalence.home301server.com.br"

# From this repo
git remote add dokku dokku@dokku.home301server.com.br:diploma-equivalence
git push dokku main
```

Health probe + zero-downtime gate:

| Source | Mechanism |
|---|---|
| `app.json` `healthchecks` | Modern Dokku — runs `curl -fsS /health` 30× during deploy, fails if unhealthy |
| `CHECKS` | Legacy Dokku fallback — same probe, plain-text format |
| `HEALTHCHECK` in Dockerfile | Container-runtime probe — also surfaces via `docker ps` |

All three target the same `/health` endpoint to avoid drift.

## License

MIT — see [LICENSE](LICENSE).
