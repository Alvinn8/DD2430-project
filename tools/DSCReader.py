"""Reader utilities for DSC input data files."""

# pylint: disable=invalid-name

import re

import pandas as pd


def read_dsc_file(file_path):
    """
    Read a DSC CSV and return Temperature/HeatFlow columns for existing analysis code.

    Parameters:
    - file_path: Path or str, path to the DSC data file.

    Returns:
    - df: DataFrame with numeric Temperature and HeatFlow columns.
    """
    errors = []
    df = None
    for encoding in ("utf-8-sig", "utf-16", "cp1252"):
        try:
            df = pd.read_csv(file_path, encoding=encoding, sep=None, engine="python")
            break
        except (UnicodeError, pd.errors.ParserError) as error:
            errors.append(error)
    if df is None:
        raise ValueError(f"Could not read DSC CSV {file_path}: {errors[-1]}")

    normalized_columns = {
        re.sub(r"[^a-z0-9]", "", str(column).casefold()): column
        for column in df.columns
    }
    temperature_column = next(
        (normalized_columns[name] for name in ("temperaturec", "temperature", "temp")
         if name in normalized_columns),
        None,
    )
    heat_flow_column = next(
        (normalized_columns[name] for name in ("heatflowmw", "heatflow", "dsc")
         if name in normalized_columns),
        None,
    )
    if temperature_column is None or heat_flow_column is None:
        raise ValueError(
            "DSC CSV must contain temperature_C and heat_flow_mW columns "
            "(or legacy Temperature and HeatFlow columns)."
        )

    df = df.rename(columns={temperature_column: "Temperature", heat_flow_column: "HeatFlow"})
    df["Temperature"] = pd.to_numeric(df["Temperature"], errors="coerce")
    df["HeatFlow"] = pd.to_numeric(df["HeatFlow"], errors="coerce")
    df = df.dropna(subset=["Temperature", "HeatFlow"]).reset_index(drop=True)
    if df.empty:
        raise ValueError(
            "No rows contain both temperature and heat flow in mW. "
            "Check the metadata file for missing mass or conversion notes."
        )

    return df
