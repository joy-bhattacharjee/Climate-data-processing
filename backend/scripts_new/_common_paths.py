from pathlib import Path
import os
import json

REPO_ROOT = Path(os.environ.get("REPO_ROOT", Path(__file__).resolve().parents[3]))
OUTPUTS_DIR = Path(os.environ.get("OUTPUTS_DIR", REPO_ROOT / "outputs"))

CONFIG_FILE = os.environ.get("PIPELINE_CONFIG_FILE")
PIPELINE_CONFIG = {}

if CONFIG_FILE and Path(CONFIG_FILE).exists():
    try:
        PIPELINE_CONFIG = json.loads(Path(CONFIG_FILE).read_text(encoding="utf-8"))
    except Exception as e:
        print(f"WARNING: Could not parse PIPELINE_CONFIG_FILE: {e}")

GRIDDED_DIR = OUTPUTS_DIR / "gridded_data"
DAILY_TS_DIR = OUTPUTS_DIR / "sievi_daily_time_series"
NETCDF_DIR = OUTPUTS_DIR / "sievi_cropped_netcdf_ready"
RAW_ZIP_DIR = OUTPUTS_DIR / "temporary_raw_zips"
DT_DIR = OUTPUTS_DIR / "for_generating_dt_files"
READY_DT_DIR = DT_DIR / "ready_to_run"
LOG_DIR = OUTPUTS_DIR / "logs"

for folder in [
    OUTPUTS_DIR,
    GRIDDED_DIR,
    DAILY_TS_DIR,
    NETCDF_DIR,
    RAW_ZIP_DIR,
    DT_DIR,
    READY_DT_DIR,
    LOG_DIR,
]:
    folder.mkdir(parents=True, exist_ok=True)

def cfg(name, default=None):
    if name in PIPELINE_CONFIG:
        return PIPELINE_CONFIG[name]

    env_key = f"PIPE_{name.upper()}"
    if env_key in os.environ:
        value = os.environ[env_key]
        try:
            return json.loads(value)
        except Exception:
            return value

    return default
