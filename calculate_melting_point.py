"""Run DSC-based melting point analysis from a local CSV file."""

from tools.DSCReader import read_dsc_file
from tools.MeltingPointAnalysis import analyze_dsc_data


def main(**kwargs):
    """Read DSC input data and run melting point analysis."""
    data = read_dsc_file("data/DSC_data3.csv")

    smoothing_window = kwargs.get("smoothing_window", 11)

    analyze_dsc_data(data, smoothing_window=smoothing_window)


if __name__ == "__main__":
    main(threshold_multiplier=0.5, search_window_fraction=0.4)
