# -*- coding: utf-8 -*-
"""
Created on Thu Sep  3 12:14:00 2026

@author: bhattaj1
"""
# ============================================================
# SCRIPT 2 - FINAL VERSION
# ============================================================
#
# SIEVI HOURLY METEOROLOGICAL DATA + FAO-56 PET
#
# INPUT:
#   Daily climate files:
#       sievi_daily_bias_corrected_historical.csv
#       sievi_daily_bias_corrected_ssp245.csv
#       sievi_daily_bias_corrected_ssp585.csv
#
#   Daily Ylivieska wind file:
#       Any CSV containing:
#           - one date column
#           - one wind-speed column
#
# IMPORTANT:
#   Column names do NOT need to have specific names.
#   The script identifies columns from their contents.
#
# OUTPUT:
#   sievi_final_hourly_penman_inputs_historical.csv
#   sievi_final_hourly_penman_inputs_ssp245.csv
#   sievi_final_hourly_penman_inputs_ssp585.csv
#
# OUTPUT CONTAINS:
#   temperature
#   relative humidity
#   solar radiation
#   precipitation
#   wind speed
#   extraterrestrial radiation
#   clear-sky radiation
#   vapour pressure
#   net shortwave radiation
#   net longwave radiation
#   net radiation
#   soil heat flux
#   PET
#
# PET METHOD:
#   FAO-56 hourly Penman-Monteith
#
# ============================================================

import os
import numpy as np
import pandas as pd


# ============================================================
# 1. USER SETTINGS
# ============================================================

# ------------------------------------------------------------
# Change this to your working directory
# ------------------------------------------------------------

WORK_DIR = r"C:\Users\bhattaj1\Desktop\Rewater\Climate_Data_&_Script\sievi_daily_time_series"


# ------------------------------------------------------------
# Scenario names
# ------------------------------------------------------------

SCENARIOS = [
    "historical",
    "ssp245",
    "ssp585"
]


# ------------------------------------------------------------
# Ylivieska wind file
# ------------------------------------------------------------

WIND_FILE = r"C:\Users\bhattaj1\Desktop\Rewater\Climate_Data_&_Script\gridded_data\sievi_gridded_wind_speed_daily.csv"

# ------------------------------------------------------------
# Output directory
# ------------------------------------------------------------

OUTPUT_DIR = WORK_DIR


# ============================================================
# 2. SIEVI SITE PARAMETERS
# ============================================================

# Latitude supplied for Sievi
SIEVI_LAT_DEG = 63.92297

# Approximate longitude of Sievi
# Used only for solar-time correction.
SIEVI_LON_DEG = 24.516

# Approximate elevation of Sievi.
#
# IMPORTANT:
# If you have the exact elevation of your model grid cell,
# replace this value with that elevation.
ALTITUDE_M = 98.0

# FAO-56 reference surface albedo
ALBEDO = 0.23


# ============================================================
# 3. TIME PARAMETERS
# ============================================================

# Finland standard-time meridian
#
# Finland standard time = UTC+2
# Standard meridian = 30 degrees E
STANDARD_MERIDIAN_DEG = 30.0

# Finland timezone
TIME_ZONE = "Europe/Helsinki"


# ============================================================
# 4. WIND PARAMETERS
# ============================================================

# The Ylivieska wind data supplied by you are DAILY.
#
# We use the daily data to calculate monthly mean/std and
# then generate hourly wind values.
#
# Change this only if your source wind measurements were
# taken at another height.
WIND_MEASUREMENT_HEIGHT_M = 10.0

# FAO-56 Penman-Monteith requires wind at 2 m.
WIND_REFERENCE_HEIGHT_M = 2.0


# ============================================================
# 5. PHYSICAL CONSTANTS
# ============================================================

# Solar constant
# MJ m-2 min-1
GSC = 0.0820

# Stefan-Boltzmann constant converted to hourly units
#
# Standard FAO value:
# 4.903e-9 MJ m-2 day-1 K-4
#
# For hourly calculations:
SIGMA_HOURLY = 4.903e-9 / 24.0


# ============================================================
# 6. BASIC FAO-56 FUNCTIONS
# ============================================================

def saturation_vapour_pressure(temp_c):
    """
    Saturation vapour pressure.

    FAO-56 equation.

    Input:
        temperature [degC]

    Output:
        es [kPa]
    """

    temp_c = np.asarray(
        temp_c,
        dtype=float
    )

    return (
        0.6108
        * np.exp(
            17.27
            * temp_c
            / (temp_c + 237.3)
        )
    )


def vapour_pressure_slope(temp_c):
    """
    Slope of saturation vapour pressure curve.

    FAO-56.

    Output:
        delta [kPa degC-1]
    """

    temp_c = np.asarray(
        temp_c,
        dtype=float
    )

    es = saturation_vapour_pressure(
        temp_c
    )

    return (
        4098.0
        * es
        / (temp_c + 237.3) ** 2
    )


def atmospheric_pressure(altitude_m):
    """
    Atmospheric pressure from elevation.

    FAO-56.

    Output:
        P [kPa]
    """

    return (
        101.3
        * (
            (
                293.0
                - 0.0065 * altitude_m
            )
            / 293.0
        ) ** 5.26
    )


def solar_declination(day_of_year):
    """
    Solar declination.

    FAO-56.

    Output:
        delta [radians]
    """

    return (
        0.409
        * np.sin(
            2.0
            * np.pi
            * day_of_year
            / 365.0
            - 1.39
        )
    )


def inverse_relative_distance(day_of_year):
    """
    Inverse relative Earth-Sun distance.

    FAO-56.
    """

    return (
        1.0
        + 0.033
        * np.cos(
            2.0
            * np.pi
            * day_of_year
            / 365.0
        )
    )


def sunset_hour_angle(
    latitude_rad,
    solar_declination_rad
):
    """
    Sunset hour angle.

    FAO-56.
    """

    argument = (
        -np.tan(latitude_rad)
        * np.tan(solar_declination_rad)
    )

    argument = np.clip(
        argument,
        -1.0,
        1.0
    )

    return np.arccos(argument)


# ============================================================
# 7. DAILY EXTRATERRESTRIAL RADIATION
# ============================================================

def extraterrestrial_radiation_daily(
    latitude_rad,
    day_of_year
):
    """
    Daily extraterrestrial radiation.

    FAO-56.

    Output:
        Ra [MJ m-2 day-1]
    """

    delta = solar_declination(
        day_of_year
    )

    dr = inverse_relative_distance(
        day_of_year
    )

    omega_s = sunset_hour_angle(
        latitude_rad,
        delta
    )

    Ra = (
        (24.0 * 60.0 / np.pi)
        * GSC
        * dr
        * (
            omega_s
            * np.sin(latitude_rad)
            * np.sin(delta)
            +
            np.cos(latitude_rad)
            * np.cos(delta)
            * np.sin(omega_s)
        )
    )

    return max(
        float(Ra),
        0.0
    )


# ============================================================
# 8. EQUATION OF TIME
# ============================================================

def equation_of_time(day_of_year):
    """
    Equation of time.

    Output:
        minutes
    """

    B = (
        2.0
        * np.pi
        * (day_of_year - 81.0)
        / 364.0
    )

    return (
        9.87 * np.sin(2.0 * B)
        - 7.53 * np.cos(B)
        - 1.5 * np.sin(B)
    )


# ============================================================
# 9. SOLAR TIME
# ============================================================

def solar_time_from_local_timestamp(
    timestamp
):
    """
    Converts local Finnish clock time into apparent solar time.

    Includes:
        - longitude correction
        - equation of time

    This is important because Sievi is not located at the
    Finnish standard meridian (30 E).
    """

    ts = pd.Timestamp(
        timestamp
    )

    # --------------------------------------------------------
    # If timestamps are naive, interpret them as Finnish
    # local clock time.
    # --------------------------------------------------------

    if ts.tzinfo is None:

        ts = ts.tz_localize(
            TIME_ZONE,
            ambiguous="NaT",
            nonexistent="shift_forward"
        )

    # --------------------------------------------------------
    # Convert to UTC
    # --------------------------------------------------------

    ts_utc = ts.tz_convert(
        "UTC"
    )

    # --------------------------------------------------------
    # Convert to Finnish STANDARD time.
    #
    # We use UTC+2 here because the longitude correction is
    # referenced to the standard meridian (30 E).
    #
    # DST is therefore not double-counted.
    # --------------------------------------------------------

    standard_time = (
        ts_utc
        + pd.Timedelta(hours=2)
    )

    decimal_hour = (
        standard_time.hour
        + standard_time.minute / 60.0
        + standard_time.second / 3600.0
        + standard_time.microsecond
        / 3.6e9
    )

    day_of_year = (
        standard_time.dayofyear
    )

    eot_minutes = (
        equation_of_time(
            day_of_year
        )
    )

    longitude_correction_minutes = (
        4.0
        * (
            STANDARD_MERIDIAN_DEG
            - SIEVI_LON_DEG
        )
    )

    solar_time = (
        decimal_hour
        + (
            longitude_correction_minutes
            + eot_minutes
        ) / 60.0
    )

    return solar_time


# ============================================================
# 10. HOURLY EXTRATERRESTRIAL RADIATION
# ============================================================

def extraterrestrial_radiation_hourly(
    timestamp,
    latitude_rad
):
    """
    Hourly extraterrestrial radiation.

    FAO-56 hourly calculation.

    Output:
        Ra [MJ m-2 h-1]
    """

    ts = pd.Timestamp(
        timestamp
    )

    if ts.tzinfo is None:

        ts = ts.tz_localize(
            TIME_ZONE,
            ambiguous="NaT",
            nonexistent="shift_forward"
        )

    ts_utc = ts.tz_convert(
        "UTC"
    )

    standard_time = (
        ts_utc
        + pd.Timedelta(hours=2)
    )

    day_of_year = (
        standard_time.dayofyear
    )

    delta = solar_declination(
        day_of_year
    )

    dr = inverse_relative_distance(
        day_of_year
    )

    solar_time = (
        solar_time_from_local_timestamp(
            ts
        )
    )

    # Centre of the hourly interval
    solar_time_start = (
        solar_time - 0.5
    )

    solar_time_end = (
        solar_time + 0.5
    )

    # Solar hour angle
    omega1 = (
        np.pi / 12.0
        * (
            solar_time_start
            - 12.0
        )
    )

    omega2 = (
        np.pi / 12.0
        * (
            solar_time_end
            - 12.0
        )
    )

    # Sunset hour angle
    omega_s = sunset_hour_angle(
        latitude_rad,
        delta
    )

    # Limit to daylight period
    omega1 = max(
        omega1,
        -omega_s
    )

    omega2 = min(
        omega2,
        omega_s
    )

    if omega2 <= omega1:
        return 0.0

    Ra = (
        (12.0 * 60.0 / np.pi)
        * GSC
        * dr
        * (
            (omega2 - omega1)
            * np.sin(latitude_rad)
            * np.sin(delta)
            +
            np.cos(latitude_rad)
            * np.cos(delta)
            * (
                np.sin(omega2)
                - np.sin(omega1)
            )
        )
    )

    return max(
        float(Ra),
        0.0
    )


# ============================================================
# 11. CLEAR-SKY RADIATION
# ============================================================

def clear_sky_radiation_hourly(
    ra_hourly,
    altitude_m
):
    """
    FAO-56 clear-sky solar radiation.

    Rso = (0.75 + 2e-5*z) Ra

    Output:
        Rso [MJ m-2 h-1]
    """

    return (
        0.75
        + 2.0e-5 * altitude_m
    ) * ra_hourly


# ============================================================
# 12. WIND HEIGHT CONVERSION
# ============================================================

def wind_to_2m(
    wind_speed,
    measurement_height_m
):
    """
    Converts wind speed from measurement height to 2 m.

    FAO-56 logarithmic wind-height correction.
    """

    wind_speed = np.asarray(
        wind_speed,
        dtype=float
    )

    factor = (
        4.87
        / np.log(
            67.8
            * measurement_height_m
            - 5.42
        )
    )

    return (
        wind_speed
        * factor
    )


# ============================================================
# 13. AUTOMATIC COLUMN IDENTIFICATION
# ============================================================

def identify_date_column(
    df,
    file_description
):
    """
    Automatically identifies the date column.

    Column names do not matter.
    """

    candidates = []

    for col in df.columns:

        converted = pd.to_datetime(
            df[col],
            errors="coerce"
        )

        valid_fraction = (
            converted.notna().mean()
        )

        if valid_fraction >= 0.80:

            candidates.append(
                (
                    col,
                    valid_fraction
                )
            )

    if not candidates:

        raise ValueError(
            f"\nCould not identify the date column in "
            f"{file_description}.\n\n"
            f"Columns found:\n"
            f"{list(df.columns)}"
        )

    # Select the column with the highest proportion
    # of valid dates.
    selected = max(
        candidates,
        key=lambda x: x[1]
    )[0]

    return selected


def numeric_column_score(
    series
):
    """
    Calculates the fraction of valid numeric values.
    """

    numeric = pd.to_numeric(
        series,
        errors="coerce"
    )

    return (
        numeric.notna().mean(),
        numeric
    )


# ============================================================
# 14. IDENTIFY DAILY CLIMATE VARIABLES
# ============================================================

def identify_daily_climate_columns(
    df
):
    """
    Identify:
        date
        tas
        tasmax
        tasmin
        precipitation

    primarily from column names where possible, and otherwise
    from the numeric data.

    The actual column names do NOT need to match the expected
    names.
    """

    columns = list(
        df.columns
    )

    # --------------------------------------------------------
    # Date
    # --------------------------------------------------------

    date_col = identify_date_column(
        df,
        "daily climate file"
    )

    # --------------------------------------------------------
    # Convert all remaining columns to numeric where possible
    # --------------------------------------------------------

    numeric_info = {}

    for col in columns:

        if col == date_col:
            continue

        score, numeric = (
            numeric_column_score(
                df[col]
            )
        )

        if score >= 0.80:

            numeric_info[col] = numeric

    if len(numeric_info) < 4:

        raise ValueError(
            "\nCould not identify the four required climate "
            "variables (temperature, Tmax, Tmin, precipitation).\n\n"
            f"Columns found:\n{columns}\n\n"
            "At least four numeric climate columns are required."
        )

    # --------------------------------------------------------
    # Name-based clues
    #
    # Names are NOT required, but if useful clues exist we
    # use them.
    # --------------------------------------------------------

    lower_names = {
        col: str(col).lower()
        for col in numeric_info
    }

    def find_by_keywords(
        keywords,
        exclude=None
    ):

        if exclude is None:
            exclude = []

        for col, name in lower_names.items():

            if col in exclude:
                continue

            if any(
                keyword in name
                for keyword in keywords
            ):
                return col

        return None

    # --------------------------------------------------------
    # Temperature mean
    # --------------------------------------------------------

    tas_col = find_by_keywords(
        [
            "tas",
            "tmean",
            "mean_temp",
            "temperature_mean",
            "temp_mean",
            "temperature"
        ]
    )

    # --------------------------------------------------------
    # Maximum temperature
    # --------------------------------------------------------

    tasmax_col = find_by_keywords(
        [
            "tasmax",
            "tmax",
            "max_temp",
            "maximum_temp",
            "temp_max",
            "temperature_max"
        ]
    )

    # --------------------------------------------------------
    # Minimum temperature
    # --------------------------------------------------------

    tasmin_col = find_by_keywords(
        [
            "tasmin",
            "tmin",
            "min_temp",
            "minimum_temp",
            "temp_min",
            "temperature_min"
        ]
    )

    # --------------------------------------------------------
    # Precipitation
    # --------------------------------------------------------

    pr_col = find_by_keywords(
        [
            "pr",
            "precip",
            "rain",
            "rainfall",
            "precipitation"
        ]
    )

    # --------------------------------------------------------
    # If names are unhelpful, identify temperature columns
    # based on their values.
    # --------------------------------------------------------

    remaining = list(
        numeric_info.keys()
    )

    # Exclude already identified variables
    used = set(
        x for x in [
            tas_col,
            tasmax_col,
            tasmin_col,
            pr_col
        ]
        if x is not None
    )

    remaining_unused = [
        col
        for col in remaining
        if col not in used
    ]

    # --------------------------------------------------------
    # Identify precipitation from a remaining column if
    # it contains non-negative values.
    # --------------------------------------------------------

    if pr_col is None:

        precipitation_candidates = []

        for col in remaining_unused:

            values = numeric_info[
                col
            ].dropna()

            if len(values) == 0:
                continue

            nonnegative_fraction = (
                (values >= 0).mean()
            )

            if nonnegative_fraction >= 0.95:

                precipitation_candidates.append(
                    (
                        col,
                        values.mean()
                    )
                )

        # Precipitation is often the non-negative variable
        # whose values are not strongly temperature-like.
        if precipitation_candidates:

            # Prefer a column whose name contains a clue.
            # Otherwise use the first suitable candidate.
            pr_col = (
                precipitation_candidates[0][0]
            )

    # --------------------------------------------------------
    # If temperature names were not found, use statistical
    # relationships among numeric columns.
    # --------------------------------------------------------

    if (
        tas_col is None
        or tasmax_col is None
        or tasmin_col is None
    ):

        candidates = []

        for col in numeric_info:

            if col == pr_col:
                continue

            values = (
                numeric_info[col]
                .dropna()
            )

            if len(values) == 0:
                continue

            mean_value = values.mean()

            # Temperature is expected to be roughly in a
            # realistic climate range.
            if (
                mean_value >= -60
                and mean_value <= 60
            ):
                candidates.append(
                    (
                        col,
                        mean_value,
                        values.std()
                    )
                )

        # ----------------------------------------------------
        # Need at least three temperature-like columns.
        # ----------------------------------------------------

        if len(candidates) >= 3:

            # Sort by mean value.
            sorted_candidates = sorted(
                candidates,
                key=lambda x: x[1]
            )

            # Lowest mean is likely Tmin
            if tasmin_col is None:
                tasmin_col = (
                    sorted_candidates[0][0]
                )

            # Highest mean is likely Tmax
            if tasmax_col is None:
                tasmax_col = (
                    sorted_candidates[-1][0]
                )

            # Remaining middle candidate is likely mean T.
            if tas_col is None:

                middle_candidates = [
                    item
                    for item in sorted_candidates
                    if item[0]
                    not in [
                        tasmin_col,
                        tasmax_col
                    ]
                ]

                if middle_candidates:

                    # Select the candidate whose mean is
                    # closest to midpoint of Tmin/Tmax.
                    target = (
                        numeric_info[
                            tasmin_col
                        ].mean()
                        +
                        numeric_info[
                            tasmax_col
                        ].mean()
                    ) / 2.0

                    tas_col = min(
                        middle_candidates,
                        key=lambda x:
                        abs(x[1] - target)
                    )[0]

    # --------------------------------------------------------
    # Final validation
    # --------------------------------------------------------

    identified = {
        "date": date_col,
        "tas": tas_col,
        "tasmax": tasmax_col,
        "tasmin": tasmin_col,
        "pr": pr_col
    }

    missing = [
        name
        for name, col in identified.items()
        if col is None
    ]

    if missing:

        raise ValueError(
            "\nCould not automatically identify:\n"
            + "\n".join(
                f"  - {item}"
                for item in missing
            )
            + "\n\nColumns found:\n"
            + "\n".join(
                f"  - {col}"
                for col in columns
            )
            + "\n\nIf your climate file has unusual structure, "
              "the column structure needs to be checked."
        )

    # --------------------------------------------------------
    # Print identification
    # --------------------------------------------------------

    print("\nIdentified climate columns:")

    for name, col in identified.items():

        print(
            f"  {name:8s} -> {col}"
        )

    return identified


# ============================================================
# 15. READ DAILY CLIMATE DATA
# ============================================================

def read_daily_data(
    file_path
):

    df = pd.read_csv(
        file_path
    )

    print("\n----------------------------------------------")
    print("Reading daily climate data")
    print("----------------------------------------------")

    print(
        "Columns found:"
    )

    print(
        list(df.columns)
    )

    identified = (
        identify_daily_climate_columns(
            df
        )
    )

    # --------------------------------------------------------
    # Standardize internally.
    #
    # The rest of the script therefore does NOT care what
    # the original column names were.
    # --------------------------------------------------------

    result = pd.DataFrame()

    result["timestamp"] = pd.to_datetime(
        df[
            identified["date"]
        ],
        errors="coerce"
    )

    result["tas"] = pd.to_numeric(
        df[
            identified["tas"]
        ],
        errors="coerce"
    )

    result["tasmax"] = pd.to_numeric(
        df[
            identified["tasmax"]
        ],
        errors="coerce"
    )

    result["tasmin"] = pd.to_numeric(
        df[
            identified["tasmin"]
        ],
        errors="coerce"
    )

    result["pr"] = pd.to_numeric(
        df[
            identified["pr"]
        ],
        errors="coerce"
    )

    # --------------------------------------------------------
    # Remove invalid rows
    # --------------------------------------------------------

    result = result.dropna(
        subset=[
            "timestamp",
            "tas",
            "tasmax",
            "tasmin",
            "pr"
        ]
    ).copy()

    # --------------------------------------------------------
    # Basic physical consistency
    # --------------------------------------------------------

    # Tmax should not be lower than Tmin.
    invalid_temperature_range = (
        result["tasmax"]
        < result["tasmin"]
    )

    if invalid_temperature_range.any():

        print(
            "WARNING:"
            f" {invalid_temperature_range.sum()} rows "
            "have Tmax < Tmin."
        )

        # Swap the two values where necessary.
        bad_indices = result.index[
            invalid_temperature_range
        ]

        old_tmax = result.loc[
            bad_indices,
            "tasmax"
        ].copy()

        result.loc[
            bad_indices,
            "tasmax"
        ] = result.loc[
            bad_indices,
            "tasmin"
        ]

        result.loc[
            bad_indices,
            "tasmin"
        ] = old_tmax

    # Precipitation cannot be negative.
    result["pr"] = np.maximum(
        result["pr"],
        0.0
    )

    result = result.sort_values(
        "timestamp"
    ).reset_index(
        drop=True
    )

    print(
        f"Number of daily records: "
        f"{len(result):,}"
    )

    print(
        f"Date range: "
        f"{result['timestamp'].min()} "
        f"to "
        f"{result['timestamp'].max()}"
    )

    return result


# ============================================================
# 16. READ DAILY YLIVIESKA WIND DATA
# ============================================================

def read_wind_data(
    file_path
):
    """
    Reads daily Ylivieska wind data.

    The column names do NOT matter.

    The function identifies:
        - date column
        - wind-speed column

    from the actual contents.
    """

    wind = pd.read_csv(
        file_path
    )

    print("\n----------------------------------------------")
    print("Reading Ylivieska wind data")
    print("----------------------------------------------")

    print(
        "Columns found:"
    )

    print(
        list(wind.columns)
    )

    if wind.shape[1] < 2:

        raise ValueError(
            "The Ylivieska wind file must contain "
            "at least two columns."
        )

    # --------------------------------------------------------
    # Identify date column
    # --------------------------------------------------------

    date_col = identify_date_column(
        wind,
        "Ylivieska wind file"
    )

    print(
        f"Identified wind date column: "
        f"'{date_col}'"
    )

    wind["wind_date"] = pd.to_datetime(
        wind[date_col],
        errors="coerce"
    )

    # --------------------------------------------------------
    # Identify wind-speed column
    # --------------------------------------------------------

    wind_candidates = []

    for col in wind.columns:

        if col == date_col:
            continue

        numeric = pd.to_numeric(
            wind[col],
            errors="coerce"
        )

        valid_fraction = (
            numeric.notna().mean()
        )

        if valid_fraction < 0.80:
            continue

        values = numeric.dropna()

        if len(values) == 0:
            continue

        # Wind speed should be non-negative.
        nonnegative_fraction = (
            (values >= 0).mean()
        )

        # Reject obviously impossible values.
        reasonable_fraction = (
            (values <= 100).mean()
        )

        if (
            nonnegative_fraction >= 0.95
            and reasonable_fraction >= 0.95
        ):

            wind_candidates.append(
                (
                    col,
                    valid_fraction
                )
            )

    if not wind_candidates:

        raise ValueError(
            "\nCould not identify the wind-speed column.\n\n"
            f"Columns found:\n"
            f"{list(wind.columns)}"
        )

    # --------------------------------------------------------
    # Prefer a column whose name contains wind/ws if several
    # numeric columns exist.
    # --------------------------------------------------------

    wind_col = None

    for col, score in wind_candidates:

        name = str(
            col
        ).lower()

        if (
            "wind" in name
            or name == "ws"
            or "ws_" in name
        ):

            wind_col = col
            break

    # Otherwise use the first valid numeric column.
    if wind_col is None:

        wind_col = (
            wind_candidates[0][0]
        )

    print(
        f"Identified wind-speed column: "
        f"'{wind_col}'"
    )

    wind["wind_speed"] = pd.to_numeric(
        wind[wind_col],
        errors="coerce"
    )

    # --------------------------------------------------------
    # Clean
    # --------------------------------------------------------

    wind = wind.dropna(
        subset=[
            "wind_date",
            "wind_speed"
        ]
    ).copy()

    wind["wind_speed"] = np.maximum(
        wind["wind_speed"],
        0.0
    )

    # --------------------------------------------------------
    # Monthly statistics
    # --------------------------------------------------------

    wind["month"] = (
        wind["wind_date"].dt.month
    )

    monthly_stats = (
        wind.groupby(
            "month"
        )["wind_speed"]
        .agg(
            mean="mean",
            std="std"
        )
    )

    monthly_stats["std"] = (
        monthly_stats["std"]
        .fillna(0.0)
    )

    print(
        f"\nNumber of daily wind observations: "
        f"{len(wind):,}"
    )

    print(
        f"Mean wind speed: "
        f"{wind['wind_speed'].mean():.3f} m/s"
    )

    print(
        "\nMonthly wind statistics:"
    )

    print(
        monthly_stats
    )

    return monthly_stats


# ============================================================
# 17. DAILY RELATIVE HUMIDITY
# ============================================================

def calculate_daily_relative_humidity(
    df_daily
):
    """
    Estimate daily RH by assuming Tmin approximately equals
    dewpoint temperature.

    RH = 100 * es(Tmin) / es(Tmean)

    This is a data-assumption because actual dewpoint was not
    provided.
    """

    tmean = df_daily[
        "tas"
    ].to_numpy(
        dtype=float
    )

    tmin = df_daily[
        "tasmin"
    ].to_numpy(
        dtype=float
    )

    es_mean = saturation_vapour_pressure(
        tmean
    )

    ea = saturation_vapour_pressure(
        tmin
    )

    rh = (
        100.0
        * ea
        / es_mean
    )

    # Prevent unrealistic values.
    rh = np.clip(
        rh,
        15.0,
        100.0
    )

    return rh


# ============================================================
# 18. DAILY HARGREAVES-SAMANI SOLAR RADIATION
# ============================================================

def calculate_daily_solar_radiation(
    df_daily
):
    """
    Hargreaves-Samani daily solar radiation.

    Rs = 0.16 * Ra * sqrt(Tmax - Tmin)

    Output:
        Rs [MJ m-2 day-1]
    """

    latitude_rad = np.radians(
        SIEVI_LAT_DEG
    )

    doy = (
        df_daily[
            "timestamp"
        ]
        .dt.dayofyear
        .to_numpy()
    )

    tmax = df_daily[
        "tasmax"
    ].to_numpy(
        dtype=float
    )

    tmin = df_daily[
        "tasmin"
    ].to_numpy(
        dtype=float
    )

    temperature_range = np.maximum(
        tmax - tmin,
        0.1
    )

    ra_daily = np.array([
        extraterrestrial_radiation_daily(
            latitude_rad,
            int(day)
        )
        for day in doy
    ])

    rs_daily = (
        0.16
        * ra_daily
        * np.sqrt(
            temperature_range
        )
    )

    return rs_daily


# ============================================================
# 19. BUILD HOURLY DATA
# ============================================================

def build_hourly_data(
    df_daily,
    monthly_wind_stats
):

    df_daily = (
        df_daily.copy()
    )

    # --------------------------------------------------------
    # Daily RH
    # --------------------------------------------------------

    df_daily[
        "rh_daily"
    ] = calculate_daily_relative_humidity(
        df_daily
    )

    # --------------------------------------------------------
    # Daily solar radiation
    # --------------------------------------------------------

    df_daily[
        "rs_daily_mj_m2_day"
    ] = calculate_daily_solar_radiation(
        df_daily
    )

    # --------------------------------------------------------
    # Maps for hourly reconstruction
    # --------------------------------------------------------

    daily_rs_map = dict(
        zip(
            df_daily[
                "timestamp"
            ].dt.date,
            df_daily[
                "rs_daily_mj_m2_day"
            ]
        )
    )

    daily_rh_map = dict(
        zip(
            df_daily[
                "timestamp"
            ].dt.date,
            df_daily[
                "rh_daily"
            ]
        )
    )

    daily_tmean_map = dict(
        zip(
            df_daily[
                "timestamp"
            ].dt.date,
            df_daily[
                "tas"
            ]
        )
    )

    daily_tmax_map = dict(
        zip(
            df_daily[
                "timestamp"
            ].dt.date,
            df_daily[
                "tasmax"
            ]
        )
    )

    daily_tmin_map = dict(
        zip(
            df_daily[
                "timestamp"
            ].dt.date,
            df_daily[
                "tasmin"
            ]
        )
    )

    daily_pr_map = dict(
        zip(
            df_daily[
                "timestamp"
            ].dt.date,
            df_daily[
                "pr"
            ]
        )
    )

    # --------------------------------------------------------
    # Hourly time index
    # --------------------------------------------------------

    start = (
        df_daily[
            "timestamp"
        ].min()
    )

    end = (
        df_daily[
            "timestamp"
        ].max()
    )

    hourly_index = pd.date_range(
        start=start,
        end=end + pd.Timedelta(hours=23),
        freq="h"
    )

    hourly = pd.DataFrame({
        "timestamp": hourly_index
    })

    hourly["date"] = (
        hourly[
            "timestamp"
        ].dt.date
    )

    # --------------------------------------------------------
    # Assign daily quantities
    # --------------------------------------------------------

    hourly[
        "temperature_celsius"
    ] = hourly[
        "date"
    ].map(
        daily_tmean_map
    )

    hourly[
        "relative_humidity_percent"
    ] = hourly[
        "date"
    ].map(
        daily_rh_map
    )

    hourly[
        "precipitation_daily_mm"
    ] = hourly[
        "date"
    ].map(
        daily_pr_map
    )

    hourly[
        "daily_tmax_celsius"
    ] = hourly[
        "date"
    ].map(
        daily_tmax_map
    )

    hourly[
        "daily_tmin_celsius"
    ] = hourly[
        "date"
    ].map(
        daily_tmin_map
    )

    # Remove dates outside actual climate data.
    hourly = hourly[
        hourly[
            "temperature_celsius"
        ].notna()
    ].copy()

    hourly = hourly.reset_index(
        drop=True
    )

    # --------------------------------------------------------
    # Hour
    # --------------------------------------------------------

    hourly["hour"] = (
        hourly[
            "timestamp"
        ].dt.hour
    )

    hourly["hour_decimal"] = (
        hourly["hour"] + 0.5
    )

    # ========================================================
    # HOURLY TEMPERATURE
    # ========================================================

    temperature_range = (
        hourly[
            "daily_tmax_celsius"
        ]
        -
        hourly[
            "daily_tmin_celsius"
        ]
    ).clip(
        lower=0.0
    )

    # Approximate daily temperature cycle.
    #
    # Maximum around 15:00.
    phase = (
        2.0
        * np.pi
        * (
            hourly[
                "hour_decimal"
            ]
            - 15.0
        )
        / 24.0
    )

    temperature_anomaly = (
        0.5
        * temperature_range
        * np.cos(
            phase
        )
    )

    hourly[
        "temperature_celsius"
    ] = (
        hourly[
            "temperature_celsius"
        ]
        + temperature_anomaly
    )

    # --------------------------------------------------------
    # Force each day's hourly mean back to the original daily
    # mean temperature.
    # --------------------------------------------------------

    daily_mean_target = (
        df_daily
        .set_index(
            df_daily[
                "timestamp"
            ].dt.date
        )["tas"]
    )

    for current_date, group_index in (
        hourly.groupby(
            "date"
        ).groups.items()
    ):

        target = (
            daily_mean_target.loc[
                current_date
            ]
        )

        current_mean = (
            hourly.loc[
                group_index,
                "temperature_celsius"
            ].mean()
        )

        hourly.loc[
            group_index,
            "temperature_celsius"
        ] += (
            target
            - current_mean
        )

    # ========================================================
    # PRECIPITATION
    # ========================================================

    hourly[
        "precipitation_mm"
    ] = (
        hourly[
            "precipitation_daily_mm"
        ]
        / 24.0
    )

    # ========================================================
    # HOURLY WIND
    # ========================================================
    #
    # Source wind data are DAILY.
    #
    # We first calculate monthly statistics from the daily
    # observations, then generate hourly values.
    # ========================================================

    rng = np.random.default_rng(
        42
    )

    wind_values = []

    for current_timestamp in (
        hourly[
            "timestamp"
        ]
    ):

        month = pd.Timestamp(
            current_timestamp
        ).month

        if month in (
            monthly_wind_stats.index
        ):

            mean_wind = (
                monthly_wind_stats.loc[
                    month,
                    "mean"
                ]
            )

            std_wind = (
                monthly_wind_stats.loc[
                    month,
                    "std"
                ]
            )

        else:

            mean_wind = (
                monthly_wind_stats[
                    "mean"
                ].mean()
            )

            std_wind = (
                monthly_wind_stats[
                    "std"
                ].mean()
            )

        wind_value = rng.normal(
            mean_wind,
            std_wind
        )

        wind_values.append(
            wind_value
        )

    hourly[
        "wind_speed_m_s"
    ] = np.maximum(
        np.asarray(
            wind_values
        ),
        0.1
    )

    # --------------------------------------------------------
    # Retain the original Script 2 mild diurnal pattern.
    # --------------------------------------------------------

    daytime = (
        (hourly["hour"] >= 12)
        &
        (hourly["hour"] < 17)
    )

    hourly.loc[
        daytime,
        "wind_speed_m_s"
    ] *= 1.15

    hourly.loc[
        ~daytime,
        "wind_speed_m_s"
    ] *= 0.92

    hourly[
        "wind_speed_m_s"
    ] = np.maximum(
        hourly[
            "wind_speed_m_s"
        ],
        0.1
    )

    # ========================================================
    # HOURLY SOLAR GEOMETRY
    # ========================================================

    latitude_rad = np.radians(
        SIEVI_LAT_DEG
    )

    hourly[
        "extraterrestrial_radiation_mj_m2_h"
    ] = [
        extraterrestrial_radiation_hourly(
            ts,
            latitude_rad
        )
        for ts in hourly[
            "timestamp"
        ]
    ]

    # ========================================================
    # HOURLY SOLAR RADIATION
    # ========================================================
    #
    # Daily Hargreaves-Samani radiation is preserved exactly.
    #
    # It is distributed over daylight hours according to
    # extraterrestrial-radiation weights.
    #
    # This gives:
    #
    # sum(hourly Rs) = daily Hargreaves Rs
    #
    # without introducing an arbitrary correction factor.
    # ========================================================

    hourly[
        "solar_radiation_w_m2"
    ] = 0.0

    for current_date, group_index in (
        hourly.groupby(
            "date"
        ).groups.items()
    ):

        daily_rs_mj = (
            daily_rs_map[
                current_date
            ]
        )

        ra_hour = hourly.loc[
            group_index,
            "extraterrestrial_radiation_mj_m2_h"
        ].to_numpy(
            dtype=float
        )

        total_ra = (
            np.sum(
                ra_hour
            )
        )

        if total_ra > 0.0:

            weights = (
                ra_hour
                / total_ra
            )

            hourly_rs_mj = (
                weights
                * daily_rs_mj
            )

            # MJ m-2 h-1 -> W m-2
            hourly_rs_w = (
                hourly_rs_mj
                / 0.0036
            )

            hourly.loc[
                group_index,
                "solar_radiation_w_m2"
            ] = hourly_rs_w

        else:

            hourly.loc[
                group_index,
                "solar_radiation_w_m2"
            ] = 0.0

    # ========================================================
    # FAO-56 PENMAN-MONTEITH
    # ========================================================

    T = hourly[
        "temperature_celsius"
    ].to_numpy(
        dtype=float
    )

    RH = hourly[
        "relative_humidity_percent"
    ].to_numpy(
        dtype=float
    )

    Rs_w = hourly[
        "solar_radiation_w_m2"
    ].to_numpy(
        dtype=float
    )

    wind = hourly[
        "wind_speed_m_s"
    ].to_numpy(
        dtype=float
    )

    # --------------------------------------------------------
    # Saturation vapour pressure
    # --------------------------------------------------------

    es = saturation_vapour_pressure(
        T
    )

    # --------------------------------------------------------
    # Actual vapour pressure
    # --------------------------------------------------------

    ea = (
        es
        * RH
        / 100.0
    )

    ea = np.clip(
        ea,
        0.0,
        es
    )

    # --------------------------------------------------------
    # Slope of vapour pressure curve
    # --------------------------------------------------------

    delta = (
        vapour_pressure_slope(
            T
        )
    )

    # --------------------------------------------------------
    # Atmospheric pressure
    # --------------------------------------------------------

    pressure_kpa = (
        atmospheric_pressure(
            ALTITUDE_M
        )
    )

    # --------------------------------------------------------
    # Psychrometric constant
    # --------------------------------------------------------

    gamma = (
        0.000665
        * pressure_kpa
    )

    # --------------------------------------------------------
    # Wind at 2 m
    # --------------------------------------------------------

    u2 = wind_to_2m(
        wind,
        WIND_MEASUREMENT_HEIGHT_M
    )

    # ========================================================
    # RADIATION
    # ========================================================

    # W m-2 -> MJ m-2 h-1
    Rs = (
        Rs_w
        * 0.0036
    )

    # --------------------------------------------------------
    # Net shortwave
    # --------------------------------------------------------

    Rns = (
        1.0
        - ALBEDO
    ) * Rs

    # --------------------------------------------------------
    # Clear-sky radiation
    # --------------------------------------------------------

    Ra_hour = hourly[
        "extraterrestrial_radiation_mj_m2_h"
    ].to_numpy(
        dtype=float
    )

    Rso = (
        clear_sky_radiation_hourly(
            Ra_hour,
            ALTITUDE_M
        )
    )

    # --------------------------------------------------------
    # Net longwave radiation
    # --------------------------------------------------------

    Tk = (
        T + 273.16
    )

    # For the FAO cloudiness term, actual Rs/Rso cannot
    # exceed 1.
    Rs_for_rnl = np.minimum(
        Rs,
        Rso
    )

    radiation_ratio = np.divide(
        Rs_for_rnl,
        Rso,
        out=np.zeros_like(
            Rs_for_rnl
        ),
        where=Rso > 0.0
    )

    radiation_ratio = np.clip(
        radiation_ratio,
        0.0,
        1.0
    )

    Rnl = (
        SIGMA_HOURLY
        * Tk ** 4
        * (
            0.34
            - 0.14
            * np.sqrt(
                np.maximum(
                    ea,
                    0.0
                )
            )
        )
        * (
            1.35
            * radiation_ratio
            - 0.35
        )
    )

    # Net outgoing longwave radiation cannot be negative.
    Rnl = np.maximum(
        Rnl,
        0.0
    )

    # --------------------------------------------------------
    # Net radiation
    # --------------------------------------------------------

    Rn = (
        Rns
        - Rnl
    )

    # ========================================================
    # SOIL HEAT FLUX
    # ========================================================

    solar_present = (
        Rs > 0.0
    )

    # FAO-56 hourly approximation:
    #
    # Day:
    #     G = 0.1 Rn
    #
    # Night:
    #     G = 0.5 Rn

    G = np.where(
        solar_present,
        0.1 * Rn,
        0.5 * Rn
    )

    # ========================================================
    # HOURLY PENMAN-MONTEITH PET
    # ========================================================
    #
    # ET0 =
    #
    # [0.408 delta (Rn-G)
    #  +
    #  gamma * 37/(T+273) * u2 * (es-ea)]
    #
    # /
    #
    # [delta + gamma(1+0.34u2)]
    #
    # Result:
    #     mm h-1
    # ========================================================

    numerator = (
        0.408
        * delta
        * (
            Rn - G
        )
        +
        gamma
        * (
            37.0
            / (
                T + 273.0
            )
        )
        * u2
        * (
            es - ea
        )
    )

    denominator = (
        delta
        +
        gamma
        * (
            1.0
            + 0.34 * u2
        )
    )

    PET = np.divide(
        numerator,
        denominator,
        out=np.zeros_like(
            numerator
        ),
        where=denominator > 0.0
    )

    # PET cannot be negative.
    PET = np.maximum(
        PET,
        0.0
    )

    # ========================================================
    # ADD CALCULATED VARIABLES TO OUTPUT
    # ========================================================

    hourly[
        "solar_radiation_mj_m2_h"
    ] = Rs

    hourly[
        "clear_sky_radiation_mj_m2_h"
    ] = Rso

    hourly[
        "actual_vapour_pressure_kpa"
    ] = ea

    hourly[
        "saturation_vapour_pressure_kpa"
    ] = es

    hourly[
        "vapour_pressure_slope_kpa_per_c"
    ] = delta

    hourly[
        "atmospheric_pressure_kpa"
    ] = pressure_kpa

    hourly[
        "psychrometric_constant_kpa_per_c"
    ] = gamma

    hourly[
        "wind_speed_2m_m_s"
    ] = u2

    hourly[
        "net_shortwave_radiation_mj_m2_h"
    ] = Rns

    hourly[
        "longwave_radiation_rnl_mj_m2_h"
    ] = Rnl

    hourly[
        "net_radiation_rn_mj_m2_h"
    ] = Rn

    hourly[
        "soil_heat_flux_g_mj_m2_h"
    ] = G

    hourly[
        "PET_mm_h"
    ] = PET

    # --------------------------------------------------------
    # Solar time for validation/debugging
    # --------------------------------------------------------

    hourly[
        "solar_time_decimal_hour"
    ] = [
        solar_time_from_local_timestamp(
            ts
        )
        for ts in hourly[
            "timestamp"
        ]
    ]

    # ========================================================
    # FINAL OUTPUT COLUMNS
    # ========================================================

    columns_to_keep = [

        # Time
        "timestamp",

        # Meteorological variables
        "temperature_celsius",
        "relative_humidity_percent",
        "precipitation_mm",
        "wind_speed_m_s",
        "wind_speed_2m_m_s",

        # Solar radiation
        "solar_radiation_w_m2",
        "solar_radiation_mj_m2_h",

        # Solar geometry
        # "extraterrestrial_radiation_mj_m2_h",
        # "clear_sky_radiation_mj_m2_h",
        # "solar_time_decimal_hour",

        # Vapour pressure
        # "actual_vapour_pressure_kpa",
        # "saturation_vapour_pressure_kpa",
        # "vapour_pressure_slope_kpa_per_c",

        # Atmospheric variables
        # "atmospheric_pressure_kpa",
        # "psychrometric_constant_kpa_per_c",

        # Energy balance
        "net_shortwave_radiation_mj_m2_h",
        "longwave_radiation_rnl_mj_m2_h",
        # "net_radiation_rn_mj_m2_h",
        # "soil_heat_flux_g_mj_m2_h",

        # Final PET
        "PET_mm_h"
    ]
    

    hourly = hourly[
        columns_to_keep
    ]

    return hourly


# ============================================================
# 20. VALIDATION CHECKS
# ============================================================

def validate_hourly_output(
    hourly,
    scenario
):
    """
    Basic physical/numerical checks.
    """

    print("\n----------------------------------------------")
    print(
        f"Validation: {scenario}"
    )
    print("----------------------------------------------")

    # --------------------------------------------------------
    # Missing values
    # --------------------------------------------------------

    missing = (
        hourly.isna().sum()
    )

    missing_total = (
        missing.sum()
    )

    print(
        f"Missing values: "
        f"{missing_total}"
    )

    if missing_total > 0:

        print(
            "WARNING: Missing values detected."
        )

        print(
            missing[
                missing > 0
            ]
        )

    # --------------------------------------------------------
    # Negative PET
    # --------------------------------------------------------

    negative_pet = (
        hourly[
            "PET_mm_h"
        ] < 0
    ).sum()

    print(
        f"Negative PET values: "
        f"{negative_pet}"
    )

    # --------------------------------------------------------
    # Negative solar radiation
    # --------------------------------------------------------

    negative_solar = (
        hourly[
            "solar_radiation_w_m2"
        ] < 0
    ).sum()

    print(
        f"Negative solar radiation values: "
        f"{negative_solar}"
    )

    # --------------------------------------------------------
    # PET statistics
    # --------------------------------------------------------

    print(
        f"Mean hourly PET: "
        f"{hourly['PET_mm_h'].mean():.5f} mm/h"
    )

    print(
        f"Total PET: "
        f"{hourly['PET_mm_h'].sum():.2f} mm"
    )

    print(
        f"Maximum hourly PET: "
        f"{hourly['PET_mm_h'].max():.5f} mm/h"
    )

    # --------------------------------------------------------
    # Radiation statistics
    # --------------------------------------------------------

    print(
        f"Mean solar radiation: "
        f"{hourly['solar_radiation_w_m2'].mean():.2f} W/m2"
    )

    print(
        f"Maximum solar radiation: "
        f"{hourly['solar_radiation_w_m2'].max():.2f} W/m2"
    )

    print(
        f"Mean wind speed: "
        f"{hourly['wind_speed_m_s'].mean():.2f} m/s"
    )

    print(
        "Validation completed."
    )


# ============================================================
# 21. MAIN PROGRAM
# ============================================================

def main():

    print()
    print("====================================================")
    print(" SIEVI HOURLY FAO-56 PENMAN-MONTEITH PET")
    print("====================================================")
    print(
        f"Latitude:             {SIEVI_LAT_DEG:.5f} deg"
    )
    print(
        f"Longitude:            {SIEVI_LON_DEG:.5f} deg"
    )
    print(
        f"Elevation:            {ALTITUDE_M:.1f} m"
    )
    print(
        f"Albedo:               {ALBEDO:.2f}"
    )
    print(
        f"Wind measurement:     {WIND_MEASUREMENT_HEIGHT_M:.1f} m"
    )
    print(
        f"Wind reference:       {WIND_REFERENCE_HEIGHT_M:.1f} m"
    )
    print(
        "===================================================="
    )
    print()

    # ========================================================
    # READ YLIVIESKA WIND
    # ========================================================

    if not os.path.exists(
        WIND_FILE
    ):

        raise FileNotFoundError(
            f"\nYlivieska wind file not found:\n"
            f"{WIND_FILE}\n\n"
            "Please update WIND_FILE at the top of the script."
        )

    monthly_wind_stats = (
        read_wind_data(
            WIND_FILE
        )
    )

    # ========================================================
    # PROCESS SCENARIOS
    # ========================================================

    for scenario in SCENARIOS:

        print()
        print(
            "===================================================="
        )
        print(
            f" PROCESSING: {scenario}"
        )
        print(
            "===================================================="
        )

        # ----------------------------------------------------
        # Input filename
        # ----------------------------------------------------

        input_file = os.path.join(
            WORK_DIR,
            (
                "sievi_daily_bias_corrected_"
                f"{scenario}.csv"
            )
        )

        if not os.path.exists(
            input_file
        ):

            print(
                f"WARNING: Input file not found:\n"
                f"{input_file}"
            )

            continue

        # ----------------------------------------------------
        # Read daily climate
        # ----------------------------------------------------

        df_daily = (
            read_daily_data(
                input_file
            )
        )

        # ----------------------------------------------------
        # Build hourly data
        # ----------------------------------------------------

        hourly = (
            build_hourly_data(
                df_daily,
                monthly_wind_stats
            )
        )

        # ----------------------------------------------------
        # Add scenario
        # ----------------------------------------------------

        hourly.insert(
            1,
            "scenario",
            scenario
        )

        # ----------------------------------------------------
        # Output filename
        # ----------------------------------------------------

        output_file = os.path.join(
            OUTPUT_DIR,
            (
                "sievi_final_hourly_penman_inputs_"
                f"{scenario}.csv"
            )
        )

        # ----------------------------------------------------
        # Save
        # ----------------------------------------------------

        hourly.to_csv(
            output_file,
            index=False
        )

        print()
        print(
            "Output saved:"
        )
        print(
            output_file
        )

        print(
            f"Number of hourly records: "
            f"{len(hourly):,}"
        )

        # ----------------------------------------------------
        # Validation
        # ----------------------------------------------------

        validate_hourly_output(
            hourly,
            scenario
        )

    # ========================================================
    # DONE
    # ========================================================

    print()
    print("====================================================")
    print(" ALL SCENARIOS COMPLETED")
    print("====================================================")


# ============================================================
# 22. RUN SCRIPT
# ============================================================

if __name__ == "__main__":

    main()
