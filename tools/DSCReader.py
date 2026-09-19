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
