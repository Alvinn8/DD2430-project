import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from scipy.signal import find_peaks, savgol_filter
from dataclasses import dataclass

SMOOTH_WINDOW_C = 1.5
TANGENT_HALF_WIDTH_C = 1.0
MIN_PROMINENCE_FRAC = 0.005
MIN_STEP_WIDTH_C = 3.0
MAX_STEP_WIDTH_C = 15.0


@dataclass
class GlassTransition:
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
        return self.slope * np.asarray(temperature) + self.intercept


def load_dsc(file_path):
    df = pd.read_csv(file_path).dropna(subset=["temperature_C", "heat_flow_mW"])
    df = df.sort_values("temperature_C").reset_index(drop=True)
    return df["temperature_C"].to_numpy(), df["heat_flow_mW"].to_numpy()


def _odd_window(width_c, T):
    """Convert a window width in deg C to an odd number of samples (>= 5)."""
    n = int(round(width_c / np.median(np.diff(T))))
    n = max(n, 5)
    return n if n % 2 == 1 else n + 1


def _find_step_candidates(T, HFs, prominence):
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


def find_glass_transition(T, HF):
    """Locate and analyse the glass transition anywhere in the dataset.

    The transition is identified as the most pronounced single falling edge
    (local maximum -> local minimum) whose temperature width lies between
    MIN_STEP_WIDTH_C and MAX_STEP_WIDTH_C. This rejects broad endotherms,
    narrow spikes/peaks and noise.
    """
    win = min(_odd_window(SMOOTH_WINDOW_C, T), len(T) - (len(T) % 2 == 0))
    HFs = savgol_filter(HF, window_length=win, polyorder=3)
    dHF = np.gradient(HFs, T)
    prominence = MIN_PROMINENCE_FRAC * np.ptp(HFs)

    candidates = [
        (i_pre, i_dip)
        for i_pre, i_dip in _find_step_candidates(T, HFs, prominence)
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


def plot_glass_transition(T, HF, gt):
    """Plot the whole dataset with baselines, step line, onset/endset and Tg."""
    pad = 0.25 * (gt.t_endset - gt.t_onset) + 3
    fig, ax = plt.subplots(figsize=(11, 6))
    ax.plot(T, HF, color="black", lw=1.5, label="DSC raw data")

    t_pre = np.array([gt.t_pre - 12, gt.t_onset + pad])
    t_post = np.array([gt.t_endset - pad, gt.t_post + 12])
    t_step = np.array([gt.t_onset - pad, gt.t_endset + pad])

    ax.plot(t_pre, [gt.hf_pre] * 2, "--", color="blue", label="Pre-transition baseline")
    ax.plot(
        t_post, [gt.hf_post] * 2, "--", color="green", label="Post-transition baseline"
    )
    ax.plot(t_step, gt.step_hf(t_step), "--", color="orange", label="Angled step line")

    ax.scatter(
        [gt.t_onset, gt.t_endset],
        [gt.hf_pre, gt.hf_post],
        color="gray",
        zorder=4,
        label="Onset / Endset",
    )
    ax.scatter(
        [gt.tg],
        [gt.step_hf(gt.tg)],
        color="red",
        s=80,
        zorder=5,
        label=f"Tg (half-width) = {gt.tg:.2f} °C",
    )

    ax.set(
        title="Glass Transition Analysis by DSC",
        xlabel="Temperature (°C)",
        ylabel="Heat Flow (mW)",
    )
    ax.grid(True, linestyle=":", alpha=0.6)
    ax.legend(loc="lower center", bbox_to_anchor=(0.68, 0.02))
    fig.tight_layout()
    plt.show()


def analyze_glass_transition(file_path):
    T, HF = load_dsc(file_path)
    gt = find_glass_transition(T, HF)
    plot_glass_transition(T, HF, gt)
    return gt.tg


if __name__ == "__main__":
    tg_value = analyze_glass_transition("../backend/data/DSC_data9.csv")
    print(f"Calculated Glass Transition Temperature: {tg_value:.2f} °C")
