"""Reader utilities for DSC input data files."""

# pylint: disable=invalid-name

import pandas as pd


def read_dsc_file(file_path):
    """
    Reads a DSC data file and returns a pandas DataFrame with the relevant columns.

    Parameters:
    - file_path: str, path to the DSC data file.

    Returns:
    - df: pandas DataFrame containing the Temperature and HeatFlow columns.
    """
    df = pd.read_csv(file_path, encoding="utf-16")

    return df


REQUIRED_COLUMNS = ("temperature_C", "heat_flow_mW")


def read_standardized_dsc_file(file_path):
    """
    Reads a DSC data file in the standardized format.

    Parameters:
    - file_path: str, path to the .csv data file with the columns
      time_min, temperature_C and heat_flow_mW.

    Returns:
    - df: pandas DataFrame with the three columns. Missing values are NaN.
    """
    df = pd.read_csv(file_path)
    missing = [column for column in REQUIRED_COLUMNS if column not in df.columns]
    if missing:
        raise ValueError(
            f"missing columns {missing} (found {list(df.columns)}); "
            "this is not a standardized DSC data file"
        )
    return df


def read_standardized_dsc_metadata(file_path):
    """
    Reads the metadata belonging to a standardized DSC data file, if it exists.

    Parameters:
    - file_path: str, path to the .csv data file. The metadata is read from
      the file with the same name ending in _metadata.csv.

    Returns:
    - metadata: dict with the metadata columns, or None if there is no metadata file.
    """
    metadata_path = file_path.removesuffix(".csv") + "_metadata.csv"
    try:
        df = pd.read_csv(metadata_path)
    except FileNotFoundError:
        return None
    return df.iloc[0].to_dict()
