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

| Variable | Default | Notes |
|---|---|---|
| `PORT` | `5000` | HTTP listen port |
| `CORS_ORIGINS` | `*` | Comma-separated allowed origins |
| `DATABASE_URL` | — | Postgres connection string (for vector store) |
| `QDRANT_URL` | — | Qdrant endpoint (alternative vector store) |

## License

MIT — see [LICENSE](LICENSE).
