# -*- coding: utf-8 -*

import pandas as pd
import requests
from bs4 import BeautifulSoup
from pathlib import Path

def run_wind_download(start_year: int, end_year: int, lat: float, lon: float, model: str, output_dir: Path, logger=print):
    # You can make this configurable via the UI later if needed
    FMI_PORTAL_URL = "https://fmiodata-timeseries-convert.fmi.fi/Ylivieska%20airfield:%201.1.1986%20-%2031.12.2025_6a27d950-7eb0-47f6-b44d-f7caa08c9141.html"
    out_csv = output_dir / "fmi_observed_daily_wind_speed_ylivieska.csv"

    logger(f"Fetching FMI page: {FMI_PORTAL_URL}")
    try:
        r = requests.get(FMI_PORTAL_URL, headers={"User-Agent": "Mozilla/5.0"}, timeout=60)
        r.raise_for_status()
    except Exception as e:
        logger(f"Failed to fetch FMI URL: {e}")
        raise

    soup = BeautifulSoup(r.content, "html.parser")
    text = soup.get_text()
    lines = text.splitlines()
    parsed = []

    for line in lines:
        parts = line.strip().split()
        # Very heuristic — depends on your original page layout
        if len(parts) >= 7 and parts[0] == "Ylivieska" and parts[1] == "airfield":
            try:
                year, month, day, time_str, wind_val = parts[2], parts[3].zfill(2), parts[4].zfill(2), parts[5], parts[6]
                if wind_val.lower() == "nan" or wind_val == "-":
                    continue
                ts = pd.to_datetime(f"{year}-{month}-{day} {time_str}", format="%Y-%m-%d %H:%M")
                parsed.append({"timestamp": ts, "ws": float(wind_val)})
            except Exception:
                continue

    if not parsed:
        logger("No records parsed from raw text; attempting table format...")
        for row in soup.find_all("tr"):
            tds = [td.get_text().strip() for td in row.find_all("td")]
            if len(tds) >= 6 and "Ylivieska" in tds[0]:
                try:
                    ts = pd.to_datetime(f"{tds[1]}-{tds[2].zfill(2)}-{tds[3].zfill(2)} {tds[4]}")
                    parsed.append({"timestamp": ts, "ws": float(tds[5])})
                except Exception:
                    continue

    if not parsed:
        raise RuntimeError("Could not parse FMI HTML layout; verify URL and format")

    dfh = pd.DataFrame(parsed).set_index("timestamp")
    daily = dfh["ws"].resample("1D").mean().reset_index()
    daily["date"] = daily["timestamp"].dt.strftime("%Y-%m-%d")
    daily.rename(columns={"ws": "wind_speed"}, inplace=True)
    # Optional date clip
    daily = daily[["date", "wind_speed"]].dropna().sort_values("date")

    daily.to_csv(out_csv, index=False)
    logger(f"Saved {out_csv.name} with {len(daily)} daily rows")
