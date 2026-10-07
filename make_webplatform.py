from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parent
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"
SCRIPTS_DIR = BACKEND / "scripts_new"
OUTPUTS = ROOT / "outputs"

REQS = [
    "fastapi>=0.110",
    "uvicorn[standard]>=0.23",
    "pydantic>=2.0",
    "pandas>=2.0",
    "numpy>=1.24",
    "xarray>=2023.6",
    "netCDF4>=1.6",
    "scipy>=1.10",
    "requests>=2.31",
    "beautifulsoup4>=4.12",
    "cdsapi>=0.7",
    "openpyxl>=3.1",
]


def ensure_dirs():
    BACKEND.mkdir(exist_ok=True)
    FRONTEND.mkdir(exist_ok=True)
    SCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUTS.mkdir(exist_ok=True)
    (BACKEND / "__init__.py").touch()


def sync_latest_scripts(source_folder: Path):
    if not source_folder.exists():
        raise FileNotFoundError(f"Scripts folder not found: {source_folder}")

    copied = 0

    for py_file in sorted(source_folder.glob("*.py")):
        if py_file.name in {"quick_update.py", "make_webplatform.py"}:
            continue

        target = SCRIPTS_DIR / py_file.name
        shutil.copy2(py_file, target)
        copied += 1

    if copied == 0:
        raise RuntimeError(f"No .py scripts found in {source_folder}")

    return copied


def write_backend():
    code = r'''
from pathlib import Path
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

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"
SCRIPTS_DIR = BACKEND / "scripts_new"
OUTPUTS = ROOT / "outputs"
LOG_DIR = OUTPUTS / "logs"

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
'''
    (BACKEND / "main.py").write_text(code.strip() + "\n", encoding="utf-8")


def write_frontend():
    index_html = r'''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Climate Data Processing Platform</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link rel="stylesheet" href="style.css">
</head>
<body>
  <header>
    <div>
      <h1>Climate Data Processing Platform</h1>
      <p>Run climate processing scripts from the browser and monitor logs.</p>
    </div>
    <div class="header-actions">
      <a href="https://github.com/joy-bhattacharjee/Climate-data-processing" target="_blank">
        GitHub Repository
      </a>
    </div>
  </header>

  <div class="layout">
    <aside class="panel">
      <h2>Configuration</h2>

      <label>
        Start Year
        <input id="start_year" type="number" value="1985">
      </label>

      <label>
        End Year
        <input id="end_year" type="number" value="2014">
      </label>

      <label>
        Latitude
        <input id="latitude" type="number" step="0.00001" value="63.92297">
      </label>

      <label>
        Longitude
        <input id="longitude" type="number" step="0.00001" value="24.516">
      </label>

      <label>
        Scenarios
        <input id="scenarios" type="text" value="historical,ssp245,ssp585">
      </label>

      <div class="button-col">
        <button id="run_all" class="primary">Run Complete Pipeline</button>
        <button id="cancel_job" class="danger">Cancel Current Job</button>
        <button id="refresh_steps">Refresh Steps</button>
        <button id="refresh_outputs">Refresh Files</button>
        <button id="clear_log">Clear Log</button>
      </div>

      <div class="status-card">
        <h3>Status</h3>
        <p><strong>Current Job:</strong> <span id="job_id">None</span></p>
        <p><strong>State:</strong> <span id="job_status">Idle</span></p>
        <p><strong>Current Step:</strong> <span id="current_step">None</span></p>
      </div>
    </aside>

    <main>
      <section class="panel">
        <h2>Pipeline Steps</h2>
        <div id="steps" class="steps"></div>
      </section>

      <section class="panel">
        <h2>Processing Log</h2>
        <pre id="log">System ready.</pre>
      </section>

      <section class="panel">
        <h2>Generated Files</h2>
        <div id="outputs" class="outputs"></div>
      </section>
    </main>
  </div>

  <script src="app.js"></script>
</body>
</html>
'''

    app_js = r'''const stepsDiv = document.getElementById("steps");
const logBox = document.getElementById("log");
const outputsDiv = document.getElementById("outputs");

const jobIdSpan = document.getElementById("job_id");
const jobStatusSpan = document.getElementById("job_status");
const currentStepSpan = document.getElementById("current_step");

let currentJob = null;
let pollTimer = null;

function getConfig() {
  return {
    start_year: Number(document.getElementById("start_year").value || 1985),
    end_year: Number(document.getElementById("end_year").value || 2014),
    latitude: Number(document.getElementById("latitude").value || 63.92297),
    longitude: Number(document.getElementById("longitude").value || 24.516),
    scenarios: (document.getElementById("scenarios").value || "")
      .split(",")
      .map(s => s.trim())
      .filter(Boolean)
  };
}

function appendLog(message) {
  logBox.textContent += "\n" + message;
  logBox.scrollTop = logBox.scrollHeight;
}

function setStatus(data) {
  jobIdSpan.textContent = data?.job_id || currentJob || "None";
  jobStatusSpan.textContent = data?.status || "Idle";
  currentStepSpan.textContent = data?.current_step || "None";
}

async function loadSteps() {
  const res = await fetch("/api/steps");
  const steps = await res.json();

  stepsDiv.innerHTML = "";

  if (!steps.length) {
    stepsDiv.innerHTML = "<p>No scripts found in backend/scripts_new.</p>";
    return;
  }

  for (const step of steps) {
    const card = document.createElement("div");
    card.className = "step-card";

    const left = document.createElement("div");
    left.innerHTML = `
      <div class="step-id">${step.id}</div>
      <div class="step-title">${step.label}</div>
      <div class="script-path">${step.script}</div>
    `;

    const runBtn = document.createElement("button");
    runBtn.textContent = "Run";
    runBtn.onclick = () => runStep(step.id);

    card.appendChild(left);
    card.appendChild(runBtn);
    stepsDiv.appendChild(card);
  }
}

async function runStep(stepId) {
  if (currentJob) {
    appendLog("A job is already running. Cancel it or wait until it finishes.");
    return;
  }

  appendLog(`Starting ${stepId}...`);

  const res = await fetch("/api/run", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({
      step: stepId,
      config: getConfig()
    })
  });

  const data = await res.json();

  if (!res.ok) {
    appendLog(`ERROR: ${data.detail || "Could not start job"}`);
    return;
  }

  currentJob = data.job_id;
  setStatus(data);
  appendLog(`Job started: ${currentJob}`);

  pollTimer = setInterval(pollJob, 1500);
}

async function pollJob() {
  if (!currentJob) return;

  const res = await fetch(`/api/job/${currentJob}`);
  const data = await res.json();

  if (!res.ok) {
    appendLog("Could not read job status.");
    return;
  }

  setStatus(data);

  if (data.log !== undefined) {
    logBox.textContent = data.log || "";
    logBox.scrollTop = logBox.scrollHeight;
  }

  if (["completed", "failed", "cancelled"].includes(data.status)) {
    clearInterval(pollTimer);
    pollTimer = null;
    appendLog(`\nJob finished with status: ${data.status}`);
    currentJob = null;
    await refreshOutputs();
  }
}

async function cancelJob() {
  if (!currentJob) {
    appendLog("No active job to cancel.");
    return;
  }

  await fetch(`/api/cancel/${currentJob}`, {
    method: "POST"
  });

  appendLog("Cancel requested.");
}

async function refreshOutputs() {
  const res = await fetch("/api/outputs");
  const files = await res.json();

  outputsDiv.innerHTML = "";

  if (!files.length) {
    outputsDiv.innerHTML = "<p>No generated files found in outputs/.</p>";
    return;
  }

  for (const file of files) {
    const row = document.createElement("div");
    row.className = "output-row";

    const sizeKb = (file.size / 1024).toFixed(1);

    row.innerHTML = `
      <span>${file.path}</span>
      <span>${sizeKb} KB</span>
      <a href="${file.url}" target="_blank">Open</a>
    `;

    outputsDiv.appendChild(row);
  }
}

document.getElementById("run_all").onclick = () => runStep("ALL");
document.getElementById("cancel_job").onclick = cancelJob;
document.getElementById("refresh_steps").onclick = loadSteps;
document.getElementById("refresh_outputs").onclick = refreshOutputs;
document.getElementById("clear_log").onclick = () => {
  logBox.textContent = "Log cleared.";
};

loadSteps();
refreshOutputs();
setStatus(null);
'''

    style_css = r'''* {
  box-sizing: border-box;
}

body {
  margin: 0;
  font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  background: #08111f;
  color: #e5e7eb;
}

header {
  display: flex;
  justify-content: space-between;
  gap: 20px;
  align-items: center;
  padding: 18px 24px;
  background: #020617;
  border-bottom: 1px solid #1e293b;
}

header h1 {
  margin: 0;
  font-size: 22px;
}

header p {
  margin: 4px 0 0;
  color: #94a3b8;
}

.header-actions a {
  color: white;
  text-decoration: none;
  background: #1d4ed8;
  padding: 9px 12px;
  border-radius: 8px;
}

.layout {
  display: grid;
  grid-template-columns: 320px minmax(0, 1fr);
  gap: 20px;
  padding: 20px;
}

.panel {
  background: #0f172a;
  border: 1px solid #1e293b;
  border-radius: 12px;
  padding: 16px;
  box-shadow: 0 10px 30px rgba(0,0,0,0.25);
}

aside {
  align-self: start;
  position: sticky;
  top: 20px;
}

h2 {
  margin-top: 0;
  font-size: 18px;
}

h3 {
  margin-bottom: 8px;
}

label {
  display: block;
  margin-bottom: 12px;
  color: #cbd5e1;
  font-size: 14px;
}

input {
  width: 100%;
  margin-top: 5px;
  padding: 9px;
  border-radius: 8px;
  border: 1px solid #334155;
  background: #020617;
  color: #e5e7eb;
}

button {
  border: 0;
  border-radius: 8px;
  padding: 9px 13px;
  background: #334155;
  color: white;
  cursor: pointer;
  font-weight: 600;
}

button:hover {
  background: #475569;
}

button.primary {
  background: #2563eb;
}

button.primary:hover {
  background: #1d4ed8;
}

button.danger {
  background: #dc2626;
}

button.danger:hover {
  background: #b91c1c;
}

.button-col {
  display: grid;
  gap: 8px;
  margin: 16px 0;
}

.status-card {
  background: #020617;
  border: 1px solid #1e293b;
  padding: 12px;
  border-radius: 10px;
}

.status-card p {
  margin: 6px 0;
  color: #cbd5e1;
}

.steps {
  display: grid;
  gap: 10px;
}

.step-card {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 12px;
  align-items: center;
  padding: 13px;
  border: 1px solid #1e293b;
  border-radius: 10px;
  background: #020617;
}

.step-id {
  display: inline-block;
  padding: 3px 8px;
  border-radius: 999px;
  background: #1d4ed8;
  font-weight: 700;
  margin-bottom: 5px;
}

.step-title {
  font-weight: 700;
}

.script-path {
  margin-top: 4px;
  color: #94a3b8;
  font-size: 12px;
}

#log {
  min-height: 360px;
  max-height: 600px;
  overflow: auto;
  background: #020617;
  color: #bfdbfe;
  border: 1px solid #1e293b;
  border-radius: 10px;
  padding: 12px;
  white-space: pre-wrap;
}

.outputs {
  display: grid;
  gap: 8px;
}

.output-row {
  display: grid;
  grid-template-columns: 1fr 100px 80px;
  gap: 10px;
  align-items: center;
  padding: 10px;
  border: 1px solid #1e293b;
  border-radius: 8px;
  background: #020617;
}

.output-row a {
  color: #93c5fd;
}

@media (max-width: 850px) {
  .layout {
    grid-template-columns: 1fr;
  }

  aside {
    position: static;
  }
}
'''

    (FRONTEND / "index.html").write_text(index_html, encoding="utf-8")
    (FRONTEND / "app.js").write_text(app_js, encoding="utf-8")
    (FRONTEND / "style.css").write_text(style_css, encoding="utf-8")


def package_key(req_line: str):
    line = req_line.strip()

    if not line or line.startswith("#"):
        return None

    line = line.split(";", 1)[1].strip()

    for sep in ["==", ">=", "<=", "~=", ">", "<"]:
        if sep in line:
            line = line.split(sep, 1)[1].strip()
            break

    if "[" in line:
        line = line.split("[", 1)[1].strip()

    return line.lower()


def patch_requirements():
    req_file = ROOT / "requirements.txt"

    existing_lines = []
    if req_file.exists():
        existing_lines = req_file.read_text(encoding="utf-8").splitlines()

    existing_packages = set()

    for line in existing_lines:
        key = package_key(line)
        if key:
            existing_packages.add(key)

    final_lines = existing_lines[:]

    for req in REQS:
        key = package_key(req)

        if key and key not in existing_packages:
            final_lines.append(req)
            existing_packages.add(key)

    req_file.write_text("\n".join(final_lines).strip() + "\n", encoding="utf-8")


def patch_gitignore():
    gitignore = ROOT / ".gitignore"

    existing = ""
    if gitignore.exists():
        existing = gitignore.read_text(encoding="utf-8")

    additions = [
        "",
        "# Local runtime logs and large climate downloads",
        "outputs/logs/",
        "**/__pycache__/",
        "*.pyc",
    ]

    text = existing

    for line in additions:
        if line and line not in text:
            text += "\n" + line

    gitignore.write_text(text.strip() + "\n", encoding="utf-8")


def main():
    if len(sys.argv) >= 2:
        source_folder = Path(sys.argv[1]).resolve()
    else:
        source_folder = ROOT / "latest_scripts"

    ensure_dirs()

    copied = sync_latest_scripts(source_folder)

    write_backend()
    write_frontend()
    print("Skipping automatic requirements update.")
    patch_gitignore()

    print("")
    print("DONE.")
    print(f"Copied scripts: {copied}")
    print(f"Scripts folder: {SCRIPTS_DIR}")
    print(f"Backend API: {BACKEND / 'main.py'}")
    print(f"Frontend: {FRONTEND}")
    print("")
    print("Next commands:")
    print('  "C:\\ProgramData\\anaconda3\\python.exe" -m pip install -r requirements.txt')
    print('  "C:\\ProgramData\\anaconda3\\python.exe" -m uvicorn backend.main:app --reload --port 8000')
    print("")
    print("Then open:")
    print("  http://localhost:8000")


if __name__ == "__main__":
    main()
