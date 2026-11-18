# Mainframe Control Tower API

The FastAPI backend uses SQLAlchemy with SQLite for persisted jobs, steps,
datasets, and report history. It provides a bounded JES2-inspired worker queue,
JCL validation and submission, COBOL execution, spool output, and system metrics.

## Run locally with GnuCOBOL

For Windows development, run this backend in Ubuntu WSL so `cobc` is available
to the same process that executes COBOL and accesses the indexed file. Install
the system packages once in Ubuntu:

```bash
sudo apt update
sudo apt install -y gnucobol python3-venv python3-pip
cobc --version
```

From an Ubuntu terminal, install Python dependencies and start the API:

```bash
cd /mnt/e/Mainframe/Mainframe-Project
python3 -m venv ~/.venvs/mainframe-control-tower
source ~/.venvs/mainframe-control-tower/bin/activate
python -m pip install -r backend/requirements.txt
export CONTROL_TOWER_DATABASE_PATH=/mnt/e/Mainframe/Mainframe-Project/backend/data/control_tower.db
export CONTROL_TOWER_CORS_ORIGINS=http://localhost:8080,http://127.0.0.1:8080,http://localhost:5173,http://127.0.0.1:5173
python -m uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port 8000
```

Open `http://127.0.0.1:8000/docs` for the interactive API. The database is
created at `backend/data/control_tower.db` by default; set
`CONTROL_TOWER_DATABASE_PATH` to use a different file. Check
`http://127.0.0.1:8000/health` and confirm `gnucobol_available` is `true`
before testing indexed-file operations. Installing GnuCOBOL in WSL does not
make `cobc` available to a backend process running directly on Windows.

## Tests

```bash
cd /mnt/e/Mainframe/Mainframe-Project
source ~/.venvs/mainframe-control-tower/bin/activate
python -m pip install -r backend/requirements-dev.txt
cd backend
python -m pytest -q
```

The backend tests use GnuCOBOL automatically when `cobc` is on `PATH`; they
exercise compiled program execution and the indexed-file insert/read/update/
delete routes. Without `cobc`, tests verify the explicit interpreter fallback
and that VSAM routes report the feature as unavailable.

## Job submission and COBOL execution

Submit JSON to `POST /api/jobs`:

```json
{
  "content": "//GREETCHK JOB (ACCT),'SAMPLE'\n//HELLO EXEC PGM=GREET\n//SYSOUT DD SYSOUT=*\n"
}
```

Alternatively, upload a `.jcl` file to `POST /api/jobs/upload`. Both routes
validate JCL before queueing it and return a job ID. Poll `GET /api/jobs/{id}`
until its status is `completed` or `failed`; the response includes per-step
return codes and output.

When `cobc` (GnuCOBOL) is installed, trusted programs in `backend\cobol`
are compiled and run with it. The bundled programs demonstrate payroll,
transaction processing, customer data, and COBOL-generated reports. Without
the compiler, the fallback interpreter supports only the sample arithmetic and
display statements (working-storage `PIC X` and `PIC 9`; `MOVE`, `ADD`,
`SUBTRACT`, `COMPUTE`, `DISPLAY`, `ACCEPT`, and `STOP RUN`/`GOBACK`). The API
records which executor ran each step; the interpreter is not a COBOL compiler
or a replacement for a mainframe runtime.

The bounded job queue recovers queued and interrupted jobs from SQLite on
restart. JCL may use named `JOB`, `EXEC PGM=...`, and `DD` statements,
including inline `DD *` data terminated by `/*`. `SYSIN DD DSN=...` reads
records from a SQLite dataset. Program names are restricted to files in the
bundled COBOL directory; JCL cannot execute arbitrary commands or paths.

The VSAM customer API (`/api/vsam/customers`) uses the `VSAMCUS` COBOL program
with a persistent GnuCOBOL indexed file (`backend\data\vsam\CUSTOMER.KSDS`) for
insert, read, update, delete, and list operations. These are real local indexed
files when GnuCOBOL is installed, not SQLite-backed VSAM emulation.

JES2 queue management is a local simulator, not IBM JES2 or z/OS. Retry creates
a new persisted job submission; cancellation stops queued jobs or terminates an
active local COBOL subprocess. Spool output is the persisted per-job and
per-step stdout/stderr.

## API outline

- `GET /health`
- `GET /api/metrics`
- `GET /api/programs` and `GET /api/programs/{program_name}`
- `POST /api/jcl/parse` and `POST /api/jcl/validate` (the latter checks the
  approved COBOL library and referenced SYSIN datasets)
- `POST /api/jobs`, `POST /api/jobs/upload`, `GET /api/jobs`,
  `GET /api/jobs/{job_id}`, `GET /api/jobs/{job_id}/steps`,
  `GET /api/jobs/{job_id}/spool`, `POST /api/jobs/{job_id}/retry`, and
  `POST /api/jobs/{job_id}/cancel`
- `GET /api/reports/summary` and `GET /api/reports/jobs` (persisted totals,
  daily activity, and completed COBOL report output)
- `GET /api/datasets`, `POST /api/datasets`, `GET /api/datasets/{name}`,
  `GET /api/datasets/{name}/records`, and
  `PUT /api/datasets/{name}/records`
- `GET`, `POST`, `PUT`, and `DELETE /api/vsam/customers` operations

Dataset names and records are stored in SQLite. Job definitions, parsed steps,
execution statuses, return codes, and COBOL stdout/stderr are also persisted
there. The COBOL samples are in `backend\cobol`, with matching JCL examples in
`backend\jcl`. SQLite connection code and domain models are in
`backend\app\database`; HTTP routers, core execution, services, and schemas are
organized into their corresponding `backend\app` packages.
Regular batch datasets and job history are SQLite-backed. The separate VSAM
customer dataset is held in the GnuCOBOL indexed file. System metrics include
the actual queue depth, persisted job counts, database size, and executor
availability.

## Frontend connection

The Vite development server proxies `/api` and `/health` to
`http://127.0.0.1:8000` by default. Start the frontend and backend in separate
terminals. Set `CONTROL_TOWER_API_URL` before starting Vite to use a different
backend URL. For direct cross-origin browser requests, configure
`CONTROL_TOWER_CORS_ORIGINS` as a comma-separated list of trusted frontend
origins. For a deployed frontend that does not share the backend origin, set
`VITE_API_BASE_URL` to the browser-reachable backend base URL and include that
frontend origin in `CONTROL_TOWER_CORS_ORIGINS`.

The internal console adds a JCL Studio for parse/validation, submission, live
status polling, and spool viewing. Dashboard, jobs, streams, failures, recovery,
datasets, and reports are backed by the API; remaining dependency and AI
analysis views retain their explicitly illustrative demo data.

`backend\.env.example` lists supported backend variables. The application does
not load `.env` files automatically; set the variables in the process
environment before starting Uvicorn.
