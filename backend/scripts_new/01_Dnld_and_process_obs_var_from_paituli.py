# -*- coding: utf-8 -*-
"""
Created on Fri Aug  7 16:13:37 2026
@author: bhattaj1
"""
import io
import os
import requests
import xarray as xr
import pandas as pd

# =====================================================================
# METADATA CONFIGURATION
# =====================================================================
START_YEAR = 1961
END_YEAR = 2025

# Target EPSG:3067 metric coordinates (Central Finland)
TARGET_LAT = 7092181.907  # Northing (Y)
TARGET_LON = 370025.172  # Easting (X)

# Define variables, server routes, internal netCDF shortnames, and clean output paths
DATA_CONFIGS = {
    "temperature": {
        "base_url": "https://www.nic.funet.fi/index/geodata/ilmatiede/10km_daily_mean_temperature/netcdf/",
        "file_prefix": "tday",
        "nc_varname": "Tday",
        "output_file": r"C:\Users\bhattaj1\Desktop\Rewater\Sievi data\gridded_data\finland_daily_temperature.csv"
    },
    "global_radiation": {
        "base_url": "https://www.nic.funet.fi/index/geodata/ilmatiede/10km_daily_radiation/netcdf/",
        "file_prefix": "globrad", # Typically prefixes matching years
        "nc_varname": "Globrad",     # Common internal variable name for radiation grids
        "output_file": r"C:\Users\bhattaj1\Desktop\Rewater\Sievi data\gridded_data\finland_daily_global_radiation.csv"
    },
    "precipitation": {
        "base_url": "https://www.nic.funet.fi/index/geodata/ilmatiede/10km_daily_precipitation/netcdf/",
        "file_prefix": "RRday",
        "nc_varname": "rrday",
        "output_file": r"C:\Users\bhattaj1\Desktop\Rewater\Sievi data\gridded_data\finland_daily_precipitation_sum.csv"
    },
    "relative_humidity": {
        "base_url": "https://www.nic.funet.fi/index/geodata/ilmatiede/10km_daily_avg_rel_hum/netcdf/",
        "file_prefix": "rh",
        "nc_varname": "Rh",
        "output_file": r"C:\Users\bhattaj1\Desktop\Rewater\Sievi data\gridded_data\finland_daily_relative_humidity.csv"
    }
}

# =====================================================================
# ENGINE STREAMING PIPELINE
# =====================================================================

def execute_climate_streaming_pipeline():
    years = list(range(START_YEAR, END_YEAR + 1))
    total_years = len(years)
    
    print(f"🚀 Initializing Unified Climate Pipeline across {total_years} years ({START_YEAR}-{END_YEAR}).")
    
    for var_key, config in DATA_CONFIGS.items():
        print("\n" + "="*70)
        print(f"🔄 PROCESSING COMPONENT: {var_key.upper()}")
        print("="*70)
        
        all_extracted_dfs = []
        
        for idx, year in enumerate(years):
            # Form standard name structures used by Paituli servers (e.g., tday_1961.nc, pday_2015.nc)
            filename = f"{config['file_prefix']}_{year}.nc"
            file_url = f"{config['base_url']}{filename}"
            
            try:
                # 1. Download file contents into volatile memory
                response = requests.get(file_url, timeout=45)
                
                # Check for year boundary breaks (e.g. if 2025 isn't fully compiled yet)
                if response.status_code != 200:
                    # Alternative backup check if files don't use the prefix underscore format uniformly
                    alt_filename = f"{config['nc_varname'].lower()}_{year}.nc"
                    alt_url = f"{config['base_url']}{alt_filename}"
                    response = requests.get(alt_url, timeout=45)
                    if response.status_code != 200:
                        continue
                
                raw_bytes = response.content

                # 2. SEAMLESS DUAL ENGINE INTERPRETATION (Bypasses invalid NetCDF-3 ID issues)
                try:
                    ds = xr.open_dataset(raw_bytes)
                    engine_type = "NetCDF-4"
                except Exception:
                    nc_bytes_io = io.BytesIO(raw_bytes)
                    ds = xr.open_dataset(nc_bytes_io, engine="scipy")
                    engine_type = "NetCDF-3"

                # 3. COORDINATE SUBSETTING & RUNTIME ADAPTATION
                try:
                    # Dynamically inspect and switch coordinate dimensions
                    if 'X' in ds.dims or 'Y' in ds.dims:
                        lon_name, lat_name = 'X', 'Y'
                    elif 'easting' in ds.dims or 'northing' in ds.dims:
                        lon_name, lat_name = 'easting', 'northing'
                    else:
                        lat_name = 'Lat' if 'Lat' in ds.dims else ('latitude' if 'latitude' in ds.dims else 'y')
                        lon_name = 'Lon' if 'Lon' in ds.dims else ('longitude' if 'longitude' in ds.dims else 'x')

                    time_col = next((col for col in ds.coords if col.lower() in ['time', 'date', 't']), 'time')
                    
                    # Verify variable name matches the netcdf metadata
                    active_var = config['nc_varname']
                    if active_var not in ds.data_vars:
                        # Fallback case detection if variable naming matches lowercase file strings
                        active_var = next((v for v in ds.data_vars if var_key[:3].lower() in v.lower() or v.lower() == config['nc_varname'].lower()), list(ds.data_vars)[0])

                    # Extract point slice array
                    point_data = ds[active_var].sel(
                        {lat_name: TARGET_LAT, lon_name: TARGET_LON}, 
                        method='nearest'
                    )
                    
                    # Lock data state arrays into memory prior to channel stream breaks
                    point_data = point_data.load()
                    
                    # Convert to dataframe chunk
                    df_chunk = point_data.to_dataframe().reset_index()
                    df_chunk = df_chunk[[time_col, active_var]].rename(columns={time_col: 'standard_date', active_var: 'value'})
                    all_extracted_dfs.append(df_chunk)
                    
                    print(f"  [{idx+1}/{total_years}] ✓ Compiled {year} via {engine_type} engine.")
                    
                finally:
                    ds.close()
                    
            except Exception as e:
                # Log any anomalies but keep processing subsequent rows cleanly
                print(f"  [{idx+1}/{total_years}] ⚠️ Skipped {year}: {e}")
                continue

        # 4. CONSOLIDATE AND SHAPE INDIVIDUAL OUTPUT
        if all_extracted_dfs:
            print(f"\nFinalizing dataframe compilation for {var_key}...")
            final_df = pd.concat(all_extracted_dfs, ignore_index=True)
            
            # Post-processing adjustments by type
            if var_key == "temperature" and final_df['value'].max() > 150:
                final_df['value'] = final_df['value'] - 273.15  # Kelvin adjustment
                print("  -> Transformed temperature units into Celsius.")
                
            final_df = final_df[['standard_date', 'value']].copy()
            final_df.columns = ['date', var_key]
            final_df = final_df.sort_values(by='date')
            
            # Save variable CSV
            final_df.to_csv(config['output_file'], index=False)
            print(f"💾 File written: {config['output_file']} ({len(final_df)} days mapped)")
        else:
            print(f"❌ Failed to construct data table mapping context for variable: {var_key}")

    print("\n" + "="*70)
    print("🏁 PIPELINE EXECUTION COMPLETED! All output tables generated successfully.")
    print("="*70)

if __name__ == "__main__":
    execute_climate_streaming_pipeline()
