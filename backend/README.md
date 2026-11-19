# Mainframe Control Tower API

The FastAPI backend uses SQLAlchemy with SQLite for persisted jobs, steps,
datasets, and report history. It provides a bounded JES2-inspired worker queue,
JCL validation and submission, COBOL execution, spool output, system metrics,
and a Telegram Bot integration for mobile monitoring and operations.

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
cp backend/.env.example backend/.env
# Edit backend/.env to configure TELEGRAM_BOT_TOKEN and ADMIN_TELEGRAM_IDS
export CONTROL_TOWER_DATABASE_PATH=/mnt/e/Mainframe/Mainframe-Project/backend/data/control_tower.db
export CONTROL_TOWER_CORS_ORIGINS=http://localhost:8081,http://127.0.0.1:8081,http://localhost:5173,http://127.0.0.1:5173
python -m uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port 8000
```

In PowerShell, get the WSL IP and point the Vite proxy to it (localhost
forwarding is not enabled on every WSL setup):

```powershell
Set-Location E:\Mainframe\Mainframe-Project
$wslIp = (wsl.exe --distribution Ubuntu --user root --exec /bin/hostname -I).Trim().Split(' ')[0]
$env:CONTROL_TOWER_API_URL = "http://${wslIp}:8000"
npm.cmd run dev -- --host 127.0.0.1 --port 8081 --strictPort
```

Open `http://127.0.0.1:8081`; use `curl.exe "http://${wslIp}:8000/health"` to
verify native execution and open `http://${wslIp}:8000/docs` for the interactive
API.

## Telegram Bot Integration

Mainframe Control Tower includes a real Telegram Bot integration for monitoring
and managing mainframe batch workloads directly from the Telegram mobile app.

### Configuration

Set the configuration variables in `backend/.env` (or environment):

| Variable | Description | Default |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | Bot token from Telegram's @BotFather | *(Required to enable bot)* |
| `ADMIN_TELEGRAM_IDS` | Comma-separated list of authorized Telegram user IDs (`*` to allow all) | `*` |
| `TELEGRAM_MODE` | Bot delivery mode: `polling` or `webhook` | `polling` |
| `TELEGRAM_WEBHOOK_URL` | Public HTTPS endpoint for Telegram webhooks (production) | Optional |
| `TELEGRAM_WEBHOOK_SECRET` | Secret token to validate incoming webhook requests | Optional |

### Supported Bot Commands

- `/start` — Welcome message, overview, and interactive navigation menu.
- `/help` — Full bot command and feature reference.
- `/status` — System status, GnuCOBOL compiler health, and queue depth.
- `/jobs` — Recent 10 batch jobs with execution status and return codes.
- `/running` — Currently executing or queued batch workloads.
- `/failed` — Failed batch jobs with error details and return codes.
- `/job <JOB_ID>` — Detailed step execution breakdown for a specific job.
- `/logs <JOB_ID>` — Formatted console logs and SYSOUT/SYSERR spool output.
- `/datasets` — Cataloged SQLite mainframe datasets and record counts.
- `/metrics` — System metrics, success ratios, and average runtimes.
- `/rc` — Mainframe return-code classifications guide.

### Mainframe Return Code Standards

The bot monitors and formats return codes according to mainframe standards:

- **RC 0000** — `SUCCESS`: All steps completed with zero errors.
- **RC 0004** — `WARNING`: Completed with non-fatal warnings or anomalies.
- **RC 0008** — `ERROR`: Execution failed; step error encountered.
- **RC 0012** — `CRITICAL ERROR`: Severe mainframe failure; execution aborted.
- **RC 0130** — `CANCELLED`: Cancelled by operator or scheduler.

### Automated Notifications

When a batch job completes or fails in the JES2 engine, an automated notification
is delivered to authorized Telegram users with:
- Job ID and Job Name
- Executed Program(s)
- Return Code & Classification (e.g. `🟢 RC 0000 – SUCCESS`, `🔴 RC 0008 – ERROR`)
- Execution Status & Duration
- Execution Summary & Spool inspection button

Duplicate notifications are automatically suppressed.

### Running the Telegram Bot

**Method 1: Integrated with FastAPI (Default)**
When `TELEGRAM_BOT_TOKEN` is set, starting the FastAPI application (`uvicorn app.main:app`)
automatically launches the Telegram Bot inside the application lifespan.

**Method 2: Standalone Runner**
To run the Telegram Bot in a dedicated background worker process:
```bash
python -m app.telegram.runner
```

## Tests

```bash
cd /mnt/e/Mainframe/Mainframe-Project
source ~/.venvs/mainframe-control-tower/bin/activate
python -m pip install -r backend/requirements-dev.txt
cd backend
python -m pytest -v
```

The test suite covers:
- Core JCL parsing, COBOL execution, and VSAM operations (`test_backend.py`)
- Telegram bot command handlers, security access control, RC classification, formatters, and notifications (`test_telegram.py`)

## API outline

- `GET /health`
- `GET /api/metrics`
- `GET /api/programs` and `GET /api/programs/{program_name}`
- `POST /api/jcl/parse` and `POST /api/jcl/validate`
- `POST /api/jobs`, `POST /api/jobs/upload`, `GET /api/jobs`,
  `GET /api/jobs/{job_id}`, `GET /api/jobs/{job_id}/steps`,
  `GET /api/jobs/{job_id}/spool`, `POST /api/jobs/{job_id}/retry`, and
  `POST /api/jobs/{job_id}/cancel`
- `GET /api/reports/summary` and `GET /api/reports/jobs`
- `GET /api/datasets`, `POST /api/datasets`, `GET /api/datasets/{name}`,
  `GET /api/datasets/{name}/records`, and
  `PUT /api/datasets/{name}/records`
- `GET`, `POST`, `PUT`, and `DELETE /api/vsam/customers` operations
- `POST /api/telegram/webhook` (Telegram Webhook receiver)
