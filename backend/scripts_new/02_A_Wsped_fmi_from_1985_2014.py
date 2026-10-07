# -*- coding: utf-8 -*-
"""
Created on Fri Aug 14 14:01:07 2026

@author: bhattaj1
"""

import os
import pandas as pd
import numpy as np

# =====================================================================
# CONFIGURATION
# =====================================================================
os.chdir(r"C:\Users\bhattaj1\Desktop\Rewater\Climate_Data_&_Script\gridded_data")
HOURLY_STATION_FILE = "fmi_observed_daily_wind_speed_ylivieska.csv" 
STATION_OUTPUT_FILE = "sievi_gridded_wind_speed_daily.csv"
END_TARGET_DATE = "2014-12-31"

def process_station_explicit_columns():
    print("="*75)
    print("🌬️ STEP 2: AGGREGATING MULTI-COLUMN STATION WIND DATA TO DAILY MEAN")
    print("="*75)
    
    if not os.path.exists(HOURLY_STATION_FILE):
        print(f"❌ Error: Raw file '{HOURLY_STATION_FILE}' not found. Please check your path.")
        return
        
    # 1. Load the raw scraped dataframe
    df = pd.read_csv(HOURLY_STATION_FILE)
    print(f"Successfully loaded file containing columns: {list(df.columns)}")
    
    # Clean up column names from any accidental whitespace
    df.columns = [c.strip() for c in df.columns]
    
    # 2. Map the explicit columns into a unified ISO string date layout (YYYY-MM-DD)
    # This ignores sub-daily hours/minutes since we are computing a daily aggregate
    try:
        df['date_str'] = (
            df['Year'].astype(str) + '-' + 
            df['Month'].astype(str).str.zfill(2) + '-' + 
            df['Day'].astype(str).str.zfill(2)
        )
    except KeyError as e:
        print(f"❌ Column Mapping Error: Could not locate columns. Check spacing. Details: {e}")
        return

    # Handle numeric formatting for the Wind Speed target column
    # Cast potential text flags ('NaN' or '-') cleanly into actual numerical floats
    df['Wind speed [m/s]'] = pd.to_numeric(df['Wind speed [m/s]'].astype(str).str.replace(',', '.'), errors='coerce')
    
    # 3. Aggregate all sub-daily rows to compute a single true daily mean (m/s)
    print("-> Grouping values to calculate daily mean arrays...")
    daily_aggregated = df.groupby('date_str')['Wind speed [m/s]'].mean().reset_index()
    daily_aggregated.columns = ['date', 'wind_speed']
    
    # 4. Determine boundaries and establish complete timeline checklist matrix
    earliest_date_str = daily_aggregated['date'].min()
    print(f"Detected Historical Data Sequence Timeline:")
    print(f"  -> Records available from: {earliest_date_str}")
    print(f"  -> Capping Target End:      {END_TARGET_DATE}")
    
    # Construct a perfect consecutive calendar array to intercept missing dates
    perfect_calendar = pd.date_range(start=earliest_date_str, end=END_TARGET_DATE, freq='D').strftime('%Y-%m-%d')
    
    # Merge daily measurements with the continuous calendar checklist framework
    df_timeline_checked = pd.DataFrame({'date': perfect_calendar}).merge(daily_aggregated, on='date', how='left')
    
    # 5. Missing metrics validation checks
    missing_days_count = df_timeline_checked['wind_speed'].isna().sum()
    total_timeline_days = len(df_timeline_checked)
    
    print(f"\nStation Timeline Integrity Stats ({earliest_date_str} to {END_TARGET_DATE}):")
    print(f"  Total Expected Grid Days: {total_timeline_days} rows")
    
    if missing_days_count > 0:
        print(f"  ⚠️ Missing Value Warning: Found {missing_days_count} missing days in wind monitoring records.")
        # Apply standard meteorological linear interpolation to clear out missing days
        df_timeline_checked['wind_speed'] = df_timeline_checked['wind_speed'].interpolate(method='linear', limit_direction='both')
        print("  -> Fixed: Applied localized linear gap-filling to complete the wind vector.")
    else:
        print("  ✓ Perfect station sequence! Zero data dropouts found across the years.")
        
    # 6. Save output file
    df_timeline_checked.to_csv(STATION_OUTPUT_FILE, index=False)
    print(f"\n💾 STATION PROCESS COMPLETE! Generated file: {STATION_OUTPUT_FILE}")
    print("="*75)

if __name__ == "__main__":
    process_station_explicit_columns()
