# -*- coding: utf-8 -*-
"""
Created on Mon Aug 10 14:12:35 2026

@author: bhattaj1
"""

import os
import requests
import pandas as pd
from bs4 import BeautifulSoup

# =====================================================================
# CONFIGURATION
# =====================================================================
# Your custom generated FMI portal observation link
FMI_PORTAL_URL = "https://fmiodata-timeseries-convert.fmi.fi/Ylivieska%20airfield:%201.1.1986%20-%2031.12.2025_6a27d950-7eb0-47f6-b44d-f7caa08c9141.html"

# Output daily timeline file target matching your pipeline
OUTPUT_CSV = "fmi_observed_daily_wind_speed_ylivieska.csv"

# =====================================================================
# EXTRACTION ENGINE
# =====================================================================

def parse_fmi_html_portal_stream():
    print(f"🚀 Contacting FMI Document Portal: {FMI_PORTAL_URL}...")
    
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    try:
        response = requests.get(FMI_PORTAL_URL, headers=headers, timeout=60)
        if response.status_code != 200:
            print(f"❌ Failed to reach file link. Server returned status: {response.status_code}")
            return
    except Exception as e:
        print(f"❌ Connection error: {e}")
        return

    print("✓ HTML file retrieved. Commencing table layout parsing...")
    soup = BeautifulSoup(response.content, 'html.parser')
    
    # 1. Target the raw observation text layout rows
    # FMI export text formats typically utilize structured grid table lines or <pre> rows
    raw_text = soup.get_text()
    lines = raw_text.split('\n')
    
    parsed_hourly_records = []
    
    print("⏳ Processing lines into structural text elements...")
    for line in lines:
        parts = line.strip().split()
        
        # Look specifically for row splits matching the station dump structure:
        # Index layout: ['Ylivieska', 'airfield', 'Year', 'Month', 'Day', 'Time', 'WindSpeed']
        if len(parts) >= 7 and parts[0] == "Ylivieska" and parts[1] == "airfield":
            try:
                year = parts[2]
                month = parts[3].zfill(2)
                day = parts[4].zfill(2)
                time_str = parts[5]
                wind_val = parts[6]
                
                # Filter out any text placeholders indicating data gaps or empty loops
                if wind_val.lower() == 'nan' or wind_val == '-':
                    continue
                    
                # Build an in-memory chronological timestamp mapping vector
                dt_stamp = pd.to_datetime(f"{year}-{month}-{day} {time_str}", format="%Y-%m-%d %H:%M")
                
                parsed_hourly_records.append({
                    "timestamp": dt_stamp,
                    "ws": float(wind_val)
                })
            except Exception:
                continue # Skip corrupt lines or header description structures natively
                
    if not parsed_hourly_records:
        print("⚠️ Warning: Standard whitespace string matching failed. Retrying alternate table rows parsing...")
        # Fallback loop targeting explicit HTML <tr> tables if layout rendered inside a table grid
        for row in soup.find_all('tr'):
            tds = [td.get_text().strip() for td in row.find_all('td')]
            if len(tds) >= 6 and 'Ylivieska' in tds[0]:
                try:
                    parsed_hourly_records.append({
                        "timestamp": pd.to_datetime(f"{tds[1]}-{tds[2].zfill(2)}-{tds[3].zfill(2)} {tds[4]}"),
                        "ws": float(tds[5])
                    })
                except Exception:
                    continue

    if not parsed_hourly_records:
        print("❌ Error: No text structures could be sliced. Please ensure the link is active and valid.")
        return

    # =====================================================================
    # DATA COMPILATION & TEMPORAL RESAMPLING
    # =====================================================================
    print(f"✓ Sliced {len(parsed_hourly_records)} hourly wind speed records.")
    print("⏳ Resampling high-resolution values into daily meteorological means...")
    
    df_hourly = pd.DataFrame(parsed_hourly_records)
    df_hourly.set_index("timestamp", inplace=True)
    
    # Compress 24 hourly logs into clean daily average blocks matching CMIP6 spacing rules
    df_daily = df_hourly["ws"].resample("1D").mean().reset_index()
    
    # Shape date values to standardized format: YYYY-MM-DD
    df_daily["date"] = df_daily["timestamp"].dt.strftime("%Y-%m-%d")
    df_daily.rename(columns={"ws": "wind_speed"}, inplace=True)
    
    # Filter rows to match the WMO historical climate baseline framework (1991–2020)
    df_final = df_daily[(df_daily['date'] >= '1991-01-01') & (df_daily['date'] <= '2020-12-31')].copy()
    df_final = df_final[["date", "wind_speed"]].dropna().sort_values(by="date")
    
    # Write file to disk
    df_final.to_csv(OUTPUT_CSV, index=False)
    
    print("="*70)
    print(f"💾 ARCHIVE PARSING SUCCESSFUL! Generated: {OUTPUT_CSV}")
    print(f"Unified table contains {len(df_final)} matching observation days.")
    print("="*70)

if __name__ == "__main__":
    parse_fmi_html_portal_stream()
