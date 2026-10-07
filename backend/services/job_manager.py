from threading import Thread
from uuid import uuid4

class JobManager:
    def __init__(self):
        # job_id -> dict(status, logs, thread, cancel)
        self.jobs = {}

    def create_job(self):
        job_id = str(uuid4())
        self.jobs[job_id] = {
            "status": "running",
            "logs": [],
            "thread": None,
            "cancel": False,
        }
        return job_id

    def log(self, job_id, message):
        self.jobs[job_id]["logs"].append(message)

    def complete(self, job_id):
        self.jobs[job_id]["status"] = "completed"

    def fail(self, job_id, err):
        self.jobs[job_id]["status"] = "failed"
        self.jobs[job_id]["logs"].append(str(err))

    def cancel(self, job_id):
        if job_id in self.jobs:
            self.jobs[job_id]["cancel"] = True
            self.jobs[job_id]["logs"].append("Cancellation requested.")
            return True
        return False

    def is_cancelled(self, job_id):
        return self.jobs.get(job_id, {}).get("cancel", False)

    def run_in_thread(self, job_id, func, *args, **kwargs):
        t = Thread(target=func, args=args, kwargs=kwargs, daemon=True)
        self.jobs[job_id]["thread"] = t
        t.start()
