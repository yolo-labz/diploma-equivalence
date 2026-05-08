# diploma-equivalence — CLAUDE.md

Brazil-Portugal diploma equivalence automation (v1: auto-match report for
UFPE ↔ UC ementas, per ADR 0002). See vault at
`~/Documents/Notes/1. Projects/Diploma-Equivalence/` for specs, research,
and decisions.

## Credential retrieval (NON-NEGOTIABLE)

**ALL credential access uses the rbw/thumbdrive integration.** No exceptions,
no asking Pedro for passwords, no storing secrets in repo.

### USB thumbdrive chain (documented at `HEALTH-SAVE-STATE.md:77-91`)

1. Verify USB stick is plugged: `lsblk | grep BW_KEYRING` (label
   `fc049664-779a-4e60-925e-f378f8c78ee2`)
2. Mount if needed:
   `mountpoint -q /run/bw-keyring || /run/wrappers/bin/mount /run/bw-keyring`
3. Decrypt master password:
   `MP=$(age -d -i ~/.config/age/bw-keyring.txt /run/bw-keyring/master.age)`
4. Login to Bitwarden via API key from SOPS:
   `cd ~/NixOS && export BW_CLIENTID=$(sops -d secrets/common.yaml | awk '/^bitwarden_rbw_client_id:/ {print $2}')`
   `export BW_CLIENTSECRET=$(sops -d secrets/common.yaml | awk '/^bitwarden_rbw_client_secret:/ {print $2}')`
   `bw login --apikey`
5. Unlock the vault:
   `SESSION=$(bw unlock "$MP" --raw 2>/dev/null)`
6. Query via `BW_SESSION` prefix:
   `BW_SESSION="$SESSION" bw get password <item-id>`
7. Unmount USB when done:
   `/run/wrappers/bin/umount /run/bw-keyring`

**Known issue:** `rbw unlock` (v1.15) requires pinentry — currently broken
in the CLI sandbox. Workaround: `bw` CLI with `--passwordenv` / arg-passed
master password. When NixOS rbw pinentry is fixed, switch back to pure
`rbw unlock` + `rbw get`. Until then, `bw` CLI is the accepted fallback
that still enforces the USB-thumbdrive gate.

### Credentials already retrieved for this repo

| Service | Key/Entry | Status |
|---|---|---|
| GitHub token | `gh auth token` (logged in) | ✅ |
| SonarQube | `sonarqube.home301server.com.br` in Bitwarden | ✅ token in GH secrets |
| PostgreSQL | TBD — pgvector instance not yet provisioned | ⏳ |
| Qdrant | TBD — not yet deployed | ⏳ |

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
| SonarQube | SAST | `https://sonarqube.home301server.com.br/dashboard?id=yolo-labz_diploma-equivalence` |

**Line width:** 100 cols (ruff). **Type mode:** basic (pyright).
**Build:** hatchling. **Python:** ≥3.12.

## Git workflow

Feature branches → PR → main. Never push directly to main.
Commit message style: Conventional Commits (`feat:`, `fix:`, `ci:`, `docs:`).

## Vault separation

Docs, specs, research, decisions, transcripts → `~/Documents/Notes/`.
Code, tools, CI, deploy config → this repo.
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
