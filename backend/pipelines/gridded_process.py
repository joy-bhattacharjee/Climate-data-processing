from pathlib import Path
import pandas as pd

def run_gridded_process(start_year: int, end_year: int, lat: float, lon: float, model: str, output_dir: Path, logger=print, is_cancelled=lambda: False):
    inputs = {
        "temperature": output_dir / "finland_daily_temperature.csv",
        "precipitation": output_dir / "finland_daily_precipitation_sum.csv",
        "radiation": output_dir / "finland_daily_global_radiation.csv",
        "humidity": output_dir / "finland_daily_relative_humidity.csv",
    }

    TARGET_START = "1985-01-01"
    TARGET_END = "2014-12-31"

    perfect = pd.date_range(start=TARGET_START, end=TARGET_END, freq="D").strftime("%Y-%m-%d")
    for name, path in inputs.items():
        if is_cancelled(): raise RuntimeError("cancelled")
        logger(f"Process: {name}")
        if not path.exists():
            logger(f"  Missing: {path.name}")
            continue

        df = pd.read_csv(path)
        # availability range in source
        try:
            dmin = pd.to_datetime(df["date"]).min().strftime("%Y-%m-%d")
            dmax = pd.to_datetime(df["date"]).max().strftime("%Y-%m-%d")
            logger(f"  Source {name} available {dmin} → {dmax}")
        except Exception:
            pass

        df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")
        df = df[(df["date"] >= TARGET_START) & (df["date"] <= TARGET_END)].copy()

        val_col = [c for c in df.columns if c != "date"][0]
        checked = pd.DataFrame({"date": perfect}).merge(df, on="date", how="left")

        missing = checked[val_col].isna().sum()
        logger(f"  Expected: {len(checked)} | Present: {checked[val_col].count()} | Missing: {missing}")
        if missing > 0:
            checked[val_col] = checked[val_col].interpolate(method="linear")
            logger("  Interpolated missing values")

        out_name = Path(output_dir) / f"sievi_gridded_{name}_1985_2014.csv"
        # show availability in processed set
        try:
            dmin2 = pd.to_datetime(checked["date"]).min().strftime("%Y-%m-%d")
            dmax2 = pd.to_datetime(checked["date"]).max().strftime("%Y-%m-%d")
            logger(f"  Processed {name} covers {dmin2} → {dmax2}")
        except Exception:
            pass
        checked.to_csv(out_name, index=False)
        logger(f"  Saved {out_name.name}")
