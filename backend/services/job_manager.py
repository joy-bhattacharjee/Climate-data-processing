# -*- coding: utf-8 -*-


from threading import Thread
from uuid import uuid4

class JobManager:
    def __init__(self):
        self.jobs = {}  # job_id -> {status, logs}

    def create_job(self):
        job_id = str(uuid4())
        self.jobs[job_id] = {"status": "running", "logs": []}
        return job_id

    def log(self, job_id, message):
        self.jobs[job_id]["logs"].append(message)

    def complete(self, job_id):
        self.jobs[job_id]["status"] = "completed"

    def fail(self, job_id, err):
        self.jobs[job_id]["status"] = "failed"
        self.jobs[job_id]["logs"].append(str(err))

    def run_in_thread(self, func, *args, **kwargs):
        t = Thread(target=func, args=args, kwargs=kwargs, daemon=True)
        t.start()
