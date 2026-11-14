"""Utilities for DSC heating rate calculations and analysis."""

# pylint: disable=invalid-name

import numpy as np
from matplotlib.figure import Figure


def calculate_heating_rate(
    temperature_data: np.ndarray, time_data: np.ndarray
) -> np.ndarray:
    """
    Calculate the heating rate from temperature and time data assuming linear heating,
    least squares fit.

    Args:
        temperature_data (np.ndarray): Array of temperature values (°C).
        time_data (np.ndarray): Array of time values (s).

    Returns:
        np.ndarray: Array of heating rates (°C/s).
    """
    # Ensure the input arrays are numpy arrays
    temperature_data = np.asarray(temperature_data)
    time_data = np.asarray(time_data)

    # Perform linear regression
    A = np.vstack([time_data, np.ones(len(time_data))]).T
    m, _ = np.linalg.lstsq(A, temperature_data, rcond=None)[0]
    return m


def plot_heating_rate(temperature_data: np.ndarray, time_data: np.ndarray) -> Figure:
    """
    Plot the temperature vs. time data and the linear fit representing the heating rate.

    Args:
        temperature_data (np.ndarray): Array of temperature values (°C).
        time_data (np.ndarray): Array of time values (s).
    """
    # Calculate the heating rate
    heating_rate = calculate_heating_rate(temperature_data, time_data)

    # Create a linear fit line
    fit_line = heating_rate * time_data + np.mean(
        temperature_data - heating_rate * time_data
    )

    # Plotting
    figure = Figure(figsize=(8, 5), dpi=100)
    ax = figure.add_subplot()
    ax.plot(time_data, temperature_data, label="Temperature Data", color="blue")
    ax.plot(
        time_data,
        fit_line,
        label=f"Linear Fit (Heating Rate: {heating_rate:.2f} °C/s)",
        color="red",
        linestyle="--",
    )
    ax.set_xlabel("Time")
    ax.set_ylabel("Temperature (°C)")
    ax.set_title("Heating Rate Calculation")
    ax.legend()
    ax.grid()
    return figure
