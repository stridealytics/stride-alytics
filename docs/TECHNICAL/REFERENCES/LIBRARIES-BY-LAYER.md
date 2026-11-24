# StrideAlytics — Libraries & Tools by Layer

**Complete technology stack breakdown across all architecture layers**

> **SCOPE NOTE (2026-11-14):** Personal use, free tiers by default. Mobile (React Native/Expo) libraries are **deferred**. Datadog, LogRocket and SendGrid/SMTP are **optional** and not needed now; prefer Sentry and UptimeRobot (free) and Slack/Discord webhooks.

---

## 1. Frontend (React + Vite + Tailwind)

The frontend requires Node.js **22.19.0 or newer**. The versions below are the
declared ranges from `frontend/package.json`.

### Core Framework & Build
```
React                          ^19.0.0      - UI library & hooks
React DOM                      ^19.0.0      - DOM renderer
Vite                           ^8.0.16      - Fast build tool & dev server
TypeScript                     ^5.7.2       - Type safety
```

### UI & Styling
```
TailwindCSS                    ^4.3.1       - Utility-first CSS framework
Custom UI components           —             - Components in src/components/ui
Lucide React                   ^0.475.0     - Icon set
```

### State Management & Data
```
Zustand                        ^5.0.2       - Lightweight state management
@tanstack/react-query          ^5.62.0      - Data fetching & caching
Axios                          ^1.7.9       - HTTP client
```

### Forms & Validation
```
react-hook-form               ^7.54.2       - Form state management
Zod                           ^4.6.7        - TypeScript-first validation
```

### Routing & Navigation
```
react-router-dom              ^7.1.1        - Client-side routing
```

### Charts & Visualization
```
Recharts                       ^3.11.1      - Charting library
```

### Testing
```
Vitest                        ^5.1.1        - Unit test framework
@testing-library/react        ^16.3.3       - React component testing
@testing-library/user-event   ^14.6.10      - User interaction simulation
jsdom                         ^31.0.1       - DOM simulation
```

### Development Tools
```
ESLint                        ^9.21.0       - JavaScript linting
Vite Plugin React             ^5.2.0        - React plugin for Vite
```

ESLint remains on 9.x because `eslint-plugin-react` does not yet declare
compatibility with ESLint 10.

### Build & Deployment
```
Node.js                       >=22.19.0     - Supported frontend runtime
Vercel CLI                    Latest        - Deployment tool
```

The complete dependency manifest is maintained in
[`frontend/package.json`](../../../frontend/package.json).

---

## 2. Mobile (React Native + Expo)

### Core Framework
```
React Native                   0.73.0        - Mobile framework
Expo SDK                       50.0.0        - Managed development platform
Expo Router                    Latest        - File-based routing for RN
TypeScript                     5.1.0         - Type safety
```

### UI & Styling
```
NativeWind                     Latest        - Tailwind CSS for React Native
Tamagui                        Latest        - Cross-platform component lib
React Native SVG              13.12.0        - SVG support for React Native
Lucide React Native           Latest         - Icons for React Native
```

### State Management & Data
```
Zustand                        4.4.0         - Lightweight state management
@tanstack/react-query          4.32.0        - Data fetching & caching
Axios                          1.4.0         - HTTP client
```

### Navigation
```
@react-navigation/native      Latest         - Navigation library
@react-navigation/stack       Latest         - Stack navigator
@react-navigation/bottom-tabs Latest         - Tab navigator
Expo Router                    Latest         - File-based routing
```

### Charts & Visualization
```
Victory Native                Latest         - Mobile-ready charts
React Native SVG              13.12.0        - Vector graphics
```

### Authentication & Storage
```
Supabase JS Client            Latest         - Backend client
expo-secure-store             Latest         - Secure token storage
expo-local-authentication     Latest         - Biometric auth
```

### Native Features
```
expo-notifications            Latest         - Push notifications
expo-asset                    Latest         - Asset management
expo-font                     Latest         - Font loading
expo-splash-screen            Latest         - Splash screen
expo-status-bar               Latest         - Status bar
expo-battery                  Latest         - Battery info
expo-constants                Latest         - App constants
```

### Testing
```
Jest                          29.6.0         - Test framework
@testing-library/react-native Latest         - React Native testing
detox                         Latest         - E2E testing
```

### Build & Deployment
```
Expo EAS CLI                   Latest         - Build & submit service
Expo Prebuild                  Latest         - Native project generation
```

### Complete Dependencies List

```json
{
  "devDependencies": {
    "@testing-library/react-native": "^latest",
    "@types/react": "^18.2.0",
    "@types/react-native": "^0.73.0",
    "detox": "^latest",
    "detox-cli": "^latest",
    "jest": "^29.6.0",
    "typescript": "^5.1.0"
  },
  "dependencies": {
    "@hookform/resolvers": "^3.3.0",
    "@react-navigation/bottom-tabs": "^latest",
    "@react-navigation/native": "^latest",
    "@react-navigation/stack": "^latest",
    "@supabase/supabase-js": "^latest",
    "@tanstack/react-query": "^4.32.0",
    "axios": "^1.4.0",
    "expo": "^50.0.0",
    "expo-asset": "^latest",
    "expo-battery": "^latest",
    "expo-constants": "^latest",
    "expo-font": "^latest",
    "expo-local-authentication": "^latest",
    "expo-notifications": "^latest",
    "expo-router": "^latest",
    "expo-secure-store": "^latest",
    "expo-splash-screen": "^latest",
    "expo-status-bar": "^latest",
    "nativewind": "^latest",
    "react": "^18.2.0",
    "react-hook-form": "^7.45.0",
    "react-native": "^0.73.0",
    "react-native-svg": "^13.12.0",
    "react-native-web": "^latest",
    "tamagui": "^latest",
    "victory-native": "^latest",
    "zod": "^3.22.0",
    "zustand": "^4.4.0"
  }
}
```

---

## 3. Backend (FastAPI + Python)

The backend supports Python **3.12–3.15**. Python 3.15.2 is used for the
local default, Docker image, and Render deployment; CI tests Python 3.12,
3.13, 3.14, and 3.15.

The separate alpha screening pipeline declares Python **3.11–3.15** support
and uses Pandas **3.1.1** in `alpha/uv.lock`. Its CI matrix tests all five
Python versions. Formatter and lint targets remain Python 3.11 to preserve
compatibility with the declared minimum.

Current locked versions are declared in `backend/uv.lock`:

| Package | Locked version | Purpose |
|---------|----------------|---------|
| FastAPI | 0.165.0 | API framework |
| Uvicorn | 0.54.0 | ASGI server |
| Pydantic | 2.14.4 | Validation and settings |
| SQLAlchemy | 2.1.9 | Database ORM |
| Psycopg | 3.3.9 | PostgreSQL driver |
| NumPy | 2.5.5 | Numerical computing |
| Pandas | 3.1.1 | Data processing |
| yfinance | 1.8.0 | Market data |
| HTTPX | 0.28.1 | Async HTTP client |
| HTTPX2 | 2.16.2 | Starlette test client (dev only) |
| pytest | 9.2.0 | Test framework |
| pytest-asyncio | 1.5.0 | Async test support |
| Ruff | 0.15.22 | Linting |
| Black | 26.10.1 | Formatting |
| mypy | 2.4.1 | Type checking |

Ruff remains below 0.16 because Ruff 0.17.6 surfaced 177 lint findings;
reconcile those rules separately before upgrading it.

Upgrade dependency inputs in `backend/pyproject.toml`, regenerate the lock
with `uv lock --upgrade`, and validate with `uv run verify`.

---

## 4. Database (Supabase PostgreSQL)

### Database Engine
```
PostgreSQL                    15+           - Relational database
```

### Supabase Platform
```
Supabase Auth                 Latest        - JWT authentication
Supabase Storage              Latest        - File storage (optional)
Supabase Edge Functions       Latest        - Serverless functions (optional)
Supabase Realtime             Latest        - Real-time subscriptions (optional)
```

### Extensions
```
pg_cron                       Latest        - Scheduled jobs
pgvector                      Latest        - Vector similarity search
uuid-ossp                     Latest        - UUID generation
```

### Migrations & CLI
```
Supabase CLI                  1.92+         - CLI tool for migrations
```

---

## 5. Deployment & Infrastructure

### Web Hosting
```
Vercel                        Latest        - Frontend hosting & CDN
```

### Backend Hosting
```
Render                        Latest        - Backend server hosting
```

### Database Hosting
```
Supabase                      Latest        - Managed PostgreSQL
```

### Mobile
```
Expo EAS                      Latest        - Mobile build & CI/CD
```

### Containerization
```
Docker                        Latest        - Container runtime
Docker Compose                Latest        - Multi-container orchestration
```

### CI/CD
```
GitHub Actions                Latest        - Workflow automation
```

### Monitoring (Optional)
```
Datadog                       Latest        - APM & monitoring
Sentry                        Latest        - Error tracking
LogRocket                     Latest        - Session replay
UptimeRobot                   Latest        - Uptime monitoring
Cloudflare                    Latest        - DDoS protection
```

---

## 6. Shared Libraries

### TypeScript Types & Utilities
```
TypeScript                    5.1.0         - Type definitions
```

### API Client
```
Axios                         1.4.0         - HTTP client (shared)
```

---

## Quick Reference Table

| Category | Tool | Version | Purpose |
|----------|------|---------|---------|
| **Web Frontend** | React | 19 | UI Framework |
| | Vite | 8 | Build Tool |
| | Recharts | 3.11 | Charts |
| | TailwindCSS | 4 | Styling |
| | Node.js | 22.19+ | Runtime minimum |
| **Mobile** | React Native | 0.73 | Mobile Framework |
| | Expo | 50.0 | Development Platform |
| | NativeWind | Latest | Mobile Styling |
| **Backend** | FastAPI | 0.165 | API Framework |
| | Uvicorn | 0.54 | ASGI Server |
| | Pydantic | 2.14 | Validation |
| **Database** | PostgreSQL | 15+ | Database |
| | Supabase | Latest | Platform |
| **Deployment** | Vercel | Latest | Web Hosting |
| | Render | Latest | API Hosting |
| | Expo EAS | Latest | Mobile Build |
| **CI/CD** | GitHub Actions | Latest | Automation |

---

## Version Update Schedule

- **Frontend:** Quarterly (React, Vite patches monthly)
- **Mobile:** Quarterly (Expo SDK yearly)
- **Backend:** Quarterly (FastAPI patches monthly)
- **Database:** Managed by Supabase (automatic)
- **Deployment:** Continuous (managed platforms)

---

## Security & Compliance

All major libraries are:
- ✅ Actively maintained
- ✅ Community verified
- ✅ Regularly updated
- ✅ Industry standard
- ✅ Open source (where applicable)

---

## Next Steps

- **View Infrastructure?** → [06-DEPLOYMENT-LAYER](../LAYERS/06-DEPLOYMENT-LAYER.md)
- **Check Diagrams?** → [02-SYSTEM-DIAGRAMS](../02-SYSTEM-DIAGRAMS.md)

---

**Version:** A | **Last Updated:** 2026-11-24
