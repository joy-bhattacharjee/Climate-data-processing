from pathlib import Path
from pathlib import Path
print("DEBUG MAIN FILE:", __file__)
print("DEBUG RESOLVED FILE:", Path(__file__).resolve())
print("DEBUG PARENTS:", list(Path(__file__).resolve().parents))

import json
import os
import subprocess
import sys
import threading
import uuid
from datetime import datetime

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"
SCRIPTS_DIR = BACKEND / "scripts_new"
OUTPUTS = ROOT / "outputs"
LOG_DIR = OUTPUTS / "logs"

print("DEBUG ROOT:", ROOT)
print("DEBUG FRONTEND:", FRONTEND)
print("DEBUG FRONTEND EXISTS:", FRONTEND.exists())


OUTPUTS.mkdir(exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)
SCRIPTS_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="Climate Data Processing Platform API")

jobs = {}
processes = {}

STEP_DEFINITIONS = [
    {
        "id": "1A",
        "label": "Observed variables from Paituli / FUNET",
        "patterns": ["01_a_obs", "obs_var_from_1985"]
    },
    {
        "id": "1B",
        "label": "Download and process observed variables from Paituli",
        "patterns": ["01_dnld", "paituli"]
    },
    {
        "id": "2A",
        "label": "Process FMI wind speed 1985–2014",
        "patterns": ["02_a_wsped", "wsped_fmi_from"]
    },
    {
        "id": "2B",
        "label": "Download FMI wind speed",
        "patterns": ["02_dnld_wsped", "dnld_wsped"]
    },
    {
        "id": "3",
        "label": "Download CMIP6 climate variables",
        "patterns": ["03_climate", "climate_all"]
    },
    {
        "id": "4",
        "label": "Process climate variables and create T/P time series",
        "patterns": ["04_processing", "creating_ts"]
    },
    {
        "id": "5",
        "label": "Merge observed variables except wind speed",
        "patterns": ["05_merge", "merge_all_obs"]
    },
    {
        "id": "6",
        "label": "Bias-correct precipitation and temperature",
        "patterns": ["06_bias", "bias_corrected"]
    },
    {
        "id": "7",
        "label": "Generate other variables from bias-corrected T/P",
        "patterns": ["07_generating_other", "other_var_timeseries"]
    },
    {
        "id": "8",
        "label": "Generate 7 unique dt files",
        "patterns": ["08_generating_7", "unique_dt"]
    },
    {
        "id": "9",
        "label": "Modify dt files for simulation",
        "patterns": ["09_modifying", "modifying_all_other"]
    },
]


class RunRequest(BaseModel):
    step: str
    config: dict = {}


def discover_steps():
    files = sorted(SCRIPTS_DIR.glob("*.py"))
    used = set()
    steps = []

    for definition in STEP_DEFINITIONS:
        found = None

        for file_path in files:
            if file_path.name in used:
                continue

            lower_name = file_path.name.lower()

            for pattern in definition["patterns"]:
                pattern = pattern.lower()
                if lower_name.startswith(pattern) or pattern in lower_name:
                    found = file_path
                    break

            if found:
                break

        if found:
            used.add(found.name)
            steps.append({
                "id": definition["id"],
                "label": definition["label"],
                "script": str(found.relative_to(ROOT)).replace("\\", "/")
            })

    generic_number = 1

    for file_path in files:
        if file_path.name in used:
            continue

        steps.append({
            "id": f"X{generic_number}",
            "label": f"Run {file_path.name}",
            "script": str(file_path.relative_to(ROOT)).replace("\\", "/")
        })

        generic_number += 1

    return steps


def log_path(job_id: str):
    return LOG_DIR / f"{job_id}.log"


def write_log(job_id: str, message: str):
    path = log_path(job_id)

    with path.open("a", encoding="utf-8", errors="replace") as f:
        f.write(str(message))

        if not str(message).endswith("\n"):
            f.write("\n")


def run_worker(job_id, selected_steps, config):
    jobs[job_id]["status"] = "running"
    jobs[job_id]["started_at"] = datetime.utcnow().isoformat()

    config_file = LOG_DIR / f"{job_id}_config.json"
    config_file.write_text(json.dumps(config or {}, indent=2), encoding="utf-8")

    env = os.environ.copy()
    env["REPO_ROOT"] = str(ROOT)
    env["OUTPUTS_DIR"] = str(OUTPUTS)
    env["PIPELINE_CONFIG_FILE"] = str(config_file)

    write_log(job_id, f"Job ID: {job_id}")
    write_log(job_id, f"Started: {jobs[job_id]['started_at']}")
    write_log(job_id, f"Repo root: {ROOT}")
    write_log(job_id, f"Scripts folder: {SCRIPTS_DIR}")
    write_log(job_id, f"Outputs folder: {OUTPUTS}")
    write_log(job_id, "-" * 90)

    for step in selected_steps:
        if jobs[job_id]["status"] == "cancelled":
            write_log(job_id, "Job cancelled.")
            return

        script_path = ROOT / step["script"]
        jobs[job_id]["current_step"] = step["id"]

        write_log(job_id, "")
        write_log(job_id, "=" * 90)
        write_log(job_id, f"Running step {step['id']}: {step['label']}")
        write_log(job_id, f"Script: {script_path}")
        write_log(job_id, "=" * 90)

        if not script_path.exists():
            jobs[job_id]["status"] = "failed"
            write_log(job_id, f"ERROR: Script not found: {script_path}")
            return

        try:
            proc = subprocess.Popen(
                [sys.executable, str(script_path)],
                cwd=str(OUTPUTS),
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
            )

            processes[job_id] = proc

            for line in proc.stdout:
                write_log(job_id, line.rstrip("\n"))

            return_code = proc.wait()
            processes.pop(job_id, None)

            if return_code != 0:
                jobs[job_id]["status"] = "failed"
                jobs[job_id]["returncode"] = return_code
                write_log(job_id, f"FAILED with return code {return_code}")
                return

            write_log(job_id, f"Step {step['id']} finished successfully.")

        except Exception as exc:
            jobs[job_id]["status"] = "failed"
            write_log(job_id, f"ERROR running step {step['id']}: {exc}")
            return

    if jobs[job_id]["status"] != "cancelled":
        jobs[job_id]["status"] = "completed"

    jobs[job_id]["finished_at"] = datetime.utcnow().isoformat()
    write_log(job_id, "")
    write_log(job_id, f"Final job status: {jobs[job_id]['status']}")


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "root": str(ROOT),
        "scripts_dir": str(SCRIPTS_DIR),
        "outputs_dir": str(OUTPUTS),
    }


@app.get("/api/steps")
def api_steps():
    return discover_steps()


@app.post("/api/run")
def api_run(req: RunRequest):
    all_steps = discover_steps()

    if req.step.upper() == "ALL":
        selected_steps = all_steps
    else:
        selected_steps = [s for s in all_steps if s["id"] == req.step]

    if not selected_steps:
        raise HTTPException(status_code=404, detail=f"Unknown step: {req.step}")

    job_id = str(uuid.uuid4())[:8]

    jobs[job_id] = {
        "job_id": job_id,
        "status": "queued",
        "requested_step": req.step,
        "current_step": None,
        "created_at": datetime.utcnow().isoformat(),
    }

    thread = threading.Thread(
        target=run_worker,
        args=(job_id, selected_steps, req.config or {}),
        daemon=True,
    )

    thread.start()

    return {
        "job_id": job_id,
        "status": "queued",
        "steps": selected_steps,
    }


@app.get("/api/job/{job_id}")
def api_job(job_id: str, tail: int = 30000):
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    path = log_path(job_id)
    log_text = ""

    if path.exists():
        text = path.read_text(encoding="utf-8", errors="replace")
        log_text = text[-tail:]

    return {
        **jobs[job_id],
        "log": log_text,
    }


@app.post("/api/cancel/{job_id}")
def api_cancel(job_id: str):
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    jobs[job_id]["status"] = "cancelled"

    proc = processes.get(job_id)

    if proc and proc.poll() is None:
        proc.terminate()

    write_log(job_id, "Cancellation requested.")

    return {"status": "cancelled"}


@app.get("/api/outputs")
def api_outputs():
    files = []

    if OUTPUTS.exists():
        for path in OUTPUTS.rglob("*"):
            if path.is_file():
                rel = path.relative_to(OUTPUTS)
                files.append({
                    "name": path.name,
                    "path": str(rel).replace("\\", "/"),
                    "url": "/outputs/" + str(rel).replace("\\", "/"),
                    "size": path.stat().st_size,
                    "modified": path.stat().st_mtime,
                })

    files.sort(key=lambda x: x["modified"], reverse=True)
    return files


app.mount("/outputs", StaticFiles(directory=str(OUTPUTS)), name="outputs")
app.mount("/", StaticFiles(directory=str(FRONTEND), html=True), name="frontend")
