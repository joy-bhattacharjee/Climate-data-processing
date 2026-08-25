# -*- coding: utf-8 -*-

from pathlib import Path
import pandas as pd

def run_wind_process(start_year: int, end_year: int, lat: float, lon: float, model: str, output_dir: Path, logger=print):
    src = output_dir / "fmi_observed_daily_wind_speed_ylivieska.csv"
    dst = output_dir / "sievi_observed_wind_speed_daily.csv"
    END_TARGET_DATE = "2014-12-31"

    if not src.exists():
        raise FileNotFoundError(f"Input wind file not found: {src.name}")

    df = pd.read_csv(src)
    if "date" not in df or "wind_speed" not in df:
        raise ValueError("Input wind file must have columns: date, wind_speed")

    earliest = df["date"].min()
    logger(f"Timeline from {earliest} to {END_TARGET_DATE}")

    perfect = pd.date_range(start=earliest, end=END_TARGET_DATE, freq="D").strftime("%Y-%m-%d")
    checked = pd.DataFrame({"date": perfect}).merge(df, on="date", how="left")
    missing = checked["wind_speed"].isna().sum()
    if missing > 0:
        checked["wind_speed"] = checked["wind_speed"].interpolate(method="linear", limit_direction="both")
        logger(f"Interpolated {missing} missing days")

    checked.to_csv(dst, index=False)
    logger(f"Saved {dst.name} with {len(checked)} rows")
