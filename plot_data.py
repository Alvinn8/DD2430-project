import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
from tools.DSCReader import read_dsc_file
from tools.MeltingPointAnalysis import find_break_points, find_intersection


def main(**kwargs):
    data = read_dsc_file("data/DSC_data4.csv")

    threshold_multiplier = kwargs.get("threshold_multiplier", 0.3)
    search_window_fraction = kwargs.get("search_window_fraction", 0.3)

    start_plateau_index, end_of_plateau_index, start_decline_index, valley_min_idx = (
        find_break_points(
            data, threshold_multiplier, search_window_fraction=search_window_fraction
        )
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
