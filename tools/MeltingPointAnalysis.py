import matplotlib.pyplot as plt
import numpy as np
from scipy.signal import savgol_filter


def find_break_points(
    data, threshold_multiplier=0.3, smoothing_window=11, search_window_fraction=0.3
):
    data = data.sort_values("Temperature").reset_index(drop=True)

    valley_min_idx = data["HeatFlow"].idxmin()
    peak_max_idx = data["HeatFlow"].idxmax()

    start_plateau_index = 0
    end_of_plateau_index = 0
    start_decline_index = 0
    end_of_decline_index = valley_min_idx

    # Ensure window length is odd and valid
    window_length = max(
        smoothing_window if smoothing_window % 2 != 0 else smoothing_window + 1, 5
    )

    # Calculate 2nd derivative using Savitzky-Golay filter to prevent noise explosion
    # polyorder=3 allows capturing curved peaks while smoothing
    dT = np.mean(np.diff(data["Temperature"].values))
    smoothed_1st_deriv = savgol_filter(
        data["HeatFlow"].values,
        window_length=window_length,
        polyorder=3,
        deriv=1,
        delta=dT,
    )
    smoothed_2nd_deriv = savgol_filter(
        data["HeatFlow"].values,
        window_length=window_length,
        polyorder=3,
        deriv=2,
        delta=dT,
    )
    data["first_derivative"] = smoothed_1st_deriv
    data["second_derivative"] = smoothed_2nd_deriv

    if peak_max_idx < valley_min_idx:
        for idx in range(peak_max_idx, valley_min_idx + 1):
            if 0 < data.iloc[idx]["second_derivative"] < 1e-1:
                start_plateau_index = data.index[idx]
                break

    for idx in range(valley_min_idx - 1, 0, -1):
        if 0 > data.iloc[idx]["second_derivative"] > -1e-1:
            start_decline_index = data.index[idx]
            break

    stdev = np.std(
        data[start_plateau_index:start_decline_index]["first_derivative"].values
    )
    mean = np.mean(
        data[start_plateau_index:start_decline_index]["first_derivative"].values
    )
    print(f"Mean of first derivative: {mean}")
    print(f"Standard deviation of first derivative: {stdev}")

    # Determine the end of the plateau region
    for idx in range(start_plateau_index + 1, start_decline_index):
        if np.abs(data.iloc[idx]["first_derivative"] - mean) >= stdev:
            end_of_plateau_index = data.index[idx]
            break

    print(f"Valley min index: {valley_min_idx}")
    print(f"Peak max index: {peak_max_idx}")
    print(f"Start plateau index: {start_plateau_index}")
    print(f"Start decline index: {start_decline_index}")
    print(f"End of plateau index: {end_of_plateau_index}")
    print(f"End of decline index: {end_of_decline_index}")

    return (
        start_plateau_index,
        end_of_plateau_index,
        start_decline_index,
        valley_min_idx,
    )


def find_intersection(slope1, intercept1, slope2, intercept2):
    if slope1 == slope2:
        raise ValueError("Lines are parallel and do not intersect.")
    x_int = (intercept2 - intercept1) / (slope1 - slope2)
    y_int = slope1 * x_int + intercept1
    return x_int, y_int
