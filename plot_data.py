import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
from scipy.ndimage import uniform_filter1d


def find_intersection(m1, b1, m2, b2):
    if np.isclose(m1, m2):
        raise ValueError("Lines are parallel and do not intersect.")

    x_intersect = (b2 - b1) / (m1 - m2)
    y_intersect = m1 * x_intersect + b1

    return x_intersect, y_intersect


def find_break_points(
    data, threshold_multiplier=0.3, smoothing_window=5, search_window_fraction=0.3
):
    valley_min_idx = data["HeatFlow"].idxmin()
    left_df = data.loc[:valley_min_idx].copy()

    left_df = left_df.drop_duplicates(subset="Temperature", keep="first")

    left_df["dy"] = left_df["HeatFlow"].diff()
    left_df["dx"] = left_df["Temperature"].diff()
    left_df["slope"] = left_df["dy"] / left_df["dx"]

    left_df["slope"] = left_df["slope"].bfill()

    left_df["slope_smooth"] = uniform_filter1d(
        left_df["slope"].values, size=smoothing_window, mode="nearest"
    )

    assert np.isfinite(
        left_df["slope_smooth"]
    ).all(), (
        "Non-finite slope values remain -- check for NaN/Inf in HeatFlow or Temperature"
    )

    n = len(left_df)
    slope_values = left_df["slope_smooth"].values

    window_start = int(n * (1 - search_window_fraction))
    window_slice = slope_values[window_start:]
    steepest_pos = window_start + int(np.argmin(window_slice))
    min_slope = slope_values[steepest_pos]

    rapid_threshold = min_slope * threshold_multiplier

    print(
        f"Search window: last {search_window_fraction*100:.0f}% of points "
        f"(rows {window_start} to {n - 1})"
    )
    print(f"Minimum slope in window: {min_slope:.6f}")
    print(f"Threshold (multiplier={threshold_multiplier}): {rapid_threshold:.6f}")

    is_steep = slope_values <= rapid_threshold

    pos = steepest_pos
    while pos >= 0 and is_steep[pos]:
        pos -= 1
    start_decline = pos + 1

    last_slope = slope_values[pos + 1]
    while pos >= 0 and np.isclose(slope_values[pos], last_slope, rtol=1):
        pos -= 1
    start_plateau = pos + 1

    start_decline = max(0, min(start_decline, n - 1))
    start_decline_index = left_df.index[start_decline]

    start_plateau = max(0, min(start_plateau, n - 1))
    start_plateau_index = left_df.index[start_plateau]

    print(f"Start of decline index (original data): {start_decline_index}")
    print(
        f"Start of decline temperature: {data.loc[start_decline_index, 'Temperature']:.2f}°C"
    )
    print(f"Start of plateau index (original data): {start_plateau_index}")
    print(
        f"Start of plateau temperature: {data.loc[start_plateau_index, 'Temperature']:.2f}°C"
    )
    print()

    return start_plateau_index, start_decline_index, valley_min_idx, left_df


def main(**kwargs):
    data = pd.read_csv("data/GRIS - N125-180 x10.csv", encoding="utf-16")

    threshold_multiplier = kwargs.get("threshold_multiplier", 0.3)
    search_window_fraction = kwargs.get("search_window_fraction", 0.3)

    start_plateau_index, start_decline_index, valley_min_idx, analysis_df = (
        find_break_points(
            data, threshold_multiplier, search_window_fraction=search_window_fraction
        )
    )

    rapid_decline_df = data.loc[start_decline_index:valley_min_idx].copy()
    plateau_df = data.loc[start_plateau_index:start_decline_index].copy()

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

    print(f"Valley minimum at index: {valley_min_idx}")
    print(f"Rapid decline starts at index: {start_decline_index}")
    print(
        f"Temperature at the start of rapid decline: {data.loc[start_decline_index, 'Temperature']:.2f}°C"
    )
    print(
        f"Temperature at the start of plateau: {data.loc[start_plateau_index, 'Temperature']:.2f}°C"
    )
    print(
        f"Heat flow at the start of rapid decline: {data.loc[start_decline_index, 'HeatFlow']:.2f} mW"
    )
    print(
        f"Heat flow at the start of plateau: {data.loc[start_plateau_index, 'HeatFlow']:.2f} mW"
    )
    print(
        f"Intersection of extrapolated (melting point) lines at: ({x_int:.2f}°C, {y_int:.2f} mW)"
    )
    print()

    plt.figure(figsize=(12, 7))
    plt.plot(
        data["Temperature"],
        data["HeatFlow"],
        label="DSC Data",
        color="black",
        linewidth=2,
    )
    plt.plot(
        rapid_decline_df["Temperature"],
        rapid_decline_df["HeatFlow"],
        "r-",
        linewidth=3,
        label="Rapid Decline",
    )
    plt.plot(
        plateau_df["Temperature"],
        plateau_df["HeatFlow"],
        "g-",
        linewidth=3,
        label="Plateau",
    )
    plt.scatter(
        np.array([data.loc[start_decline_index, "Temperature"]]),
        np.array([data.loc[start_decline_index, "HeatFlow"]]),
        color="red",
        s=150,
        zorder=5,
        label="Detected Decline Start",
        edgecolors="darkred",
        linewidths=2,
    )
    plt.scatter(
        np.array([data.loc[start_plateau_index, "Temperature"]]),
        np.array([data.loc[start_plateau_index, "HeatFlow"]]),
        color="green",
        s=150,
        zorder=5,
        label="Detected Plateau Start",
        edgecolors="darkgreen",
        linewidths=2,
    )

    plt.xlabel("Temperature (°C)", fontsize=12)
    plt.ylabel("Heat Flow (mW)", fontsize=12)
    plt.title(
        f"DSC Data with Detected Rapid Decline (threshold={threshold_multiplier}, window={search_window_fraction})",
        fontsize=13,
    )
    plt.legend(fontsize=11)
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.show()

    plt.figure(figsize=(12, 7))

    plt.plot(
        data["Temperature"],
        data["HeatFlow"],
        label="DSC Data",
        color="black",
        linewidth=2,
    )

    plt.plot(
        data["Temperature"],
        full_baseline_y,
        "b--",
        linewidth=2,
        label=f"Extrapolated Plateau Line\n(y = {slope:.4f}x + {intercept:.2f})",
    )

    plt.plot(
        data["Temperature"],
        full_rapid_decline_y,
        "r--",
        linewidth=2,
        label=f"Extrapolated Decline Line\n(y = {rapid_decline_slope:.4f}x + {rapid_decline_intercept:.2f})",
    )

    plt.scatter(
        np.array([x_int]),
        np.array([y_int]),
        color="blue",
        s=150,
        zorder=5,
        label="Detected Melting Point",
        edgecolors="darkblue",
        linewidths=2,
    )

    plt.xlabel("Temperature (°C)", fontsize=12)
    plt.ylabel("Heat Flow (mW)", fontsize=12)
    plt.title("Plateau Linear Fit Extrapolated Across Entire DSC Dataset", fontsize=13)
    plt.legend(fontsize=11)
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
    main(threshold_multiplier=0.5, search_window_fraction=0.4)
