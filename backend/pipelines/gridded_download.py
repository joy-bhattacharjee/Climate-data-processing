# -*- coding: utf-8 -*-


from pathlib import Path
import io
import requests
import xarray as xr
import pandas as pd

def run_gridded_download(start_year: int, end_year: int, lat: float, lon: float, model: str, output_dir: Path, logger=print):
    logger(f"Downloading gridded data {start_year}-{end_year} at nearest to lat={lat}, lon={lon}")
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    DATA_CONFIGS = {
        "temperature": {
            "base_url": "https://www.nic.funet.fi/index/geodata/ilmatiede/10km_daily_mean_temperature/netcdf/",
            "file_prefix": "tday",
            "nc_varname": "Tday",
            "outfile": output_dir / "finland_daily_temperature.csv",
        },
        "global_radiation": {
            "base_url": "https://www.nic.funet.fi/index/geodata/ilmatiede/10km_daily_radiation/netcdf/",
            "file_prefix": "globrad",
            "nc_varname": "Globrad",
            "outfile": output_dir / "finland_daily_global_radiation.csv",
        },
        "precipitation": {
            "base_url": "https://www.nic.funet.fi/index/geodata/ilmatiede/10km_daily_precipitation/netcdf/",
            "file_prefix": "RRday",
            "nc_varname": "rrday",
            "outfile": output_dir / "finland_daily_precipitation_sum.csv",
        },
        "relative_humidity": {
            "base_url": "https://www.nic.funet.fi/index/geodata/ilmatiede/10km_daily_avg_rel_hum/netcdf/",
            "file_prefix": "rh",
            "nc_varname": "Rh",
            "outfile": output_dir / "finland_daily_relative_humidity.csv",
        },
    }

    years = range(int(start_year), int(end_year) + 1)

    for var_key, cfg in DATA_CONFIGS.items():
        logger(f"Processing {var_key}")
        chunks = []
        for y in years:
            filename = f"{cfg['file_prefix']}_{y}.nc"
            url = f"{cfg['base_url']}{filename}"

            try:
                r = requests.get(url, timeout=60)
                if r.status_code != 200:
                    alt = f"{cfg['nc_varname'].lower()}_{y}.nc"
                    r = requests.get(f"{cfg['base_url']}{alt}", timeout=60)
                    if r.status_code != 200:
                        logger(f"  Year {y} not available (HTTP {r.status_code})")
                        continue

                raw = r.content
                try:
                    ds = xr.open_dataset(io.BytesIO(raw))  # try netcdf4
                    engine = "NetCDF-4"
                except Exception:
                    ds = xr.open_dataset(io.BytesIO(raw), engine="scipy")  # netcdf3
                    engine = "NetCDF-3"

                # Resolve dims/coords names
                dims = ds.dims
                lat_name = next((n for n in ["Y", "northing", "Lat", "latitude", "y"] if n in dims), None)
                lon_name = next((n for n in ["X", "easting", "Lon", "longitude", "x"] if n in dims), None)
                time_name = next((c for c in ds.coords if c.lower() in ["time", "date", "t"]), "time")

                varname = cfg["nc_varname"]
                if varname not in ds.data_vars:
                    # fallbacks
                    candidates = [v for v in ds.data_vars if var_key[:3].lower() in v.lower() or v.lower() == varname.lower()]
                    varname = candidates[0] if candidates else list(ds.data_vars)[0]

                pt = ds[varname].sel({lat_name: lat, lon_name: lon}, method="nearest").load()
                df = pt.to_dataframe().reset_index()
                df = df[[time_name, varname]].rename(columns={time_name: "date", varname: var_key})
                chunks.append(df)
                logger(f"  {y} ✓ via {engine}")
            except Exception as e:
                logger(f"  {y} skipped: {e}")
            finally:
                try:
                    ds.close()
                except Exception:
                    pass

        if chunks:
            out = pd.concat(chunks, ignore_index=True).sort_values("date")
            if var_key == "temperature" and out[var_key].max() > 150:
                out[var_key] = out[var_key] - 273.15
                logger("  Temperature converted from K to °C")
            out.to_csv(cfg["outfile"], index=False)
            logger(f"Saved {cfg['outfile'].name} with {len(out)} rows")
        else:
            logger(f"No data extracted for {var_key}")
