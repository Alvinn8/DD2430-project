"""Utilities for DSC glass-transition detection."""

from dataclasses import dataclass

import numpy as np
from scipy.signal import find_peaks, savgol_filter

SMOOTH_WINDOW_C = 1.5
TANGENT_HALF_WIDTH_C = 1.0
MIN_PROMINENCE_FRAC = 0.005
MIN_STEP_WIDTH_C = 3.0
MAX_STEP_WIDTH_C = 15.0


# pylint: disable=too-many-instance-attributes
@dataclass
class GlassTransition:
    """Result of a glass transition analysis."""

    tg: float  # half-width midpoint
    t_onset: float
    t_endset: float
    t_inflection: float
    hf_pre: float  # horizontal pre-transition baseline level
    hf_post: float  # horizontal post-transition baseline level
    t_pre: float  # temperature of the pre-baseline extremum
    t_post: float  # temperature of the post-baseline extremum
    slope: float
    intercept: float

    def step_hf(self, temperature):
        """Heat flow of the tangent through the inflection point."""
        return self.slope * np.asarray(temperature) + self.intercept


def _odd_window(width_c, T):
    """Convert a window width in deg C to an odd number of samples (>= 5)."""
    n = int(round(width_c / np.median(np.diff(T))))
    n = max(n, 5)
    return n if n % 2 == 1 else n + 1


def _find_step_candidates(HFs, prominence):
    """Return (i_max, i_min) index pairs for every maximum followed by a minimum."""
    maxima, _ = find_peaks(HFs, prominence=prominence)
    minima, _ = find_peaks(-HFs, prominence=prominence)
    pairs = []
    for i_max in maxima:
        later = minima[minima > i_max]
        if len(later) == 0:
            continue
        i_min = later[0]
        if np.any((maxima > i_max) & (maxima < i_min)):
            continue
        pairs.append((i_max, i_min))
    return pairs


# pylint: disable=invalid-name
def find_glass_transition(T, HF):
    """Locate and analyse the glass transition anywhere in the dataset.

    T and HF are arrays of temperature (sorted ascending, no NaN) and heat flow.

    The transition is identified as the most pronounced single falling edge
    (local maximum -> local minimum) whose temperature width lies between
    MIN_STEP_WIDTH_C and MAX_STEP_WIDTH_C. This rejects broad endotherms,
    narrow spikes/peaks and noise.
    """
    T = np.asarray(T, dtype=float)
    HF = np.asarray(HF, dtype=float)
    win = min(_odd_window(SMOOTH_WINDOW_C, T), len(T) - (len(T) % 2 == 0))
    HFs = savgol_filter(HF, window_length=win, polyorder=3)
    dHF = np.gradient(HFs, T)
    prominence = MIN_PROMINENCE_FRAC * np.ptp(HFs)

    candidates = [
        (i_pre, i_dip)
        for i_pre, i_dip in _find_step_candidates(HFs, prominence)
        if MIN_STEP_WIDTH_C <= T[i_dip] - T[i_pre] <= MAX_STEP_WIDTH_C
    ]
    if not candidates:
        raise ValueError("No glass transition step found in the data.")
    i_pre, i_post = max(candidates, key=lambda ij: HFs[ij[0]] - HFs[ij[1]])

    i_infl = i_pre + np.argmin(dHF[i_pre : i_post + 1])
    T_infl = T[i_infl]

    fit = np.abs(T - T_infl) <= TANGENT_HALF_WIDTH_C
    slope, intercept = np.polyfit(T[fit], HF[fit], 1)

    hf_pre, hf_post = HFs[i_pre], HFs[i_post]
    t_ons = (hf_pre - intercept) / slope
    t_end = (hf_post - intercept) / slope
    if not t_ons < t_end:
        raise ValueError(
            "Onset/endset intersections are inconsistent; adjust settings."
        )

    return GlassTransition(
        tg=(t_ons + t_end) / 2,
        t_onset=t_ons,
        t_endset=t_end,
        t_inflection=T_infl,
        hf_pre=hf_pre,
        hf_post=hf_post,
        t_pre=T[i_pre],
        t_post=T[i_post],
        slope=slope,
        intercept=intercept,
    )
