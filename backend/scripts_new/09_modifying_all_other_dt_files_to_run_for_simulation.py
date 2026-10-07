# -*- coding: utf-8 -*-
"""
Created on Tue Oct  6 18:19:27 2026

@author: bhattaj1
"""

# -*- coding: utf-8 -*-
"""
Modify selected dt_*.txt files so they match the length of the climate
reference time series.

Only files listed in FILES_TO_MODIFY are changed.

The following 7 climate reference files are never modified:

    dt_precip_01.txt
    dt_humid_01.txt
    dt_pet_01.txt
    dt_radiat_long_01.txt
    dt_radiat_short_01.txt
    dt_temp_01.txt
    dt_wind_01.txt

Special rules:

1. dt_draincontrol*.txt
   May 1 00:00 to September 30 23:00 -> value = -2
   Other periods are extended using previous/last value.

2. dt_rrotdepths*.txt
   May 1 00:00 to September 30 23:00 -> seasonal root-depth pattern copied
   across the full time series.

3. Other selected files in FILES_TO_MODIFY
   Extended using previous/last row value.

Output format:
    index<TAB>value
"""

import glob
import numpy as np
import pandas as pd
from pathlib import Path


# =============================================================================
# USER SETTINGS
# =============================================================================

BASE_DIR = Path(
    r"C:\Users\bhattaj1\Desktop\Rewater\Climate_Data_&_Script\for_generating_dt_files\ready_to_run"
)

SCENARIOS = [
    "historical",
    "ssp245",
    "ssp585"
]

# -------------------------------------------------------------------------
# IMPORTANT:
# Set the correct first year of each scenario.
#
# The script assumes timestep 0 = January 1 00:00 of this year.
# -------------------------------------------------------------------------

START_YEAR_BY_SCENARIO = {
    "historical": 1985,
    "ssp245": 2015,
    "ssp585": 2015
}

# -------------------------------------------------------------------------
# These 7 files define the target length.
# They will NOT be modified.
# -------------------------------------------------------------------------

REFERENCE_CLIMATE_FILES = [
    "dt_precip_01.txt",
    "dt_humid_01.txt",
    "dt_pet_01.txt",
    "dt_radiat_long_01.txt",
    "dt_radiat_short_01.txt",
    "dt_temp_01.txt",
    "dt_wind_01.txt"
]

PROTECTED_CLIMATE_FILES = set(REFERENCE_CLIMATE_FILES)

# -------------------------------------------------------------------------
# ONLY these files will be modified.
#
# Add here only the files from your images.
#
# Example names are included below. Remove names that you do not have and
# add the exact names from your folder/images.
# -------------------------------------------------------------------------

FILES_TO_MODIFY = [
    "dt_draincontrol_01.txt",
    "dt_rootdepths_01.txt",
    "dt_eroshydr_01.txt",
    "dt_erosrain_01.txt",
    "dt_gridsavepnts_01.txt",
    "dt_macropmult_01.txt",
    "dt_mann_01.txt",
    "dt_overflowthr_01.txt",
    "dt_solutes_depos_01.txt",
    "dt_solutes_fertil_01.txt",
    "dt_temp_soil_bottom_01.txt"  

    # Add other selected dt files from your images here, for example:
    # "dt_irrigation_01.txt",
    # "dt_lai_01.txt",
    # "dt_crop_01.txt",
    # "dt_snow_01.txt",
    # "dt_boundary_01.txt",
]

# Seasonal period
SEASON_START_MONTH = 5
SEASON_START_DAY = 1
SEASON_START_HOUR = 0

SEASON_END_MONTH = 9
SEASON_END_DAY = 30
SEASON_END_HOUR = 23

DRAINCONTROL_SEASON_VALUE = -2.0

CREATE_BACKUP = True
BACKUP_SUFFIX = ".backup_before_length_fix"


# =============================================================================
# FILE READ/WRITE FUNCTIONS
# =============================================================================

def read_dt_file(file_path):
    """
    Read dt file.

    Supports:
        index<TAB>value
    or:
        value
    """

    file_path = Path(file_path)

    df = pd.read_csv(
        file_path,
        sep=r"\s+|\t+",
        engine="python",
        header=None
    )

    if df.shape[1] == 1:
        values = pd.to_numeric(
            df.iloc[:, 0],
            errors="coerce"
        )
    else:
        values = pd.to_numeric(
            df.iloc[:, 1],
            errors="coerce"
        )

    return values.reset_index(drop=True)


def write_dt_file(file_path, values):
    """
    Write dt file as:

        index<TAB>value
    """

    output = pd.DataFrame({
        "index": np.arange(len(values), dtype=int),
        "value": values
    })

    output.to_csv(
        file_path,
        sep="\t",
        header=False,
        index=False,
        na_rep="NaN"
    )


def backup_file(file_path):
    """
    Create backup before overwriting.
    """

    file_path = Path(file_path)

    backup_path = file_path.with_name(
        file_path.name + BACKUP_SUFFIX
    )

    if not backup_path.exists():
        backup_path.write_bytes(
            file_path.read_bytes()
        )


# =============================================================================
# LENGTH AND TIME FUNCTIONS
# =============================================================================

def get_target_length(scenario_dir):
    """
    Determine target length from the 7 reference climate files.
    """

    lengths = {}

    for file_name in REFERENCE_CLIMATE_FILES:

        file_path = scenario_dir / file_name

        if file_path.exists():

            values = read_dt_file(file_path)

            lengths[file_name] = len(values)

    if not lengths:

        raise FileNotFoundError(
            f"No reference climate dt files found in:\n{scenario_dir}"
        )

    print()
    print("Reference climate file lengths:")

    for file_name, length in lengths.items():

        print(f"  {file_name:30s} {length:,}")

    unique_lengths = sorted(set(lengths.values()))

    if len(unique_lengths) > 1:

        print()
        print("WARNING: Reference climate files have different lengths.")
        print("Using the maximum length as target length.")

    target_length = max(unique_lengths)

    print()
    print(f"Target length: {target_length:,}")

    return target_length


def build_hourly_time_index(scenario, target_length):
    """
    Build hourly time index.

    Timestep 0 is assumed to be Jan 1 00:00 of the scenario start year.
    """

    start_year = START_YEAR_BY_SCENARIO[scenario]

    start_time = pd.Timestamp(
        year=start_year,
        month=1,
        day=1,
        hour=0
    )

    return pd.date_range(
        start=start_time,
        periods=target_length,
        freq="h"
    )


def get_season_mask(time_index):
    """
    True from May 1 00:00 to September 30 23:00 every year.
    """

    t = pd.Series(time_index)

    month = t.dt.month
    day = t.dt.day
    hour = t.dt.hour

    after_start = (
        (month > SEASON_START_MONTH)
        |
        (
            (month == SEASON_START_MONTH)
            &
            (
                (day > SEASON_START_DAY)
                |
                (
                    (day == SEASON_START_DAY)
                    &
                    (hour >= SEASON_START_HOUR)
                )
            )
        )
    )

    before_end = (
        (month < SEASON_END_MONTH)
        |
        (
            (month == SEASON_END_MONTH)
            &
            (
                (day < SEASON_END_DAY)
                |
                (
                    (day == SEASON_END_DAY)
                    &
                    (hour <= SEASON_END_HOUR)
                )
            )
        )
    )

    return (after_start & before_end).to_numpy()


def get_season_indices_by_year(time_index):
    """
    Return seasonal indices by year.
    """

    t = pd.Series(time_index)

    season_mask = get_season_mask(time_index)

    years = sorted(t.dt.year.unique())

    result = {}

    for year in years:

        year_mask = (t.dt.year == year).to_numpy()

        indices = np.where(year_mask & season_mask)[0]

        if len(indices) > 0:
            result[year] = indices

    return result


def extend_or_truncate_previous_values(values, target_length):
    """
    Extend with last value or truncate.
    """

    values = pd.Series(values).reset_index(drop=True)

    current_length = len(values)

    if current_length == target_length:

        return values

    if current_length > target_length:

        return values.iloc[:target_length].reset_index(drop=True)

    if current_length == 0:

        raise ValueError("Cannot extend an empty dt file.")

    last_value = values.iloc[-1]

    extension_length = target_length - current_length

    extension = pd.Series(
        [last_value] * extension_length
    )

    output = pd.concat(
        [
            values,
            extension
        ],
        ignore_index=True
    )

    return output


# =============================================================================
# SPECIAL MODIFICATION FUNCTIONS
# =============================================================================

def modify_draincontrol(values, target_length, time_index):
    """
    For dt_draincontrol:

        May 1 00:00 to Sep 30 23:00 -> -2
        otherwise keep/extend previous values
    """

    output_values = extend_or_truncate_previous_values(
        values,
        target_length
    )

    season_mask = get_season_mask(
        time_index
    )

    output_values.loc[season_mask] = DRAINCONTROL_SEASON_VALUE

    return output_values.reset_index(drop=True)


def modify_rrotdepths(values, target_length, time_index):
    """
    For dt_rrotdepths:

    Copy/repeat the seasonal pattern from May 1 00:00 to Sep 30 23:00
    for every year.
    """

    output_values = extend_or_truncate_previous_values(
        values,
        target_length
    )

    original_values = pd.Series(values).reset_index(drop=True)

    original_length = len(original_values)

    season_indices_by_year = get_season_indices_by_year(
        time_index
    )

    template_values = None

    for year, indices in season_indices_by_year.items():

        valid_indices = indices[
            indices < original_length
        ]

        if len(valid_indices) > 0:

            template_values = original_values.iloc[
                valid_indices
            ].reset_index(drop=True)

            break

    if template_values is None or len(template_values) == 0:

        print("    WARNING: No seasonal template found for rrotdepths.")
        print("    Using normal previous-value extension.")

        return output_values.reset_index(drop=True)

    template_array = template_values.to_numpy()

    for year, indices in season_indices_by_year.items():

        required_length = len(indices)

        repeated_values = np.resize(
            template_array,
            required_length
        )

        output_values.iloc[indices] = repeated_values

    return output_values.reset_index(drop=True)


# =============================================================================
# FILE IDENTIFICATION
# =============================================================================

def is_draincontrol_file(file_name):
    """
    Detect draincontrol file.
    """

    name = file_name.lower()

    return (
        "draincontrol" in name
        or "drain_control" in name
        or "dt_drain" in name
    )


def is_rrotdepths_file(file_name):
    """
    Detect rrotdepths/root depth file.
    """

    name = file_name.lower()

    return (
        "rrotdepths" in name
        or "rootdepth" in name
        or "root_depth" in name
        or "dt_rrot" in name
    )


def should_modify_file(file_name):
    """
    Modify only files explicitly listed in FILES_TO_MODIFY.

    Never modify the 7 protected climate files.
    """

    if file_name in PROTECTED_CLIMATE_FILES:
        return False

    if file_name in FILES_TO_MODIFY:
        return True

    return False


# =============================================================================
# PROCESS SCENARIO
# =============================================================================

def process_scenario(scenario):
    """
    Process only selected dt files for one scenario.
    """

    scenario_dir = BASE_DIR / scenario

    if not scenario_dir.exists():

        print()
        print(f"WARNING: Scenario folder not found:")
        print(scenario_dir)

        return

    print()
    print("==================================================")
    print(f"PROCESSING SCENARIO: {scenario}")
    print("==================================================")
    print(f"Folder: {scenario_dir}")

    target_length = get_target_length(
        scenario_dir
    )

    time_index = build_hourly_time_index(
        scenario,
        target_length
    )

    print()
    print(f"Assumed start time: {time_index[0]}")
    print(f"Assumed end time:   {time_index[-1]}")

    modified_count = 0
    skipped_count = 0
    missing_count = 0

    print()
    print("Files selected for modification:")

    for file_name in FILES_TO_MODIFY:

        file_path = scenario_dir / file_name

        if file_name in PROTECTED_CLIMATE_FILES:

            print(f"  SKIP protected climate file: {file_name}")
            skipped_count += 1
            continue

        if not file_path.exists():

            print(f"  MISSING: {file_name}")
            missing_count += 1
            continue

        print(f"  MODIFY: {file_name}")

        values = read_dt_file(
            file_path
        )

        original_length = len(values)

        if CREATE_BACKUP:
            backup_file(
                file_path
            )

        if is_draincontrol_file(file_name):

            new_values = modify_draincontrol(
                values,
                target_length,
                time_index
            )

            print("    Type: draincontrol")
            print("    May 1 00:00 to Sep 30 23:00 set to -2.")

        elif is_rrotdepths_file(file_name):

            new_values = modify_rrotdepths(
                values,
                target_length,
                time_index
            )

            print("    Type: rrotdepths")
            print("    Seasonal root-depth pattern copied/repeated.")

        else:

            new_values = extend_or_truncate_previous_values(
                values,
                target_length
            )

            print("    Type: generic selected file")
            print("    Extended/truncated using previous/last value.")

        write_dt_file(
            file_path,
            new_values
        )

        print(f"    Original length: {original_length:,}")
        print(f"    New length:      {len(new_values):,}")

        modified_count += 1

    print()
    print(f"Scenario completed: {scenario}")
    print(f"Modified files: {modified_count}")
    print(f"Missing selected files: {missing_count}")
    print(f"Skipped files: {skipped_count}")


# =============================================================================
# MAIN
# =============================================================================

def main():

    print()
    print("==================================================")
    print(" MODIFYING ONLY SELECTED DT FILES")
    print("==================================================")
    print(f"Base directory: {BASE_DIR}")
    print("==================================================")

    if not BASE_DIR.exists():

        raise FileNotFoundError(
            f"BASE_DIR does not exist:\n{BASE_DIR}"
        )

    print()
    print("Protected climate files, never modified:")

    for file_name in REFERENCE_CLIMATE_FILES:
        print(f"  - {file_name}")

    print()
    print("User-selected files to modify:")

    for file_name in FILES_TO_MODIFY:
        print(f"  - {file_name}")

    for scenario in SCENARIOS:

        process_scenario(
            scenario
        )

    print()
    print("==================================================")
    print("ALL SCENARIOS COMPLETED")
    print("==================================================")


if __name__ == "__main__":

    main()
