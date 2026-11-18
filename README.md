# Mainframe Control Tower

A control-tower web application for monitoring and managing mainframe batch workloads — public marketing site plus an internal operations console (dashboard, jobs, batch streams, dependency map, failures, AI analysis, recovery, reports, datasets, settings, users, audit log).

> Academic / Project Demonstration · COBOL programs and operational data are for demonstration use.

## Backend API

The standalone FastAPI backend, including SQLite persistence, JCL submission,
COBOL sample programs, and API test instructions, is documented in
[backend/README.md](./backend/README.md).

## Frontend

The frontend stack is documented in [TECH_STACK.md](./TECH_STACK.md).

## Local development (Windows + WSL Ubuntu)

Run the frontend with Windows Node.js and the backend inside Ubuntu WSL so the
backend can use GnuCOBOL for real COBOL compilation and indexed-file operations.
The project directory `E:\Mainframe\Mainframe-Project` is `/mnt/e/Mainframe/Mainframe-Project`
inside WSL.

Install the backend system packages once in Ubuntu:

```bash
sudo apt update
sudo apt install -y gnucobol python3-venv python3-pip
cobc --version
```

In an Ubuntu terminal, create the Python environment and start the API:

```bash
cd /mnt/e/Mainframe/Mainframe-Project
python3 -m venv ~/.venvs/mainframe-control-tower
source ~/.venvs/mainframe-control-tower/bin/activate
python -m pip install -r backend/requirements.txt
export CONTROL_TOWER_DATABASE_PATH=/mnt/e/Mainframe/Mainframe-Project/backend/data/control_tower.db
export CONTROL_TOWER_CORS_ORIGINS=http://localhost:8081,http://127.0.0.1:8081,http://localhost:5173,http://127.0.0.1:5173
python -m uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port 8000
```

In a separate PowerShell terminal, install frontend dependencies if needed and
start Vite. Resolve the current WSL IP because Windows localhost forwarding may
not be enabled:

```powershell
Set-Location E:\Mainframe\Mainframe-Project
npm.cmd install
$wslIp = (wsl.exe --distribution Ubuntu --user root --exec /bin/hostname -I).Trim().Split(' ')[0]
$env:CONTROL_TOWER_API_URL = "http://${wslIp}:8000"
npm.cmd run dev -- --host 127.0.0.1 --port 8081 --strictPort
```

Open `http://127.0.0.1:8081`. Verify the backend with
`curl.exe "http://${wslIp}:8000/health"`; it should report
`"executor":"gnucobol"` and `"gnucobol_available":true`. The Vite server
proxies `/api` and `/health` to that backend. If the backend runs on Windows
without GnuCOBOL, it explicitly uses the limited sample-program interpreter
and its VSAM routes return `503`; that mode is not native COBOL or VSAM.

### Tests and production build

Run backend tests from Ubuntu:

```bash
cd /mnt/e/Mainframe/Mainframe-Project
source ~/.venvs/mainframe-control-tower/bin/activate
python -m pip install -r backend/requirements-dev.txt
cd backend
python -m pytest -q
```

Run frontend checks from PowerShell:

```powershell
Set-Location E:\Mainframe\Mainframe-Project
npm.cmd test
npx.cmd tsc --noEmit
npx.cmd eslint src\lib\api\index.ts src\routes\_app.dashboard.tsx src\routes\_app.jobs.index.tsx src\routes\_app.datasets.tsx src\routes\_app.failures.tsx src\routes\_app.recovery.tsx src\routes\_app.reports.tsx
npm.cmd run build
```

To compile and run the bundled greeting program directly in Ubuntu:

```bash
cd /mnt/e/Mainframe/Mainframe-Project/backend/cobol
cobc -x -o /tmp/GREET GREET.cob
/tmp/GREET
```

The backend's VSAM customer API performs actual GnuCOBOL indexed-file
operations when `/health` reports GnuCOBOL available. JES2 is a local queue
simulator, not IBM JES2 or z/OS.

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
