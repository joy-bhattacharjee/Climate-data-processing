# -*- coding: utf-8 -*-
"""
Created on Tue Aug 25 17:25:56 2026

@author: bhattaj1
"""

import os
import glob
import xarray as xr
import pandas as pd

# =====================================================================
# CONFIGURATION
# =====================================================================
# Directory containing your generated annual Sievi NetCDF files
NETCDF_DIR = r"C:\Users\bhattaj1\Desktop\Rewater\Climate_Data_&_Script\sievi_cropped_netcdf_ready"
OUTPUT_DIR = r"C:\Users\bhattaj1\Desktop\Rewater\Climate_Data_&_Script\sievi_daily_time_series"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Map friendly variable names to short variable keys inside the NetCDF metadata
VARIABLE_KEYS = {
    "temperature": "tas",
    "precipitation": "pr",
    "temp_max": "tasmax",
    "temp_min": "tasmin",
}

SCENARIOS = ["historical", "ssp245", "ssp585"]

# =====================================================================
# CORE PROCESSING ENGINE
# =====================================================================

def compile_variable_time_series():
    print("=" * 75)
    print("🚀 INITIALIZING VARIABLE-WISE CLIMATE TIME SERIES COMPILER")
    print("   Aggregating annual slices -> Converting Units -> Compiling Timelines")
    print("=" * 75)
    
    for scenario in SCENARIOS:
        print("\n" + "="*50)
        print(f"📂 SCENARIO TRACK ACTIVE: {scenario.upper()}")
        print("="*50)
        
        for var_friendly, nc_var_key in VARIABLE_KEYS.items():
            # Explicit filename query mapping based on scenario to prevent data intermingling
            search_pattern = os.path.join(NETCDF_DIR, f"sievi_{var_friendly}_{scenario}_*.nc")
            nc_files = sorted(glob.glob(search_pattern))
            
            # Existence condition: Check if the folder actually contains data for this scenario combo
            if not nc_files:
                print(f"  ❌ MESSAGE: NetCDF files for variable '{var_friendly}' under scenario '{scenario}' DO NOT EXIST in the folder. Skipping.")
                continue
                
            print(f"  🔄 Merging {len(nc_files)} annual chunks found for '{var_friendly}' under '{scenario}'...")
            
            try:
                # Open multi-file dataset with future-proofed layout conventions
                with xr.open_mfdataset(nc_files, combine='by_coords', data_vars='minimal', coords='minimal') as ds:
                    
                    # Dynamically resolve case-sensitive grid index dimension keys
                    lat_dim = next((d for d in ds.dims if d.lower() in ['lat', 'latitude', 'y']), None)
                    lon_dim = next((d for d in ds.dims if d.lower() in ['lon', 'longitude', 'x']), None)
                    time_dim = next((d for d in ds.dims if d.lower() in ['time', 'date', 't']), 'time')
                    
                    # Verify variable tracking keys match the internal NetCDF fields layout
                    actual_var = next((v for v in ds.data_vars if v.lower() == nc_var_key.lower()), None)
                    if not actual_var:
                        print(f"    ❌ Error: Variable key '{nc_var_key}' missing in file metadata. Skipping.")
                        continue
                    
                    # Extract spatial average to compress to a 1D coordinate timeline vector
                    spatial_mean = ds[actual_var].mean(dim=[lat_dim, lon_dim], skipna=True)
                    
                    # Convert only this point array to a Pandas Dataframe structure
                    df = spatial_mean.to_dataframe().reset_index()
                    
                    # Normalize time dimension stamps into string standard ISO profiles (YYYY-MM-DD)
                    df['date'] = pd.to_datetime(df[time_dim]).dt.strftime('%Y-%m-%d')
                    df.rename(columns={actual_var: 'value'}, inplace=True)
                    
                    # Eliminate duplicated overlapping boundary dates between sequential annual files
                    df = df.drop_duplicates(subset=['date']).sort_values(by='date')
                    
                    # =========================================================
                    # METEOROLOGICAL METRIC UNIT CONVERSIONS (EXPLICIT)
                    # =========================================================
                    # 1. Temperature Conversion (Kelvin -> Celsius)
                    # Targets 'temperature', 'temp_max', 'temp_min', or metadata keys 'tas', 'tasmax', 'tasmin'
                    is_temp = any(x in var_friendly.lower() or x in nc_var_key.lower() for x in ["tas", "temp"])
                    if is_temp and df['value'].max() > 150.0:
                        df['value'] = df['value'] - 273.15
                        unit_label = "Converted K → °C"
                    
                    # 2. Precipitation Flux Conversion (kg/m²/s -> mm/day)
                    # Multiplies by 86400 (seconds in a day) to yield exact daily depth
                    elif any(x in var_friendly.lower() or x in nc_var_key.lower() for x in ["pr", "precip"]) and df['value'].max() < 0.1:
                        df['value'] = df['value'] * 86400.0
                        unit_label = "Converted kg/m²/s → mm/day"
                    else:
                        unit_label = "Natively scaled"
                        
                    # Prepare and wrap the clean output data slice 
                    output_filename = f"sievi_daily_{var_friendly}_{scenario}.csv"
                    output_path = os.path.join(OUTPUT_DIR, output_filename)
                    
                    final_df = df[['date', 'value']].copy()
                    final_df.columns = ['date', var_friendly]
                    
                    final_df.to_csv(output_path, index=False)
                    print(f"    💾 Saved ({unit_label}): {output_filename} ({len(final_df)} rows logged)")
                    
            except Exception as e:
                print(f"    ❌ Error processing '{var_friendly}' under '{scenario}': {e}")
                continue

    print("\n" + "=" * 75)
    print("🏁 TIMELINE SEPARATION COMPLETED! All available normalized scenario tables are generated.")
    print("=" * 75)

if __name__ == "__main__":
    compile_variable_time_series()
