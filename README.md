# Mainframe Control Tower

A control-tower web application for monitoring and managing mainframe batch workloads — public marketing site plus an internal operations console (dashboard, jobs, batch streams, dependency map, failures, AI analysis, recovery, reports, datasets, settings, users, audit log).

> Academic / Project Demonstration · COBOL programs and operational data are for demonstration use.

## Backend API

The standalone FastAPI backend, including SQLite persistence, JCL submission,
COBOL sample programs, and API test instructions, is documented in
[backend/README.md](./backend/README.md).

## Frontend

The frontend stack is documented in [TECH_STACK.md](./TECH_STACK.md).

## Development

```sh
git clone <this-repository-url>
cd mainframe-control-tower
npm i
npm run dev
```

Start the FastAPI service in a second terminal for the jobs, datasets, dashboard,
and reports pages:

```powershell
py -m pip install -r backend\requirements.txt
py -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

Install GnuCOBOL separately and put `cobc` on `PATH` for compiled COBOL
execution and actual indexed-file VSAM operations. The backend reports compiler
availability at `/health`; without GnuCOBOL it explicitly identifies the
limited sample-program interpreter, and VSAM routes return `503`.

The Vite server proxies API requests to `http://127.0.0.1:8000`. Set
`CONTROL_TOWER_API_URL` if the backend listens elsewhere.

## Scripts

| Script | Purpose |
| --- | --- |
| `npm run dev` | Start the dev server |
| `npm run build` | Production build |
| `npm run build:dev` | Development-mode build (prerender) |
| `npm run preview` | Preview the production build |
| `npm run test` | Run tests (Vitest) |
| `npm run lint` | ESLint |
| `npm run format` | Prettier |

## Deployment

The app builds with Nitro, which supports multiple hosts from one codebase:

- **Vercel** — import the repository (framework preset: **Other**). `vercel.json` supplies the build command (`vite build`) and output directory; the Vercel preset is selected automatically (`VERCEL=1`). No extra dependencies or environment variables needed.
- **Cloudflare** — the default build target (`cloudflare-module` preset), used by the Lovable preview.

See [TECH_STACK.md](./TECH_STACK.md#deployment) for details.

The FastAPI backend is deployed separately. For production API calls, either
serve the backend under the frontend origin at `/api`, or set
`VITE_API_BASE_URL` to its browser-reachable URL and allow the frontend origin
through `CONTROL_TOWER_CORS_ORIGINS`.

## Built with

- TanStack Start (React 19)
- TypeScript
- Tailwind CSS v4
- Vite
