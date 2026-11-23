---
name: devops-engineer
description: CI/CD and deployment for this repo - GitHub Actions workflows, Dockerfiles, Render (backend), Vercel (frontend), Supabase migrations, and incident response. Use when editing .github/workflows, Dockerfiles, render.yaml, vercel.json, scheduler cron jobs, or responding to a production incident. Stays within free-tier limits.
license: MIT
metadata:
  author: https://github.com/Jeffallan
  company: https://synergetic.solutions
  version: "1.2.0-stride"
  domain: devops
  triggers: CI/CD, deployment, Docker, GitHub Actions, Render, Vercel, cron, workflow, incident response
  role: engineer
  scope: implementation
  output-format: code
  related-skills: security-reviewer, test-master
---

# DevOps Engineer (StrydeAlytics)

Adapted from the upstream `devops-engineer` skill. Kubernetes, Terraform, GitLab CI and platform-engineering material is not used by this repo (CI is GitHub Actions; deploys are Render, Vercel and Supabase on free tiers). `references/gitlab-ci.md`, `kubernetes.md`, `terraform-iac.md` and `platform-engineering.md` are kept only as an archive in case that changes: do NOT read or follow them unless the user explicitly asks.

## This repo's deployment stack

- **CI**: `.github/workflows/` (`ci.yml`, `backend-ci-cd.yml`, `frontend-ci-cd.yml`, `database-migrate.yml`, `database-backup.yml`, `alpha-daily-run.yml`, `market-close.yml`, `weekly.yml`, `health-check.yml`, `reusable-python-task.yml`)
- **Backend**: Docker image, Render free plan (`backend/render.yaml`; sleeps when idle, cold start about 30 s)
- **Frontend**: Vercel (`frontend/vercel.json`)
- **Database**: Supabase Postgres free tier (about 500 MB); migrations in `database/migrations/`
- **Scheduler / alpha**: GitHub Actions cron (free minutes are limited)
- Read `docs/TECHNICAL/LAYERS/06-DEPLOYMENT-LAYER.md` and `07-CI-CD-LAYER.md` first. Use the `deployment-engineer` agent for repo-specific env vars.

## Core Workflow

1. **Assess** - which workflow, image or environment is affected
2. **Implement** - change the workflow, Dockerfile or config
3. **Validate** - lint the YAML, run the relevant tests locally, confirm no destructive changes
4. **Plan rollout** - prepare the deployment summary, rollback step and smoke test
5. **Approve and deploy** - for production, present the summary and rollback plan and get explicit user approval before running deploy commands
6. **Monitor** - check `health-check.yml` and the `/health` endpoint after rollout

## Reference Guide

| Topic | Reference | Load When |
|-------|-----------|-----------|
| GitHub Actions | `references/github-actions.md` | Editing workflows |
| Docker | `references/docker-patterns.md` | Editing Dockerfiles |
| Deployment | `references/deployment-strategies.md` | Rollout and rollback |
| Release | `references/release-automation.md` | Artifacts, versioning |
| Incidents | `references/incident-response.md` | Outages, runbooks, postmortems |

## Constraints

### MUST DO
- Keep workflows within free GitHub Actions minutes; avoid needless cron frequency
- Keep steps that should gate a merge blocking (no `|| echo` on tests, lint or migrations)
- Store secrets in GitHub or Render secrets, never in the repo or workflow YAML
- Pin image tags (no `latest` in production) and run containers as non-root
- Document the rollback step before deploying

### MUST NOT DO
- Deploy to production without explicit approval
- Commit `.env` files or real secrets
- Let a failing migration step report success

## Output Templates

Provide: workflow or Dockerfile change, validation performed, rollback procedure.

### Rollback Procedure Example

```bash
# Render: redeploy the previous successful deploy from the dashboard (or re-run the prior commit's workflow)
# Database: apply the matching database/migrations/NNN_*_down.sql only after reviewing it
curl -f https://<backend-host>/health   # verify
```

Maintained upstream by [@jeffallan](https://github.com/jeffallan).
