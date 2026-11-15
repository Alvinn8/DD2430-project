"""Utilities for DSC enthalpy-of-fusion (and other peak enthalpy) analysis."""

# pylint: disable=invalid-name,too-many-arguments,too-many-locals
# pylint: disable=too-many-positional-arguments

from __future__ import annotations

import numpy as np
from matplotlib.figure import Figure
from scipy.integrate import cumulative_trapezoid, trapezoid
from scipy.optimize import curve_fit
from scipy.signal import find_peaks, peak_widths, savgol_filter
from scipy.special import erf, erfcx

SMOOTH_WINDOW_C = 1.0


# DSC_N(T) models (Ghanbari et al. paper Eqs. 16-20)
def peak_shape(T, Tm, alpha, beta):
    """Unit-area peak: (a/2) e^{a^2/4b} e^{a dT} erfc(sqrt(b)(dT + a/2b)).

    Written with the scaled complementary error function so that the product of
    the huge exponential and the tiny erfc never overflows.
    """
    d = np.asarray(T, dtype=float) - Tm
    sb = np.sqrt(beta)
    u = alpha / (2.0 * sb)
    v = sb * d
    x = u + v
    with np.errstate(over="ignore", invalid="ignore"):
        regular = 0.5 * alpha * erfcx(np.maximum(x, -20.0)) * np.exp(-v * v)
        # erfc(x) -> 2 for x << 0, giving the pure exponential rising edge
        tail = alpha * np.exp(u * u + 2.0 * u * v)
    return np.where(x < -20.0, tail, regular)


def step_shape(T, Tm, alpha, beta):
    """Cumulative of the peak, going from 0 (pre-transition) to 1 (post-transition).

    Closed form: peak/alpha + (1 + erf(sqrt(b) dT)) / 2 (equals paper Eq. 19 / dCp).
    """
    d = np.asarray(T, dtype=float) - Tm
    return peak_shape(T, Tm, alpha, beta) / alpha + 0.5 * (1.0 + erf(np.sqrt(beta) * d))


def baseline_n(T, Tm, alpha, beta, dCp, B, C, D):
    """Baseline of Eq. 20: heat-capacity step plus offset, slope and curvature."""
    d = np.asarray(T, dtype=float) - Tm
    return dCp * step_shape(T, Tm, alpha, beta) + B + C * d + D * d**2


def dsc_n(T, dH, Tm, alpha, beta, dCp, B, C, D):
    """DSC_N(T), Eq. 20 of the paper (single peak)."""
    return dH * peak_shape(T, Tm, alpha, beta) + baseline_n(
        T, Tm, alpha, beta, dCp, B, C, D
    )


# Helper functions for the DSC_N(T) fit
def _odd_window(width_c, T):
    """Convert a window width in deg C to an odd number of samples (>= 5)."""
    dt = float(np.median(np.diff(T)))
    if dt <= 0:
        raise ValueError("Temperature must be strictly increasing.")
    n = max(int(round(width_c / dt)), 5)
    return n if n % 2 == 1 else n + 1


def _smooth(T, y):
    n = len(T)
    if n < 5:
        raise ValueError("Too few data points (need at least 5).")
    win = min(_odd_window(SMOOTH_WINDOW_C, T), n if n % 2 == 1 else n - 1)
    return np.asarray(
        savgol_filter(y, window_length=win, polyorder=min(3, win - 1)), dtype=float
    )
