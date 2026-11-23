# StrideAlytics Repository Guidance

Use this file as a concise entry point. Follow relevant `.github/instructions/` and `docs/` rules for the files being changed.

## Current scope

Personal use only. PRO, billing, and multi-user features are out of scope; `mobile/` is deferred. Prefer free tiers. Record any deliberate paid API/service decision in `docs/BUSINESS/03-FINANCIAL-MODEL.md`.

## Search Strategy

1. Use `rg`/Grep before opening files.
2. Open only matching regions and the minimum required files.
3. Avoid repository-wide scans.
4. Never load lockfiles unless dependency analysis is required.
5. Never read excluded folders or generated output.
6. Read architecture documentation only when necessary.

Minimize token usage and keep responses concise. Avoid loading files over 500 lines unless required; return diffs or modified functions rather than rewriting whole files. For explicitly requested dependency debugging, temporarily remove the relevant Read/Grep deny entries in `.claude/settings.json`, then restore them.

`requirements/` is archival source material (original `.docx` drafts and blueprints) and is denied by default; `docs/` supersedes it. Ignore it unless asked. To consult one file, convert it on demand (for example `pandoc <file>.docx -t gfm` into the scratchpad) or temporarily lift the deny entries. See `requirements/README.md`.

## Repository map

- `alpha/`: options-screening pipeline and Streamlit dashboard (Python/uv).
- `backend/`: FastAPI API (Python/uv).
- `frontend/`: Vite + React + TypeScript SPA.
- `next-app/`: separate Next.js app; consult `next-app/AGENTS.md`. Read installed Next.js docs only for explicitly requested dependency debugging.
- `mobile/`: deferred Expo/React Native app; do not extend without confirmation.
- `scheduler/`: scheduled Python jobs.
- `database/`: migrations, schema, and RLS.
- `docs/`: business and technical source of truth. Start at `docs/README.md` and `docs/TECHNICAL/00-ARCHITECTURE-INDEX.md`.
- `infra/`: deployment configuration.

For backend work, also follow the relevant `docs/TECHNICAL/RULES/backend/` and `docs/TECHNICAL/RULES/api-flow/API-FLOW.md` guidance.

## Commands

Python modules use Python 3.12 (backend/scheduler) or 3.11+ (alpha) with uv.

**alpha** (run from `alpha/`):
- `uv sync`
- `uv run test_local.py`: core pipeline without external services
- `uv run python app/main.py`: full pipeline (requires Supabase/API keys)
- `streamlit run app/streamlit_app.py`
- `uv run lint|format|typecheck|verify`
- `uv run pytest tests -q`
- `uv run python -m app.inspect_target`: read-only project/status check
- `uv run python app/main.py --dry-run`: fetch and compute without writes
- `ALPHA_EXPECT_PROJECT=<project ref>` aborts if Supabase points elsewhere; `ALPHA_DRY_RUN=1` enables dry-run mode.
- `app/preflight.py` reports missing settings. Sample rows require `ALLOW_SAMPLE_DATA=1` and are never written.

**backend** (run from `backend/`):
- `uv sync`, `uv run dev` (`--once` for one run)
- `uv run lint|format|typecheck|test|verify`
- `uv run pytest tests -q`; one test: `uv run pytest tests/test_services.py::test_name -q`
- Tests use per-test SQLite. For disposable PostgreSQL guidance, see `database/scripts/local_supabase_shim.sql`.
- PostgreSQL tests use `TEST_PG_URL`; they empty tables and reject `DATABASE_URL`. `scripts/smoke_db.py --disposable` requires `SMOKE_DB_URL`.

**frontend** (run from `frontend/`):
- `npm ci`, `npm run dev`
- `npm run verify` (type-check + lint), `npm run build`, `npm test`
- One test file: `npx vitest run <file>`

Setup: `scripts/setup-dev.sh` or `scripts/setup-dev.ps1`.

## Workflow and conventions

- Read docs and matching `.github/instructions/` before technical or business changes; use the layer-specific rules.
- Keep backend endpoints, services, and schemas separate; use the centralized API URL construction patterns.
- `.husky/pre-commit` runs checks for changed modules. Backend/alpha black may modify files and abort; review, stage, and rerun the commit.
- Alpha pre-commit runs ruff, black, and pytest (not mypy). CI has non-blocking steps; a green run does not prove all tests passed.
- For diagrams, follow `.github/instructions/mermaid.instructions.md`; validate and preview `.mmd` files before presenting them. Warn before Mermaid Repair because it uses credits.
- `.claude/SKILLS.md` routes project-specific agents and skills. Verify thresholds and rules against current code/docs.

## Detailed references

Architecture, persistence, trading-rule, and configuration notes formerly kept here are in [docs/TECHNICAL/CLAUDE-CONTEXT.md](docs/TECHNICAL/CLAUDE-CONTEXT.md). Read only relevant sections. Use the relevant layer docs and `docs/TECHNICAL/RULES/README.md` for current conventions.
