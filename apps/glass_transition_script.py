import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

from backend.app.tools.GlassTransitionAnalysis import find_glass_transition


def load_dsc(file_path):
    df = pd.read_csv(file_path).dropna(subset=["temperature_C", "heat_flow_mW"])
    df = df.sort_values("temperature_C").reset_index(drop=True)
    return df["temperature_C"].to_numpy(), df["heat_flow_mW"].to_numpy()


# pylint: disable=invalid-name
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
    tg_value = analyze_glass_transition("backend/data/DSC_data9.csv")
    print(f"Calculated Glass Transition Temperature: {tg_value:.2f} °C")
