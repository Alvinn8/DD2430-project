import matplotlib.pyplot as plt
import numpy as np
from scipy.signal import savgol_filter


def find_break_points(data, smoothing_window=11) -> tuple[int, int, int, int]:
    """
    Find the start and end indices of the plateau and rapid decline regions in DSC data.
    Arguments:
    - data: DataFrame containing 'Temperature' and 'HeatFlow' columns.
    - smoothing_window: Window length for Savitzky-Golay filter (must be odd).
    Returns:
    - start_plateau_index: Index where the plateau starts.
    - end_of_plateau_index: Index where the plateau ends.
    - start_decline_index: Index where the rapid decline starts.
    - valley_min_idx: Index of the minimum heat flow (valley).
    """
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


def find_intersection(slope1, intercept1, slope2, intercept2) -> tuple[float, float]:
    """
    Find the intersection point of two lines defined by their slopes and intercepts.
    Arguments:
    - slope1, intercept1: Slope and intercept of the first line.
    - slope2, intercept2: Slope and intercept of the second line.
    Returns:
    - x_int, y_int: Coordinates of the intersection point.
    Raises:
    - ValueError: If the lines are parallel and do not intersect.
    """
    if slope1 == slope2:
        raise ValueError("Lines are parallel and do not intersect.")
    x_int = (intercept2 - intercept1) / (slope1 - slope2)
    y_int = slope1 * x_int + intercept1
    return x_int, y_int


def linear_fit(x, y) -> tuple[float, float]:
    """
    Perform a linear fit to the given x and y data.
    Arguments:
    - x: Independent variable data.
    - y: Dependent variable data.
    Returns:
    - slope, intercept: Parameters of the fitted line.
    """
    slope, intercept = np.polyfit(x, y, 1)
    return slope, intercept


def analyze_dsc_data(data, smoothing_window=11):
    """
    Analyze DSC data to find the melting point and plot the results.
    Arguments:
    - data: DataFrame containing 'Temperature' and 'HeatFlow' columns.
    - smoothing_window: Window length for Savitzky-Golay filter (must be odd).
    """
    start_plateau_index, end_of_plateau_index, start_decline_index, valley_min_idx = (
        find_break_points(data, smoothing_window)
    )

    rapid_decline_df = data.loc[start_decline_index:valley_min_idx].copy()
    plateau_df = data.loc[start_plateau_index:end_of_plateau_index].copy()

    clean_plateau = plateau_df.dropna(subset=["Temperature", "HeatFlow"])
    slope, intercept = np.polyfit(
        clean_plateau["Temperature"], clean_plateau["HeatFlow"], 1
    )

    clean_rapid_decline = rapid_decline_df.dropna(subset=["Temperature", "HeatFlow"])
    rapid_decline_slope, rapid_decline_intercept = np.polyfit(
        clean_rapid_decline["Temperature"], clean_rapid_decline["HeatFlow"], 1
    )

    full_baseline_y = slope * data["Temperature"] + intercept
    full_rapid_decline_y = (
        rapid_decline_slope * data["Temperature"] + rapid_decline_intercept
    )

    x_int, y_int = find_intersection(
        slope, intercept, rapid_decline_slope, rapid_decline_intercept
    )

    print(f"Detected Melting Point: {x_int:.2f} °C, Heat Flow: {y_int:.2f} mW")
