# -*- coding: utf-8 -*-
"""
Created on Tue Sep  1 14:49:25 2026

@author: bhattaj1
"""

# -*- coding: utf-8 -*-
"""
Created on Fri Aug 14 14:01:07 2026

@author: bhattaj1
"""

import os
import pandas as pd
import numpy as np

# Configuration mapping file sources to clean outputs
GRIDDED_FILES = {
    "temperature": r"C:\Users\bhattaj1\Desktop\Rewater\Climate_Data_&_Script\gridded_data\finland_daily_temperature.csv",
    "precipitation": r"C:\Users\bhattaj1\Desktop\Rewater\Climate_Data_&_Script\gridded_data\finland_daily_precipitation_sum.csv",
    "radiation": r"C:\Users\bhattaj1\Desktop\Rewater\Climate_Data_&_Script\gridded_data\finland_daily_global_radiation.csv",
    "humidity": r"C:\Users\bhattaj1\Desktop\Rewater\Climate_Data_&_Script\gridded_data\finland_daily_relative_humidity.csv"
}

TARGET_START = "1985-01-01"
TARGET_END = "2014-12-31"

def process_gridded_observations():
    print("="*75)
    print("🌍 STEP 1: PROCESSING REGIONAL GRIDDED HISTORICAL OBSERVATIONS")
    print("="*75)
    
    # Construct a perfect master calendar timeline to catch hidden missing dates
    perfect_calendar = pd.date_range(start=TARGET_START, end=TARGET_END, freq='D')
    perfect_dates = perfect_calendar.strftime('%Y-%m-%d')
    
    for var_name, file_path in GRIDDED_FILES.items():
        print(f"\nEvaluating: {var_name.upper()} Source: {file_path}")
        
        if not os.path.exists(file_path):
            print(f"  ❌ Error: Source file '{file_path}' not found. Skipping.")
            continue
            
        # Load and normalize date formats
        df = pd.read_csv(file_path)
        df['date'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d')
        
        # Filter strictly to the 1985-2014 target climatological timeline window
        df_filtered = df[(df['date'] >= TARGET_START) & (df['date'] <= TARGET_END)].copy()
        
        # Merge with perfect calendar to see if the file is physically missing rows/days
        df_checked = pd.DataFrame({'date': perfect_dates}).merge(df_filtered, on='date', how='left')
        
        # Count explicit missing/NaN rows in the target metric column
        val_column = [c for c in df_checked.columns if c != 'date'][0]
        missing_count = df_checked[val_column].isna().sum()
        total_rows = len(df_checked)
        
        print(f"  Total Expected Days: {total_rows} | Logged Values: {df_checked[val_column].count()}")
        
        if missing_count > 0:
            print(f"  ⚠️ Warning: Found {missing_count} missing daily values!")
            # Linearly interpolate missing blocks (meteorological standard for tiny gaps)
            df_checked[val_column] = df_checked[val_column].interpolate(method='linear')
            print(f"  -> Fixed: Missing indices filled via linear path interpolation optimization.")
        else:
            print("  ✓ Perfect sequence validation! Zero missing records detected.")
        
        # Unit conversions before saving:
        # - radiation: divide by 1000
        # - humidity: divide by 100
        if var_name == "radiation":
            df_checked[val_column] = df_checked[val_column].astype(float) / 1000.0
            print("  🔧 Conversion applied: radiation values divided by 1000.")
        elif var_name == "humidity":
            df_checked[val_column] = df_checked[val_column].astype(float) / 100.0
            print("  🔧 Conversion applied: relative humidity values divided by 100.")
            
        # Save output variable file
        os.chdir(r"C:\Users\bhattaj1\Desktop\Rewater\Climate_Data_&_Script\gridded_data")
        out_name = f"sievi_gridded_{var_name}_1985_2014.csv"
        df_checked.to_csv(out_name, index=False)
        print(f"  💾 File Written: {out_name}")

if __name__ == "__main__":
    process_gridded_observations()
