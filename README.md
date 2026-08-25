# Climate Web Platform

Run climate data pipelines (gridded observations, wind station, CMIP6) from the browser.

## Quick start (local)
1) Python 3.11/3.12 installed
2) Create venv and install:
   python -m venv venv
   .\venv\Scripts\Activate.ps1   # Windows
   # source venv/bin/activate    # macOS/Linux
   pip install -r requirements.txt
3) Run API:
   uvicorn backend.main:app --host 0.0.0.0 --port 8000
4) Open http://localhost:8000

## Docker
docker build -t climate-platform .
docker run -p 8000:8000 climate-platform

## Notes
- CMIP6 step requires a valid ~/.cdsapirc.
- Outputs appear in outputs/ (download via UI).
