from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from backend.pipelines.gridded_download import (
    run_gridded_download
)

app = FastAPI()


BASE_DIR = Path(__file__).resolve().parent.parent

FRONTEND_DIR = BASE_DIR / "frontend"

OUTPUT_DIR = BASE_DIR / "outputs"


OUTPUT_DIR.mkdir(
    exist_ok=True
)


@app.get("/api/status")
def get_status():

    return {
        "status": "running"
    }


@app.post("/api/run/{step}")
def run_pipeline_step(
    step: str
):

    valid_steps = [

        "gridded-download",
        "gridded-process",
        "wind-download",
        "wind-process",
        "cmip6-download"

    ]


    if step not in valid_steps:

        return {
            "status": "error",
            "message": "Unknown pipeline step"
        }


    return {

        "status": "started",

        "message":
            f"Pipeline step '{step}' started successfully."

    }


app.mount(

    "/",

    StaticFiles(
        directory=FRONTEND_DIR,
        html=True
    ),

    name="frontend"

)