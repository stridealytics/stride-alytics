# Skills & Agents Routing Guide

Two tiers work together. Domain agents know the trading rules; technical skills know how to implement them.

---

## Tier 1 — Custom Domain Agents (`.claude/agents/`)

Invoked with the Agent tool. Each encodes project-specific trading rules, file paths, and architectural constraints.

### Screening & Data
| Agent | Use for |
|-------|---------|
| `option-screener-architect` | Screening logic, filters, Do-Not-Trade rules, alpha pipeline order |
| `liquidity-inspector` | OI/volume/spread/slippage checks |
| `earnings-risk-guardian` | 14-day earnings buffer, catalyst calendar |
| `market-data-engineer` | yfinance/Polygon/FMP pipeline, data quality |
| `technical-entry-expert` | Support/resistance, ATR, RSI, strike selection |
| `volatility-analyst` | IV rank/percentile, HV, term structure, regime score |

### Strategy & Risk
| Agent | Use for |
|-------|---------|
| `option-strategy-reviewer` | Trade validation — max profit/risk, assignment, margin |
| `wheel-strategy-expert` | CSP → assignment → CC progression, annualized return |
| `credit-spread-validator` | Bull put / bear call spreads, R:R, leg-level liquidity |
| `assignment-risk-analyzer` | ITM probability, dividend risk, early exercise, pin risk |
| `risk-manager` | Position sizing, band caps, Base/Growth split, correlation |

### Portfolio & Records
| Agent | Use for |
|-------|---------|
| `trade-journal-auditor` | P&L, audit_events/signal_log, entry/exit rationale |
| `backtest-engineer` | Historical simulation, win rate, Sharpe, drawdown |

### System & Infrastructure
| Agent | Use for |
|-------|---------|
| `band-system-guardian` | Band A–E semantics, assignment pipeline, band caps |
| `dashboard-builder` | Streamlit app, React dashboard, band layout, source labeling |
| `python-quant-developer` | Vectorized pandas/numpy, strict typing, unit tests |
| `database-architect` | Migrations, ORM sync, RLS, append-only tables |
| `deployment-engineer` | Render, Supabase, GitHub Actions, free-tier limits |
| `security-reviewer` | JWT, RLS, auth, audit trail, secrets |
| `principal-system-architect` | Pre-merge final review across all modules |

---

## Tier 2 — Active Technical Skills (plugin: `fullstack-dev-skills`)

Auto-activate by context keywords, or invoke explicitly with `/skill-name`. Load full content only when triggered (~1–2k tokens on-invoke).

| Skill | Layer | Auto-triggers on |
|-------|-------|-----------------|
| `python-pro` | Language | Python typing, async, performance |
| `pandas-pro` | Language | DataFrame, vectorize, time series |
| `fastapi-expert` | Backend | FastAPI, Pydantic, async SQLAlchemy, JWT |
| `postgres-pro` | Database | PostgreSQL, Supabase, RLS, replication |
| `sql-pro` | Database | Migrations, window functions, CTEs, indexes |
| `react-expert` | Frontend | React components, hooks, TanStack Query |
| `typescript-pro` | Frontend | Generics, type guards, strict TS |
| `test-master` | Quality | pytest, vitest, test strategy |
| `security-reviewer` | Quality | SAST, auth review, dependency vulns |
| `code-reviewer` | Quality | Code review process |
| `debugging-wizard` | Quality | Cross-language debugging |
| `devops-engineer` | Ops | CI/CD, GitHub Actions, deployment |

---

## Workflow Routing

### Alpha pipeline change
```
option-screener-architect   ← domain rules & pipeline order
+ python-pro                ← Python patterns
+ pandas-pro                ← vectorized scoring
+ test-master               ← pytest coverage
```

### New backend endpoint
```
option-strategy-reviewer    ← trade validation logic
+ fastapi-expert            ← async endpoint, Pydantic V2
+ postgres-pro              ← query & RLS
+ security-reviewer (both)  ← auth + audit row
```

### Database migration
```
database-architect          ← SQL + ORM dual-change rule
+ postgres-pro              ← RLS policies, triggers
+ sql-pro                   ← migration syntax, indexes
```

### Frontend feature
```
dashboard-builder           ← band layout, source labeling
+ react-expert              ← components, Query hooks
+ typescript-pro            ← strict types
```

### Band system change
```
band-system-guardian        ← semantic invariants
+ python-pro                ← implementation
+ test-master               ← deterministic scoring tests
```

### Scheduler / CI change
```
deployment-engineer         ← GitHub Actions, free-tier limits
+ devops-engineer           ← CI/CD patterns
+ python-pro                ← scheduler script rules
```

### Bug investigation
```
debugging-wizard            ← systematic diagnosis
+ relevant domain agent     ← trading rule context
```

### Pre-merge review (significant features)
```
principal-system-architect  ← architecture + cross-module
+ security-reviewer         ← JWT, RLS, secrets
+ code-reviewer             ← code quality
```

### New strategy type
```
option-strategy-reviewer    ← validation rules
+ volatility-analyst        ← IV/regime context
+ risk-manager              ← sizing + band caps
+ credit-spread-validator   ← if spread-based
```

---

## Dormant Plugin Skills (not primary for this stack)

These 55 are installed and auto-trigger if relevant keywords appear, but are not part of normal workflows here:

`angular-architect`, `api-designer`, `architecture-designer`, `atlassian-mcp`, `chaos-engineer`,
`cli-developer`, `cloud-architect`, `code-documenter`, `cpp-pro`, `csharp-developer`,
`database-optimizer`, `django-expert`, `django-storages-s3`, `dotnet-core-expert`,
`embedded-systems`, `fastapi-expert`\*, `feature-forge`, `fine-tuning-expert`, `flutter-expert`,
`fullstack-guardian`, `game-developer`, `golang-pro`, `graphql-architect`, `java-architect`,
`javascript-pro`, `kotlin-specialist`, `kubernetes-specialist`, `laravel-specialist`,
`legacy-modernizer`, `mcp-developer`, `microservices-architect`, `ml-pipeline`,
`monitoring-expert`, `nestjs-expert`, `nextjs-developer`\*, `pandas-pro`\*, `php-pro`,
`playwright-expert`, `prompt-engineer`, `rag-architect`, `rails-expert`, `react-native-expert`,
`rust-engineer`, `salesforce-developer`, `secure-code-guardian`, `shopify-expert`,
`spark-engineer`, `spec-miner`, `spring-boot-engineer`, `sre-engineer`, `swift-expert`,
`terraform-engineer`, `the-fool`, `vue-expert`, `vue-expert-js`, `websocket-engineer`,
`wordpress-pro`

\* `nextjs-developer` activates if working in `next-app/`; `pandas-pro` activates for alpha work.
