const stepsDiv = document.getElementById("steps");
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
