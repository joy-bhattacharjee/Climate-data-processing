# -*- coding: utf-8 -*-
"""
Export hourly climate/PET columns from final Sievi hourly CSV/Excel files
into simulation-ready dt_*.txt files.

Expected input columns:

timestamp
scenario
temperature_celsius
relative_humidity_percent
precipitation_mm
wind_speed_m_s
wind_speed_2m_m_s
solar_radiation_w_m2
solar_radiation_mj_m2_h
net_shortwave_radiation_mj_m2_h
longwave_radiation_rnl_mj_m2_h
PET_mm_h

Output format example:

0    96
1    94
2    93
3    94
4    93

That means:
    index<TAB>value

Output folders:
    historical/
    ssp245/
    ssp585/
"""

import os
import glob
import pandas as pd
from pathlib import Path


# =============================================================================
# CONFIGURATION
# =============================================================================

BASE_DIR = r"C:\Users\bhattaj1\Desktop\Rewater\Climate_Data_&_Script\for_generating_dt_files"

# Main output directory.
# Scenario folders will be created inside this directory.
OUTPUT_DIR = BASE_DIR

SCENARIOS = [
    "historical",
    "ssp245",
    "ssp585"
]

# Output txt format
WRITE_HEADER = False
WRITE_INDEX = True
NA_REPRESENTATION = "NaN"


# =============================================================================
# VARIABLE MAPPING
# =============================================================================
#
# Output file name -> possible input column names
# =============================================================================

COLUMN_MAPPING = {
    "dt_precip_01.txt": [
        "precipitation_mm",
        "Precipitation_mm",
        "precipitation",
        "pr",
        "rainfall_mm",
        "rain_mm"
    ],

    "dt_temp_01.txt": [
        "temperature_celsius",
        "Temperature_C",
        "temperature_c",
        "temperature",
        "tas",
        "temp"
    ],

    "dt_wind_01.txt": [
        # Main hourly wind speed
        "wind_speed_m_s",
        "Wind_Speed_m_s",
        "wind",
        "wind_speed",

        # Fallback if needed
        "wind_speed_2m_m_s"
    ],

    "dt_radiat_short_01.txt": [
        # Incoming shortwave radiation in MJ/m2/h
        "solar_radiation_mj_m2_h",
        "Shortwave_Radiation_MJ_m2",
        "shortwave_radiation_mj_m2_h",
        "rsds_mj_m2_h",

        # Fallback
        "net_shortwave_radiation_mj_m2_h"
    ],

    "dt_radiat_long_01.txt": [
        "longwave_radiation_rnl_mj_m2_h",
        "Longwave_Radiation_MJ_m2_h",
        "longwave_radiation_mj_m2_h",
        "rlds_mj_m2_h",
        "longwave"
    ],

    "dt_humid_01.txt": [
        # RH is already RH * 100, meaning percent
        "relative_humidity_percent",
        "Relative_Humidity_percent",
        "relative_humidity",
        "hurs",
        "rh",
        "humidity"
    ],

    "dt_pet_01.txt": [
        "PET_mm_h",
        "pet_mm_h",
        "pet",
        "ET0_mm_h",
        "et0"
    ]
}


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def normalize_column_name(name):
    """
    Normalize names for flexible matching.
    """

    return (
        str(name)
        .strip()
        .lower()
        .replace(" ", "_")
        .replace("-", "_")
        .replace("/", "_")
        .replace("\\", "_")
        .replace("(", "")
        .replace(")", "")
        .replace("[", "")
        .replace("]", "")
    )


def find_matching_column(df, possible_names):
    """
    Find first matching column from possible names.
    """

    normalized_df_columns = {
        normalize_column_name(col): col
        for col in df.columns
    }

    for name in possible_names:

        normalized_name = normalize_column_name(name)

        if normalized_name in normalized_df_columns:
            return normalized_df_columns[normalized_name]

    return None


def read_input_file(file_path):
    """
    Read CSV or Excel file.
    """

    file_path = Path(file_path)
    suffix = file_path.suffix.lower()

    if suffix == ".csv":

        return pd.read_csv(file_path)

    elif suffix in [".xlsx", ".xls"]:

        return pd.read_excel(file_path)

    else:

        raise ValueError(
            f"Unsupported file type: {file_path}"
        )


def identify_scenario_from_file_or_column(df, file_path):
    """
    Identify scenario using:
        1. scenario column, if available
        2. filename, if it contains historical, ssp245, or ssp585
        3. parent folder name, if it contains scenario name
    """

    file_path = Path(file_path)

    # ---------------------------------------------------------
    # 1. Use scenario column if available
    # ---------------------------------------------------------

    scenario_col = find_matching_column(
        df,
        [
            "scenario",
            "Scenario",
            "scen",
            "experiment"
        ]
    )

    if scenario_col is not None:

        scenario_values = (
            df[scenario_col]
            .dropna()
            .astype(str)
            .str.lower()
            .str.strip()
            .unique()
        )

        for scenario in SCENARIOS:

            if scenario.lower() in scenario_values:
                return scenario

    # ---------------------------------------------------------
    # 2. Use filename
    # ---------------------------------------------------------

    file_name_lower = file_path.name.lower()

    for scenario in SCENARIOS:

        if scenario.lower() in file_name_lower:
            return scenario

    # ---------------------------------------------------------
    # 3. Use parent folder name
    # ---------------------------------------------------------

    parent_name_lower = file_path.parent.name.lower()

    for scenario in SCENARIOS:

        if scenario.lower() in parent_name_lower:
            return scenario

    return None


def clean_numeric_series(series):
    """
    Convert a column to numeric.
    """

    return pd.to_numeric(
        series,
        errors="coerce"
    )


def export_scenario_file(input_file_path):
    """
    Export all dt_*.txt files from one hourly scenario file.
    """

    input_file_path = Path(input_file_path)

    print()
    print("--------------------------------------------------")
    print(f"Reading file: {input_file_path}")
    print("--------------------------------------------------")

    df = read_input_file(input_file_path)

    print("Columns found:")

    for col in df.columns:
        print(f"  - {col}")

    # ---------------------------------------------------------
    # Identify scenario
    # ---------------------------------------------------------

    scenario = identify_scenario_from_file_or_column(
        df,
        input_file_path
    )

    if scenario is None:

        print()
        print("WARNING: Could not identify scenario for file:")
        print(input_file_path)
        print("This file will be skipped.")
        return 0

    print()
    print(f"Identified scenario: {scenario}")

    # ---------------------------------------------------------
    # If scenario column exists, keep only rows for this scenario
    # ---------------------------------------------------------

    scenario_col = find_matching_column(
        df,
        [
            "scenario",
            "Scenario",
            "scen",
            "experiment"
        ]
    )

    if scenario_col is not None:

        df = df[
            df[scenario_col]
            .astype(str)
            .str.lower()
            .str.strip()
            == scenario.lower()
        ].copy()

    # ---------------------------------------------------------
    # Sort by timestamp, if available
    # ---------------------------------------------------------

    timestamp_col = find_matching_column(
        df,
        [
            "timestamp",
            "time",
            "date",
            "datetime"
        ]
    )

    if timestamp_col is not None:

        df[timestamp_col] = pd.to_datetime(
            df[timestamp_col],
            errors="coerce"
        )

        df = df.sort_values(
            timestamp_col
        ).reset_index(
            drop=True
        )

    else:

        df = df.reset_index(
            drop=True
        )

    # ---------------------------------------------------------
    # Create scenario output folder
    # ---------------------------------------------------------

    scenario_output_dir = Path(OUTPUT_DIR) / scenario

    scenario_output_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    print(f"Output folder: {scenario_output_dir}")

    created_files = 0

    # ---------------------------------------------------------
    # Export variables
    # ---------------------------------------------------------

    for output_txt_name, possible_input_columns in COLUMN_MAPPING.items():

        matched_column = find_matching_column(
            df,
            possible_input_columns
        )

        if matched_column is None:

            print()
            print(f"WARNING: Could not find column for {output_txt_name}")
            print("Checked possible input column names:")

            for name in possible_input_columns:
                print(f"  - {name}")

            continue

        values = clean_numeric_series(
            df[matched_column]
        )

        # Important:
        # Reset index so txt file starts from 0, 1, 2, 3...
        values = values.reset_index(
            drop=True
        )

        output_txt_path = scenario_output_dir / output_txt_name

        values.to_csv(
            output_txt_path,
            sep="\t",
            header=WRITE_HEADER,
            index=WRITE_INDEX,
            na_rep=NA_REPRESENTATION
        )

        created_files += 1

        print(
            f"  ✓ Created {output_txt_name} "
            f"from column '{matched_column}' "
            f"with {len(values):,} values"
        )

    return created_files


# =============================================================================
# MAIN FUNCTION
# =============================================================================

def export_hourly_climate_files():

    base_path = Path(BASE_DIR)

    if not base_path.exists():

        raise FileNotFoundError(
            f"BASE_DIR does not exist:\n{BASE_DIR}"
        )

    print()
    print("==================================================")
    print(" EXPORTING HOURLY CLIMATE FILES FOR SIMULATION")
    print("==================================================")
    print(f"Base directory:   {BASE_DIR}")
    print(f"Output directory: {OUTPUT_DIR}")
    print("==================================================")

    # ---------------------------------------------------------
    # Search recursively for CSV and Excel files
    # ---------------------------------------------------------

    input_files = []

    input_files.extend(
        glob.glob(
            str(base_path / "**" / "*.csv"),
            recursive=True
        )
    )

    input_files.extend(
        glob.glob(
            str(base_path / "**" / "*.xlsx"),
            recursive=True
        )
    )

    input_files.extend(
        glob.glob(
            str(base_path / "**" / "*.xls"),
            recursive=True
        )
    )

    # ---------------------------------------------------------
    # Exclude temporary Excel files
    # ---------------------------------------------------------

    input_files = [
        file_path
        for file_path in input_files
        if not Path(file_path).name.startswith("~$")
    ]

    if not input_files:

        print()
        print("No CSV or Excel files found.")
        return

    print()
    print(f"Found {len(input_files)} input file(s).")

    total_created = 0

    for input_file_path in input_files:

        try:

            total_created += export_scenario_file(
                input_file_path
            )

        except Exception as e:

            print()
            print("ERROR processing file:")
            print(input_file_path)
            print(e)

    print()
    print("==================================================")
    print(" EXPORT COMPLETE")
    print("==================================================")
    print(f"Total text files generated: {total_created}")
    print("==================================================")


# =============================================================================
# RUN SCRIPT
# =============================================================================

if __name__ == "__main__":

    export_hourly_climate_files()
