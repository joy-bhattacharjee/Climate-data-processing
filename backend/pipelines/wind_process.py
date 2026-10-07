from pathlib import Path
import pandas as pd

def run_wind_process(start_year: int, end_year: int, lat: float, lon: float, model: str, output_dir: Path, logger=print, is_cancelled=lambda: False):
    src = Path(output_dir) / "fmi_observed_daily_wind_speed_ylivieska.csv"
    dst = Path(output_dir) / "sievi_observed_wind_speed_daily.csv"

    if not src.exists():
        raise FileNotFoundError(f"Missing input: {src.name}")

    df = pd.read_csv(src)
    if "date" not in df or "wind_speed" not in df:
        raise ValueError("Input must have columns: date, wind_speed")

    # availability of source
    dmin = df["date"].min()
    dmax = df["date"].max()
    logger(f"Source wind daily available {dmin} → {dmax}")

    # Build a continuous timeline between detected min and requested end_year
    # You can choose to cap to min(start_year, dmin) and end_year
    end_cap = f"{end_year}-12-31"
    start_cap = min(dmin, f"{start_year}-01-01") if dmin else f"{start_year}-01-01"

    perfect = pd.date_range(start=start_cap, end=end_cap, freq="D").strftime("%Y-%m-%d")
    checked = pd.DataFrame({"date": perfect}).merge(df, on="date", how="left")

    missing = checked["wind_speed"].isna().sum()
    if missing > 0:
        checked["wind_speed"] = checked["wind_speed"].interpolate(method="linear", limit_direction="both")
        logger(f"Interpolated {missing} missing days")

    # availability of processed
    dmin2 = checked["date"].min()
    dmax2 = checked["date"].max()
    logger(f"Processed wind covers {dmin2} → {dmax2} ({len(checked)} rows)")

    checked.to_csv(dst, index=False)
    logger(f"Saved {dst.name}")
