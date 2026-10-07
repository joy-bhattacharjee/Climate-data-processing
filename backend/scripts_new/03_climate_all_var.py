# -*- coding: utf-8 -*-
"""
Created on Thu Aug 13 15:47:00 2026

@author: bhattaj1
"""
# go to C:\Users\bhattaj1\climate-web-platform
# open terminal/bash and apply
# & "C:\ProgramData\anaconda3\python" -m uvicorn backend.main:app --reload
# -*- coding: utf-8 -*-
"""
Stable CMIP6 climate data extraction pipeline

Fixes:
1. Explicit time/time_bnds encoding to avoid CF warning.
2. Prevents NetCDF "NC_UNLIMITED size already in use" errors.
3. Reuses existing raw ZIP files.
4. Downloads ONLY years that are not already present in the raw ZIP.
5. Never redownloads an already downloaded year.
6. Existing annual NetCDF files are also skipped.
"""

import os
import glob
import zipfile
import tempfile
import shutil
import warnings

import cdsapi
import xarray as xr


# =====================================================================
# CONFIGURATION
# =====================================================================

DATASET = "projections-cmip6"
MODEL_ID = "ec_earth3_cc"

# Precise local coordinate boundaries for the Sievi/Ylivieska region
SIEVI_BBOX = {
    "lat_min": 63.6,
    "lat_max": 64.4,
    "lon_min": 23.9,
    "lon_max": 24.6
}

ALL_MONTHS = [f"{m:02d}" for m in range(1, 13)]

# Required variables
VARIABLES = {
    "temperature": "near_surface_air_temperature",
    "precipitation": "precipitation",
    "temp_max": "daily_maximum_near_surface_air_temperature",
    "temp_min": "daily_minimum_near_surface_air_temperature",

    # "radiation": "surface_downwelling_shortwave_radiation",
    # "humidity": "near_surface_relative_humidity",
    # "wind_speed": "near_surface_wind_speed"
}


# =====================================================================
# SCENARIO CONFIGURATION
# =====================================================================

SCENARIO_CONFIGS = {
    "historical": {
        "experiment": "historical",
        "years": [str(y) for y in range(1985, 2015)]
    },

    # "ssp245": {
    #     "experiment": "ssp2_4_5",
    #     "years": [str(y) for y in range(2015, 2100)]
    # },

    "ssp585": {
        "experiment": "ssp5_8_5",
        "years": [str(y) for y in range(2015, 2100)]
    }
}


# =====================================================================
# FOLDER MANAGEMENT
# =====================================================================

path_com = r"C:\Users\bhattaj1\Desktop\Rewater\Climate_Data_&_Script"

TEMP_ZIP_DIR = os.path.join(path_com, "temporary_raw_zips")
FINAL_OUTPUT_DIR = os.path.join(
    path_com,
    "sievi_cropped_netcdf_ready"
)

os.makedirs(TEMP_ZIP_DIR, exist_ok=True)
os.makedirs(FINAL_OUTPUT_DIR, exist_ok=True)


# =====================================================================
# HELPER: FIND YEARS INSIDE A ZIP
# =====================================================================

def get_years_from_zip(zip_path):
    """
    Inspect NetCDF filenames inside a ZIP and return the years found.

    Example filenames:
        tas_day_EC-Earth3_historical_1985.nc
        pr_day_EC-Earth3_historical_1986.nc

    The function looks for 4-digit years anywhere in the filename.
    """

    import re

    years_found = set()

    if not os.path.exists(zip_path):
        return years_found

    try:
        with zipfile.ZipFile(zip_path, "r") as z:
            for name in z.namelist():

                if not name.lower().endswith(".nc"):
                    continue

                matches = re.findall(r"(19\d{2}|20\d{2}|21\d{2})", name)

                for match in matches:
                    years_found.add(match)

    except zipfile.BadZipFile:
        print(f"    ⚠️ Existing ZIP is corrupted: {zip_path}")
        return set()

    return years_found


# =====================================================================
# HELPER: EXTRACT ZIP
# =====================================================================

def extract_zip(zip_path, extraction_folder):
    """
    Extract a ZIP without deleting existing extracted files.

    Existing files are left untouched.
    """

    os.makedirs(extraction_folder, exist_ok=True)

    try:
        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            zip_ref.extractall(extraction_folder)

        return True

    except zipfile.BadZipFile:
        print(f"    ❌ Invalid ZIP archive: {zip_path}")
        return False


# =====================================================================
# HELPER: FIND NC FILES
# =====================================================================

def find_nc_files(extraction_folder):
    """
    Recursively find all NetCDF files inside extraction folder.
    """

    return glob.glob(
        os.path.join(extraction_folder, "**", "*.nc"),
        recursive=True
    )


# =====================================================================
# HELPER: DETECT YEARS FROM NETCDF FILES
# =====================================================================

def get_years_from_nc_files(nc_files):
    """
    Determine which calendar years are actually represented
    by the NetCDF files.

    This is more reliable than relying only on filenames.
    """

    years_found = set()

    for nc_file in nc_files:

        try:
            with xr.open_dataset(
                nc_file,
                decode_times=True
            ) as temp_ds:

                if "time" not in temp_ds.coords:
                    continue

                years = temp_ds["time"].dt.year.values

                for year in years:
                    years_found.add(str(int(year)))

        except Exception as e:
            print(
                f"    ⚠️ Could not inspect {os.path.basename(nc_file)}: {e}"
            )

    return years_found


# =====================================================================
# HELPER: SAVE ANNUAL NETCDF SAFELY
# =====================================================================

def save_annual_netcdf(ds_year, annual_target_path):
    """
    Safely write one annual dataset.

    Important fixes:
    - Remove inherited NetCDF encodings.
    - Explicitly specify time units.
    - Explicitly specify time_bnds units if present.
    - Do NOT use unlimited dimensions.
    - Use NETCDF4_CLASSIC.
    """

    # Load data completely before closing source datasets
    loaded_ds = ds_year.load()

    # -------------------------------------------------------------
    # Remove inherited encodings
    # -------------------------------------------------------------

    loaded_ds.encoding = {}

    for variable_name in loaded_ds.variables:
        loaded_ds[variable_name].encoding = {}

    # -------------------------------------------------------------
    # Explicit TIME encoding
    # -------------------------------------------------------------

    if "time" in loaded_ds.variables:

        time_encoding = {
            "units": "days since 1950-01-01 00:00:00",
            "calendar": "standard"
        }

        loaded_ds["time"].encoding.update(time_encoding)

    # -------------------------------------------------------------
    # Explicit TIME BOUNDS encoding
    # -------------------------------------------------------------

    if "time_bnds" in loaded_ds.variables:

        loaded_ds["time_bnds"].encoding.update({
            "units": "days since 1950-01-01 00:00:00",
            "calendar": "standard"
        })

    # Some CMIP files use a different name for the bounds variable.
    if "time_bounds" in loaded_ds.variables:

        loaded_ds["time_bounds"].encoding.update({
            "units": "days since 1950-01-01 00:00:00",
            "calendar": "standard"
        })

    # -------------------------------------------------------------
    # IMPORTANT:
    # Do NOT create any unlimited dimensions.
    # This prevents:
    #
    # NetCDF: NC_UNLIMITED size already in use
    # -------------------------------------------------------------

    loaded_ds.to_netcdf(
        annual_target_path,
        format="NETCDF4_CLASSIC",
        unlimited_dims=[]
    )


# =====================================================================
# MAIN PIPELINE
# =====================================================================

def execute_stable_climate_pipeline():

    client = cdsapi.Client()

    # Only suppress the specific xarray UserWarning.
    warnings.filterwarnings(
        "ignore",
        category=UserWarning,
        module="xarray"
    )

    try:
        xr.set_options(
            use_new_combine_kwarg_defaults=True
        )
    except Exception:
        pass

    print("=" * 75)
    print("🚀 INITIALIZING STABLE CLIMAP-CMIP6 DATA EXTRACTION PIPELINE")
    print("=" * 75)

    print(
        "   Existing annual files will be skipped."
    )

    print(
        "   Existing raw ZIP years will be reused."
    )

    print(
        "   Only missing years will be downloaded."
    )

    print("=" * 75)


    # =================================================================
    # SCENARIOS
    # =================================================================

    for scenario_key, config in SCENARIO_CONFIGS.items():

        print(
            f"\n📂 SCENARIO GROUP ACTIVE: "
            f"{scenario_key.upper()}"
        )

        print("-" * 60)

        requested_years = config["years"]


        # =============================================================
        # VARIABLES
        # =============================================================

        for var_friendly, cds_var_name in VARIABLES.items():

            print(
                f"\n  🔄 Evaluating variable: "
                f"{var_friendly}"
            )

            # ---------------------------------------------------------
            # STEP 1
            # Check final annual files
            # ---------------------------------------------------------

            missing_years = []

            for year in requested_years:

                annual_filename = (
                    f"sievi_{var_friendly}_"
                    f"{scenario_key}_{year}.nc"
                )

                annual_path = os.path.join(
                    FINAL_OUTPUT_DIR,
                    annual_filename
                )

                if not os.path.exists(annual_path):
                    missing_years.append(year)

            # Everything already processed?
            if not missing_years:

                print(
                    f"    ✅ All requested years already exist."
                )

                continue

            print(
                f"    ℹ️ Final files still missing: "
                f"{missing_years}"
            )


            # ---------------------------------------------------------
            # STEP 2
            # Existing raw ZIP
            # ---------------------------------------------------------

            zip_filename = (
                f"raw_{var_friendly}_"
                f"{scenario_key}.zip"
            )

            zip_target_path = os.path.join(
                TEMP_ZIP_DIR,
                zip_filename
            )

            extraction_subfolder = os.path.join(
                TEMP_ZIP_DIR,
                f"extracted_{var_friendly}_{scenario_key}"
            )


            # ---------------------------------------------------------
            # STEP 3
            # Determine what years are already inside ZIP
            # ---------------------------------------------------------

            zip_years = get_years_from_zip(
                zip_target_path
            )

            if zip_years:

                print(
                    f"    📦 Existing raw ZIP contains years: "
                    f"{sorted(zip_years)}"
                )

            else:

                if os.path.exists(zip_target_path):

                    print(
                        "     ZIP exists but no valid years "
                        "could be detected."
                    )

                else:

                    print(
                        "    ℹ️ No existing raw ZIP found."
                    )


            # ---------------------------------------------------------
            # STEP 4
            # Calculate ONLY years missing from raw ZIP
            # ---------------------------------------------------------

            years_to_download = [
                year
                for year in missing_years
                if year not in zip_years
            ]


            if years_to_download:

                print(
                    f"    ⬇️ Years that must be downloaded: "
                    f"{years_to_download}"
                )

            else:

                print(
                    "    ✅ All missing final years are already "
                    "available inside the raw ZIP."
                )


            # =========================================================
            # STEP 5
            # DOWNLOAD ONLY MISSING YEARS
            # =========================================================

            if years_to_download:

                request_payload = {
                    "temporal_resolution": "daily",
                    "experiment": config["experiment"],
                    "variable": cds_var_name,
                    "model": MODEL_ID,
                    "month": ALL_MONTHS,
                    "year": years_to_download,
                    "format": "zip"
                }

                # -----------------------------------------------------
                # IMPORTANT:
                #
                # CDS returns a ZIP containing the requested years.
                #
                # If an old ZIP exists, download the missing years
                # into a temporary ZIP and MERGE the NetCDF files
                # into the existing raw ZIP.
                # -----------------------------------------------------

                download_zip = os.path.join(
                    TEMP_ZIP_DIR,
                    f"_download_{var_friendly}_"
                    f"{scenario_key}.zip"
                )

                try:

                    print(
                        f"    🌐 Requesting CDS for "
                        f"{years_to_download}..."
                    )

                    client.retrieve(
                        DATASET,
                        request_payload
                    ).download(download_zip)

                    print(
                        "    ✓ Download completed."
                    )


                    # -------------------------------------------------
                    # MERGE NEW ZIP INTO EXISTING ZIP
                    # -------------------------------------------------

                    if os.path.exists(zip_target_path):

                        print(
                            "    📦 Merging newly downloaded "
                            "years into existing raw ZIP..."
                        )

                        # Create temporary merged archive
                        merged_zip = os.path.join(
                            TEMP_ZIP_DIR,
                            f"_merged_{var_friendly}_"
                            f"{scenario_key}.zip"
                        )

                        with zipfile.ZipFile(
                            merged_zip,
                            "w",
                            compression=zipfile.ZIP_DEFLATED
                        ) as zout:

                            # Add old files
                            with zipfile.ZipFile(
                                zip_target_path,
                                "r"
                            ) as old_zip:

                                for item in old_zip.infolist():

                                    if item.is_dir():
                                        continue

                                    data = old_zip.read(
                                        item.filename
                                    )

                                    zout.writestr(
                                        item,
                                        data
                                    )


                            # Add newly downloaded files
                            with zipfile.ZipFile(
                                download_zip,
                                "r"
                            ) as new_zip:

                                for item in new_zip.infolist():

                                    if item.is_dir():
                                        continue

                                    # Avoid duplicate filenames
                                    existing_names = set(
                                        zout.namelist()
                                    )

                                    if item.filename in existing_names:
                                        print(
                                            f"      ⚠️ Skipping duplicate: "
                                            f"{item.filename}"
                                        )
                                        continue

                                    data = new_zip.read(
                                        item.filename
                                    )

                                    zout.writestr(
                                        item,
                                        data
                                    )

                        # Replace old archive
                        os.replace(
                            merged_zip,
                            zip_target_path
                        )

                        print(
                            "    ✓ Existing ZIP successfully "
                            "updated."
                        )

                    else:

                        # No previous ZIP:
                        # simply rename downloaded ZIP
                        os.replace(
                            download_zip,
                            zip_target_path
                        )

                        print(
                            "    ✓ New raw ZIP created."
                        )


                except Exception as e:

                    print(
                        f"    ❌ CDS download failed: {e}"
                    )

                    # Clean temporary download
                    if os.path.exists(download_zip):

                        try:
                            os.remove(download_zip)
                        except Exception:
                            pass

                    continue

                finally:

                    # Remove temporary downloaded ZIP
                    if os.path.exists(download_zip):

                        try:
                            os.remove(download_zip)
                        except Exception:
                            pass


            # =========================================================
            # STEP 6
            # EXTRACT THE COMPLETE RAW ZIP
            # =========================================================

            if not os.path.exists(zip_target_path):

                print(
                    "    ❌ No raw ZIP available for processing."
                )

                continue


            os.makedirs(
                extraction_subfolder,
                exist_ok=True
            )


            print(
                "    📂 Extracting raw ZIP..."
            )

            if not extract_zip(
                zip_target_path,
                extraction_subfolder
            ):

                continue


            # =========================================================
            # STEP 7
            # FIND ALL NETCDF FILES
            # =========================================================

            nc_files = find_nc_files(
                extraction_subfolder
            )

            if not nc_files:

                print(
                    "    ❌ No NetCDF files found "
                    "inside raw ZIP."
                )

                continue

            print(
                f"    ✓ Found {len(nc_files)} NetCDF files."
            )


            # =========================================================
            # STEP 8
            # OPEN MULTI-FILE DATASET
            # =========================================================

            try:

                print(
                    "    -> Reading global grid sequences "
                    "into xarray..."
                )

                with xr.open_mfdataset(
                    nc_files,
                    combine="by_coords",
                    parallel=False
                ) as ds:

                    # -------------------------------------------------
                    # DETECT LATITUDE DIMENSION
                    # -------------------------------------------------

                    if "Lat" in ds.dims:
                        lat_key = "Lat"

                    elif "lat" in ds.dims:
                        lat_key = "lat"

                    elif "latitude" in ds.dims:
                        lat_key = "latitude"

                    elif "y" in ds.dims:
                        lat_key = "y"

                    else:
                        raise ValueError(
                            "Could not identify latitude dimension."
                        )


                    # -------------------------------------------------
                    # DETECT LONGITUDE DIMENSION
                    # -------------------------------------------------

                    if "Lon" in ds.dims:
                        lon_key = "Lon"

                    elif "lon" in ds.dims:
                        lon_key = "lon"

                    elif "longitude" in ds.dims:
                        lon_key = "longitude"

                    elif "x" in ds.dims:
                        lon_key = "x"

                    else:
                        raise ValueError(
                            "Could not identify longitude dimension."
                        )


                    # -------------------------------------------------
                    # LATITUDE ORIENTATION
                    # -------------------------------------------------

                    first_lat = ds[lat_key].values[0]
                    last_lat = ds[lat_key].values[-1]

                    if first_lat > last_lat:

                        lat_slice = slice(
                            SIEVI_BBOX["lat_max"],
                            SIEVI_BBOX["lat_min"]
                        )

                    else:

                        lat_slice = slice(
                            SIEVI_BBOX["lat_min"],
                            SIEVI_BBOX["lat_max"]
                        )


                    # -------------------------------------------------
                    # SPATIAL CROP
                    # -------------------------------------------------

                    print(
                        "    -> Isolating spatial box "
                        "for Sievi..."
                    )

                    sievi_cropped_ds = ds.sel({

                        lat_key: lat_slice,

                        lon_key: slice(
                            SIEVI_BBOX["lon_min"],
                            SIEVI_BBOX["lon_max"]
                        )
                    })


                    # -------------------------------------------------
                    # ANNUAL SPLITTING
                    # -------------------------------------------------

                    print(
                        "    -> Splitting data into "
                        "annual files..."
                    )


                    for year, ds_year in (
                        sievi_cropped_ds.groupby("time.year")
                    ):

                        year_string = str(int(year))

                        # Only process requested years
                        if year_string not in requested_years:

                            continue


                        annual_filename = (
                            f"sievi_{var_friendly}_"
                            f"{scenario_key}_"
                            f"{year_string}.nc"
                        )

                        annual_target_path = os.path.join(
                            FINAL_OUTPUT_DIR,
                            annual_filename
                        )


                        # -------------------------------------------------
                        # SAFETY CHECK
                        # -------------------------------------------------

                        if os.path.exists(
                            annual_target_path
                        ):

                            print(
                                f"      [Skipped] "
                                f"{annual_filename} "
                                f"already exists."
                            )

                            continue


                        print(
                            f"      -> Processing "
                            f"{year_string}..."
                        )


                        try:

                            save_annual_netcdf(
                                ds_year,
                                annual_target_path
                            )

                            print(
                                f"      💾 Saved: "
                                f"{annual_filename}"
                            )

                        except Exception as e:

                            print(
                                f"      ❌ Failed writing "
                                f"{annual_filename}: {e}"
                            )

                            # Delete incomplete output
                            if os.path.exists(
                                annual_target_path
                            ):

                                try:
                                    os.remove(
                                        annual_target_path
                                    )
                                except Exception:
                                    pass


            except Exception as e:

                print(
                    f"    ❌ Failed to process "
                    f"component {var_friendly}: {e}"
                )

                continue


    # =================================================================
    # COMPLETE
    # =================================================================

    print("\n" + "=" * 75)
    print(
        "🏁 PIPELINE EXECUTION COMPLETELY FINISHED!"
    )
    print("=" * 75)


# =====================================================================
# RUN
# =====================================================================

if __name__ == "__main__":
    execute_stable_climate_pipeline()
