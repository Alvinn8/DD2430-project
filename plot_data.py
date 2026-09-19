import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
from tools.DSCReader import read_dsc_file
from tools.MeltingPointAnalysis import find_break_points, analyze_dsc_data


def main(**kwargs):
    data = read_dsc_file("data/DSC_data4.csv")

    smoothing_window = kwargs.get("smoothing_window", 11)

    analyze_dsc_data(data, smoothing_window=smoothing_window)


if __name__ == "__main__":
    main(threshold_multiplier=0.5, search_window_fraction=0.4)
