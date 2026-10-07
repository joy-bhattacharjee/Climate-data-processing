# script_prepare_penman_inputs_split.py
import os
import pandas as pd
import numpy as np

# =====================================================================
# CONFIGURATION
# =====================================================================
# Directory containing the outputs from your variable-wise compiler script
INPUT_DIR = r"C:\Users\bhattaj1\Desktop\Rewater\Climate_Data_&_Script\sievi_daily_time_series"
OBS_GRIDDED_MASTER = "observed_baseline_merged.csv"  # Your 1985-2014 clean gridded reference

os.chdir(INPUT_DIR)

# Define the timeframe used to calculate the historical systematic bias offsets
BASELINE_START = "1985-01-01"
BASELINE_END = "2014-12-31"

SCENARIOS = ["historical", "ssp245", "ssp585"]

def prepare_bias_corrected_scenarios():
    print("=" * 75)
    print("⚖️ INITIALIZING SPLIT-SCENARIO BIAS CORRECTION ENGINE")
    print("   Calibrating and Saving Separate Files Per Climate Pathway")
    print("=" * 75)
    
    # 1. Load your gridded ground-truth observations to calculate the training bias
    if not os.path.exists(OBS_GRIDDED_MASTER):
        print(f"❌ Error: Reference baseline file '{OBS_GRIDDED_MASTER}' missing. Cannot calibrate.")
        return
        
    df_obs = pd.read_csv(OBS_GRIDDED_MASTER)
    df_obs['date'] = pd.to_datetime(df_obs['date']).dt.strftime('%Y-%m-%d')
    
    # Extract observed historical means for calibration over the target window
    obs_mask = (df_obs['date'] >= BASELINE_START) & (df_obs['date'] <= BASELINE_END)
    obs_mean_tas  = df_obs[obs_mask]['temperature'].mean()  # Native Observed Mean
    obs_mean_tmax = df_obs[obs_mask]['temperature_max'].mean()
    obs_mean_tmin = df_obs[obs_mask]['temperature_min'].mean()
    obs_mean_pr   = df_obs[obs_mask]['precipitation'].mean()
    
    # Global calibration parameter placeholders (Trained strictly on the historical run)
    tas_offset, tmax_offset, tmin_offset, pr_scale_factor = 0.0, 0.0, 0.0, 1.0
    
    # -----------------------------------------------------------------
    # STEP A: FIRST PASS - CALCULATE SYSTEMATIC BIAS VIA HISTORICAL SCENARIO
    # -----------------------------------------------------------------
    print("\n⏳ Phase 1: Training calibration offsets using the 'historical' run...")
    hist_tas    = os.path.join(INPUT_DIR, f"sievi_daily_temperature_historical.csv")
    hist_tmax   = os.path.join(INPUT_DIR, f"sievi_daily_temp_max_historical.csv")
    hist_tmin   = os.path.join(INPUT_DIR, f"sievi_daily_temp_min_historical.csv")
    hist_precip = os.path.join(INPUT_DIR, f"sievi_daily_precipitation_historical.csv")
    
    if all(os.path.exists(f) for f in [hist_tas, hist_tmax, hist_tmin, hist_precip]):
        df_h_tas  = pd.read_csv(hist_tas)
        df_h_tmax = pd.read_csv(hist_tmax)
        df_h_tmin = pd.read_csv(hist_tmin)
        df_h_pr   = pd.read_csv(hist_precip)
        
        for df in [df_h_tas, df_h_tmax, df_h_tmin, df_h_pr]:
            df['date'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d')
            
        df_h_merged = df_h_tas.merge(df_h_tmax, on='date', how='inner')\
                              .merge(df_h_tmin, on='date', how='inner')\
                              .merge(df_h_pr, on='date', how='inner')
                              
        gcm_mask = (df_h_merged['date'] >= BASELINE_START) & (df_h_merged['date'] <= BASELINE_END)
        gcm_mean_tas  = df_h_merged[gcm_mask]['temperature'].mean()
        gcm_mean_tmax = df_h_merged[gcm_mask]['temp_max'].mean()
        gcm_mean_tmin = df_h_merged[gcm_mask]['temp_min'].mean()
        gcm_mean_pr   = df_h_merged[gcm_mask]['precipitation'].mean()
        
        # Calculate final delta/scaling properties
        tas_offset  = obs_mean_tas - gcm_mean_tas
        tmax_offset = obs_mean_tmax - gcm_mean_tmax
        tmin_offset = obs_mean_tmin - gcm_mean_tmin
        pr_scale_factor = obs_mean_pr / gcm_mean_pr if gcm_mean_pr > 0 else 1.0
        
        print(f"  📊 Calculated Calibration Metrics (Baseline {BASELINE_START} to {BASELINE_END}):")
        print(f"    -> Mean Temp Offset (tas): {tas_offset:+.3f} °C")
        print(f"    -> Max Temp Offset (tasmax): {tmax_offset:+.3f} °C")
        print(f"    -> Min Temp Offset (tasmin): {tmin_offset:+.3f} °C")
        print(f"    -> Precip Scale Factor:      {pr_scale_factor:.4f}")
    else:
        print("❌ Error: 'historical' scenario variable files missing. Cannot train bias parameters.")
        return

    # -----------------------------------------------------------------
    # STEP B: SECOND PASS - APPLY AND SAVE SCENARIOS INDIVIDUALLY
    # -----------------------------------------------------------------
    print("\n⏳ Phase 2: Applying calibration curves and exporting separate files...")
    for scenario in SCENARIOS:
        tas_file    = os.path.join(INPUT_DIR, f"sievi_daily_temperature_{scenario}.csv")
        tmax_file   = os.path.join(INPUT_DIR, f"sievi_daily_temp_max_{scenario}.csv")
        tmin_file   = os.path.join(INPUT_DIR, f"sievi_daily_temp_min_{scenario}.csv")
        precip_file = os.path.join(INPUT_DIR, f"sievi_daily_precipitation_{scenario}.csv")
        
        if not all(os.path.exists(f) for f in [tas_file, tmax_file, tmin_file, precip_file]):
            print(f"  ❌ Skipped Scenario: Missing parameter files for '{scenario}'.")
            continue
            
        # Load and align
        df_tas  = pd.read_csv(tas_file)
        df_tmax = pd.read_csv(tmax_file)
        df_tmin = pd.read_csv(tmin_file)
        df_pr   = pd.read_csv(precip_file)
        
        for df in [df_tas, df_tmax, df_tmin, df_pr]:
            df['date'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d')
            
        df_merged = df_tas.merge(df_tmax, on='date', how='inner')\
                           .merge(df_tmin, on='date', how='inner')\
                           .merge(df_pr, on='date', how='inner')
                           
        # Apply the trained calibration metrics
        df_merged['tas']    = df_merged['temperature'] + tas_offset
        df_merged['tasmax'] = df_merged['temp_max'] + tmax_offset
        df_merged['tasmin'] = df_merged['temp_min'] + tmin_offset
        df_merged['pr']     = df_merged['precipitation'] * pr_scale_factor
        
        # Enforce realistic boundaries
        df_merged['pr'] = np.clip(df_merged['pr'], 0.0, None)
        df_merged['scenario'] = scenario
        
        # Isolate clean column layout structures
        df_clean = df_merged[['date', 'scenario', 'tas', 'tasmax', 'tasmin', 'pr']].copy()
        
        # DYNAMIC OUTPUT SAVING: Generate separate individual files
        scenario_output_file = f"sievi_daily_bias_corrected_{scenario}.csv"
        df_clean.to_csv(scenario_output_file, index=False)
        print(f"  💾 Successfully Generated File: {scenario_output_file} ({len(df_clean)} rows written)")

    print("\n" + "=" * 75)
    print("🏁 PROCESS COMPLETE! Individual bias-corrected scenario files are safe on disk.")
    print("=" * 75)

if __name__ == "__main__":
    prepare_bias_corrected_scenarios()
