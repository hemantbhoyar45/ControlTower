"""Quick API test for all 4 JCL demo scenarios."""
import subprocess, json, sys

# Get WSL IP
wsl_ip_result = subprocess.run(
    ["wsl.exe", "-d", "Ubuntu", "bash", "-c", "hostname -I | cut -d' ' -f1"],
    capture_output=True, text=True
)
WSL_IP = wsl_ip_result.stdout.strip()
BASE = f"http://{WSL_IP}:8000"
print(f"Backend: {BASE}\n")

SCENARIOS = [
    ("TRNSUCC", "SUCCESS",              0,  "//TRNSUCC  JOB (ACCT),'SUCCESS TEST'\n//STEP001  EXEC PGM=TRNSUCC\n//SYSOUT   DD SYSOUT=*"),
    ("TRNWARN", "WARNING",              4,  "//TRNWARN  JOB (ACCT),'WARNING TEST'\n//STEP001  EXEC PGM=TRNWARN\n//SYSOUT   DD SYSOUT=*"),
    ("TRNERR",  "CRITICAL ERROR",       8,  "//TRNERR   JOB (ACCT),'CRITICAL TEST'\n//STEP001  EXEC PGM=TRNERR\n//SYSOUT   DD SYSOUT=*"),
    ("TRNCRIT", "ADVANCED CRITICAL ERROR", 12, "//TRNCRIT  JOB (ACCT),'ADV CRITICAL TEST'\n//STEP001  EXEC PGM=TRNCRIT\n//SYSOUT   DD SYSOUT=*"),
]

import urllib.request, time

def post(path, data):
    req = urllib.request.Request(
        BASE + path,
        data=json.dumps(data).encode(),
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())

def get(path):
    with urllib.request.urlopen(BASE + path, timeout=30) as r:
        return json.loads(r.read())

all_passed = True

# 1. Test /api/jcl/inspect for each scenario
print("=" * 60)
print("1. TESTING /api/jcl/inspect (non-rejecting validation)")
print("=" * 60)
for name, cls, rc, jcl in SCENARIOS:
    try:
        result = post("/api/jcl/inspect", {"content": jcl})
        valid = result.get("is_valid", False)
        job_name = result.get("job_name", "?")
        steps = len(result.get("steps", []))
        print(f"  {name}: is_valid={valid}, job_name={job_name}, steps={steps} ✅")
    except Exception as e:
        print(f"  {name}: FAILED - {e} ❌")
        all_passed = False

# 2. Submit each job and check result
print()
print("=" * 60)
print("2. TESTING job submission + classification")
print("=" * 60)
for name, expected_cls, expected_rc, jcl in SCENARIOS:
    try:
        job = post("/api/jobs", {"content": jcl})
        job_id = job["id"]
        # Poll up to 30 seconds for completion
        for _ in range(30):
            time.sleep(1)
            job = get(f"/api/jobs/{job_id}")
            if job["status"] not in ("queued", "running"):
                break
        rc = job.get("return_code")
        status = job.get("status")
        cls = job.get("classification", "?")
        ok = rc == expected_rc and cls == expected_cls
        mark = "✅" if ok else "❌"
        print(f"  {name}: status={status}, RC={rc} (expected {expected_rc}), cls={cls} (expected {expected_cls}) {mark}")
        if not ok:
            all_passed = False
    except Exception as e:
        print(f"  {name}: SUBMIT FAILED - {e} ❌")
        all_passed = False

print()
print("=" * 60)
print("RESULT:", "ALL PASSED ✅" if all_passed else "SOME FAILED ❌")
print("=" * 60)
sys.exit(0 if all_passed else 1)
