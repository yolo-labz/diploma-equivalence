# diploma-equivalence — CLAUDE.md

Brazil-Portugal diploma equivalence automation (v1: auto-match report for
UFPE ↔ UC ementas, per ADR 0002). Specs, research and decisions live in the
project's private notes vault, not in this repo.

## Secrets

Credentials never live in this repository. CI reads them from GitHub Actions secrets and
repository variables (see `.github/workflows/`); local runs take them from the operator's
password manager. Nothing credential-shaped belongs in a commit, an issue or a log line.

## Architecture

Ports-and-adapters (hexagonal):
```
domain/models.py  ←  application/{embed,match}/  ←  infrastructure/ingest/
       ↑                                                      ↑
  Protocol contracts                                   Adapter implementations
       ↓                                                      ↓
application/{embed,match}/service.py              infrastructure/postgres/
                                                         infrastructure/qdrant/
       ↓
api/routes/  (FastAPI)
```

- **Domain**: `CourseUnit`, `MatchResult`, `EmbeddingPort`, `VectorStorePort`,
  `IngestPort`, `CourseUnitRepository`
- **Application**: `EmbeddingService` (encode curriculum texts),
  `MatchService` (nearest-neighbor scoring)
- **Infrastructure**: UC scrape + UFPE EE/EC parsers (moved from vault);
  pgvector + Qdrant adapters (skeleton)
- **API**: FastAPI `create_app()` factory

## Tooling

| Tool | Purpose | Command |
|---|---|---|
| uv | Package manager | `uv sync --dev` |
| ruff | Lint + format | `uv run ruff check && uv run ruff format --check` |
| pyright | Type checker | `uv run pyright` |
| pytest | Tests | `uv run pytest` |
| SonarQube | SAST | CI job `.github/workflows/sonar.yml` |

**Line width:** 100 cols (ruff). **Type mode:** basic (pyright).
**Build:** hatchling. **Python:** ≥3.12.

## Git workflow

Feature branches → PR → main. Never push directly to main.
Commit message style: Conventional Commits (`feat:`, `fix:`, `ci:`, `docs:`).

## Vault separation

Docs, specs, research, decisions, transcripts live in the project's notes vault.
Code, tools, CI, deploy config live here.
Research data (parsed ementas JSON) lives in both:
- Vault: `research/ementas/ufpe-{ee,ec}/json/` (tracked, small)
- Code: `research/ementas/` (gitignored, tools produce these as working copies)

## Quick commands

```bash
# Setup
uv sync --dev

# Lint + type
uv run ruff check && uv run ruff format --check && uv run pyright

# Test
uv run pytest -v

# Run a parser (output goes to vault)
uv run python src/diploma_equivalence/infrastructure/ingest/parse_ufpe_ec_ppc.py

# Run API locally
uv run diploma-serve
```
