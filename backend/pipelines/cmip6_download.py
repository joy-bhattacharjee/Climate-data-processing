from pathlib import Path
import os, glob, zipfile
import cdsapi
import xarray as xr

def run_cmip6_download(start_year: int, end_year: int, lat: float, lon: float, model: str, output_dir: Path, logger=print, is_cancelled=lambda: False):
    DATASET = "projections-cmip6"
    MODEL_ID = model or "ec_earth3_cc"
    ALL_MONTHS = [f"{m:02d}" for m in range(1, 13)]
    SIEVI_BBOX = {"lat_min": 63.7, "lat_max": 64.2, "lon_min": 23.9, "lon_max": 24.6}
    VARIABLES = {
        "temperature": "near_surface_air_temperature",
        # "temp_max": "daily_maximum_near_surface_air_temperature",
        # "temp_min": "daily_minimum_near_surface_air_temperature",
        "precipitation": "precipitation",
        # "wind_speed": "near_surface_wind_speed",
    }
    SCENARIO_CONFIGS = {
        "historical": {"experiment": "historical", "years": [str(y) for y in range(1985, 2015)]},
        "ssp245": {"experiment": "ssp2_4_5", "years": [str(y) for y in range(2015, 2100)]},
        "ssp585": {"experiment": "ssp5_8_5", "years": [str(y) for y in range(2015, 2100)]},
    }

    temp_dir = Path(output_dir) / "cmip6_temp"
    final_dir = Path(output_dir) / "sievi_cropped_netcdf_ready"
    temp_dir.mkdir(parents=True, exist_ok=True)
    final_dir.mkdir(parents=True, exist_ok=True)

    client = cdsapi.Client()

    for scen_key, cfg in SCENARIO_CONFIGS.items():
        if is_cancelled(): raise RuntimeError("cancelled")
        logger(f"Scenario: {scen_key}")
        for friendly, cds_var in VARIABLES.items():
            if is_cancelled(): raise RuntimeError("cancelled")
            logger(f"  Variable: {friendly}")
            zip_path = temp_dir / f"raw_{friendly}_{scen_key}.zip"
            extract_dir = temp_dir / f"extracted_{friendly}_{scen_key}"
            extract_dir.mkdir(parents=True, exist_ok=True)

            if zip_path.exists():
                try: zip_path.unlink()
                except Exception: pass

            payload = {
                "temporal_resolution": "daily",
                "experiment": cfg["experiment"],
                "variable": cds_var,
                "model": MODEL_ID,
                "month": ALL_MONTHS,
                "year": cfg["years"],
                "format": "zip",
            }

            try:
                client.retrieve(DATASET, payload).download(str(zip_path))
                for old in glob.glob(str(extract_dir / "*")):
                    try: os.remove(old)
                    except Exception: pass

                with zipfile.ZipFile(zip_path, "r") as zf:
                    zf.extractall(extract_dir)

                nc_files = glob.glob(str(extract_dir / "*.nc"))
                if not nc_files:
                    logger("    No NetCDF files found after extraction")
                    continue

                with xr.open_mfdataset(nc_files, combine="by_coords") as ds:
                    lat_key = "lat" if "lat" in ds.dims else ("latitude" if "latitude" in ds.dims else "y")
                    lon_key = "lon" if "lon" in ds.dims else ("longitude" if "longitude" in ds.dims else "x")

                    if ds[lat_key].values[0] > ds[lat_key].values[-1]:
                        lat_slice = slice(SIEVI_BBOX["lat_max"], SIEVI_BBOX["lat_min"])
                    else:
                        lat_slice = slice(SIEVI_BBOX["lat_min"], SIEVI_BBOX["lat_max"])

                    cropped = ds.sel({lat_key: lat_slice, lon_key: slice(SIEVI_BBOX["lon_min"], SIEVI_BBOX["lon_max"])})
                    for year, ds_year in cropped.groupby("time.year"):
                        if is_cancelled(): raise RuntimeError("cancelled")
                        out_file = final_dir / f"sievi_{friendly}_{scen_key}_{int(year)}.nc"
                        if out_file.exists():
                            continue
                        ld = ds_year.load()
                        ld.encoding.clear()
                        for v in ld.variables:
                            ld[v].encoding.clear()
                        ld.to_netcdf(out_file, format="NETCDF4_CLASSIC")
                        logger(f"      Saved {out_file.name}")
            except Exception as e:
                logger(f"    Failed: {e}")
                continue

    logger("CMIP6 pipeline complete")
