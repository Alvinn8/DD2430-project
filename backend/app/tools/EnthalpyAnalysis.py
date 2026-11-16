"""Utilities for DSC enthalpy-of-fusion (and other peak enthalpy) analysis."""

# pylint: disable=invalid-name,too-many-arguments,too-many-locals
# pylint: disable=too-many-positional-arguments
# pylint: disable=no-name-in-module,unsubscriptable-object
# pylint: disable=invalid-name,too-many-statements

from __future__ import annotations
import warnings

import numpy as np
from matplotlib.figure import Figure
from scipy.integrate import trapezoid
from scipy.optimize import curve_fit
from scipy.signal import peak_widths, savgol_filter
from scipy.special import erf, erfcx
from app.models import EnthalpyFit, EnthalpyResult

SMOOTH_WINDOW_C = 1.0
MIN_WINDOW_POINTS = 15
EDGE_FRACTION = 0.03
WINDOW_MARGIN = 5.0
MIN_EXTENT_SAMPLES = 10
MIN_R2 = 0.97
MAX_AGREEMENT_PCT = 10.0
DECOMP_FRACTION = 0.3
PARAM_NAMES = ("dH", "Tm", "alpha", "beta", "dCp", "B", "C", "D")
ALPHA_STARTS = (0.05, 0.5, 2.0, 8.0)
BETA_STARTS = (0.05, 1.0, 10.0, 50.0)


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


def _edge_count(n):
    return max(3, int(round(EDGE_FRACTION * n)))


def select_peak_window(T, y, t_min=None, t_max=None):
    """Find the dominant upward peak and a window around it.

    Args:
        T, y: sorted temperature and heat flow with the event pointing UP.
        t_min, t_max: optional search range (use t_max to stop before a
            decomposition exotherm that follows the melt).

    Returns:
        (t_start, t_end, t_peak)
    """
    T = np.asarray(T, dtype=float)
    y = np.asarray(y, dtype=float)

    lo = T[0] if t_min is None else float(t_min)
    hi = T[-1] if t_max is None else float(t_max)

    mask = (T >= lo) & (T <= hi)

    if mask.sum() < MIN_WINDOW_POINTS:
        raise ValueError(f"Fewer than {MIN_WINDOW_POINTS} points in [{lo}, {hi}] °C.")

    Ts = T[mask]
    ys = _smooth(T, y)[mask]

    k = _edge_count(len(Ts))
    line = np.interp(Ts, [Ts[0], Ts[-1]], [ys[:k].mean(), ys[-k:].mean()])
    excess = ys - line

    # index of the maximum excess (heat flow peak)
    ip = int(np.argmax(excess))
    height = float(excess[ip])

    noise = float(np.std(y[mask] - ys))

    if ip in (0, len(Ts) - 1) or height <= 0 or height < 5 * noise:
        raise ValueError(
            "No clear peak found in the search range. Check the sign convention "
            "(endo up/down) and the temperature range."
        )

    _, _, l_ips, r_ips = peak_widths(excess, [ip], rel_height=0.5)
    idx = np.arange(len(Ts))

    t_left = float(np.interp(l_ips[0], idx, Ts))
    t_right = float(np.interp(r_ips[0], idx, Ts))
    t_peak = float(Ts[ip])

    dt = float(np.median(np.diff(Ts)))

    ext_l = max(WINDOW_MARGIN * (t_peak - t_left), MIN_EXTENT_SAMPLES * dt)
    ext_r = max(WINDOW_MARGIN * (t_right - t_peak), MIN_EXTENT_SAMPLES * dt)

    return max(t_peak - ext_l, Ts[0]), min(t_peak + ext_r, Ts[-1]), t_peak


def _tangent_crossing(T, ys, base, i0, direction):
    """Intersection of the tangent at index i0 with the baseline (None if absent)."""
    slope = np.gradient(ys, T)[i0]
    g = ys[i0] + slope * (T - T[i0]) - base
    rng = range(i0, 0, -1) if direction < 0 else range(i0, len(T) - 1)
    for j in rng:
        k = j - 1 if direction < 0 else j + 1
        if g[j] * g[k] <= 0 and g[j] != g[k]:
            return float(T[j] + (0.0 - g[j]) * (T[k] - T[j]) / (g[k] - g[j]))
    return None


def _tangent_onset_endset(T, ys, base, ip):
    """Extrapolated onset/endset: steepest-edge tangents meet the baseline."""
    if ip < 2 or ip > len(T) - 3:
        return None, None
    dy = np.gradient(ys, T)
    ir = int(np.argmax(dy[: ip + 1]))
    jf = ip + int(np.argmin(dy[ip:]))
    return (
        _tangent_crossing(T, ys, base, ir, -1),
        _tangent_crossing(T, ys, base, jf, +1),
    )


def fit_dsc_n(T, y, heating_rate, fit_dcp=True) -> EnthalpyFit:
    """Fit DSC_N(T) (paper Eq. 20) to a peak window with the event pointing up.

    Args:
        T: temperature (deg C), ascending.
        y: heat flow in W/g.
        heating_rate: heating rate used to convert area to J/g.
        fit_dcp: fit the heat-capacity step. The paper calls it "not very
            accurate"; set False to fix it to zero.
    """
    T = np.asarray(T, dtype=float)
    y = np.asarray(y, dtype=float)

    width = float(T[-1] - T[0])

    ptp = float(np.ptp(y)) or 1.0
    k = _edge_count(len(T))

    yl, yr = float(y[:k].mean()), float(y[-k:].mean())

    line = np.interp(T, [T[0], T[-1]], [yl, yr])
    area0 = float(trapezoid(y - line, T))

    # index and value of peak temperature
    ip = int(np.argmax(y - line))
    Tp = float(T[ip])

    lo = np.array(
        [
            0.0,
            T[0],
            1e-2,
            1e-3,
            -2 * ptp,
            y.min() - ptp,
            -10 * ptp / width,
            -50 * ptp / width**2,
        ]
    )
    hi = np.array(
        [
            10 * ptp * width,
            T[-1],
            1e2,
            1e3,
            2 * ptp,
            y.max() + ptp,
            10 * ptp / width,
            50 * ptp / width**2,
        ]
    )
    dH0 = area0 if area0 > 0 else 0.05 * ptp * width
    B0 = float(np.interp(Tp, [T[0], T[-1]], [yl, yr]))
    C0 = (yr - yl) / width

    free = np.array([i for i, n in enumerate(PARAM_NAMES) if fit_dcp or n != "dCp"])
    fixed = np.zeros(len(PARAM_NAMES))

    def model(Tv, *p):
        full = fixed.copy()
        full[free] = p
        return dsc_n(Tv, *full)

    # grid search
    best = None
    for a0 in ALPHA_STARTS:
        for b0 in BETA_STARTS:
            p0 = np.clip(np.array([dH0, Tp, a0, b0, 0.0, B0, C0, 0.0]), lo, hi)
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    popt, pcov = curve_fit(
                        model,
                        T,
                        y,
                        p0=p0[free],
                        bounds=(lo[free], hi[free]),
                        method="trf",
                        x_scale="jac",
                        max_nfev=2000,
                    )
            except (RuntimeError, ValueError):
                continue

            # Sum of squared residuals (SSR) for this fit
            ssr = float(np.sum((y - model(T, *popt)) ** 2))
            if best is None or ssr < best[0]:
                best = (ssr, popt, pcov)
    if best is None:
        raise ValueError("DSC_N(T) fit did not converge from any starting point.")

    ssr, popt, pcov = best
    p = fixed.copy()
    p[free] = popt
    err = np.zeros(len(PARAM_NAMES))
    with np.errstate(invalid="ignore"):
        err[free] = np.sqrt(np.diag(pcov))
    err[~np.isfinite(err)] = np.nan
    sst = float(np.sum((y - y.mean()) ** 2))
    r2 = 1.0 - ssr / sst if sst > 0 else 0.0

    problems: list[str] = []
    if r2 < MIN_R2:
        problems.append(f"R² = {r2:.3f} is below {MIN_R2}")

    def _at_bound(i):
        # alpha and beta span decades, so compare them on a log scale
        if PARAM_NAMES[i] in ("alpha", "beta"):
            val, lo_i, hi_i = np.log(p[i]), np.log(lo[i]), np.log(hi[i])
            tol = 1e-2 * (hi_i - lo_i)
        else:
            val, lo_i, hi_i = p[i], lo[i], hi[i]
            tol = 1e-3 * (hi_i - lo_i)
        return min(val - lo_i, hi_i - val) <= tol

    pinned = [PARAM_NAMES[i] for i in free if _at_bound(i)]
    if pinned:
        problems.append("parameters at their bounds: " + ", ".join(pinned))
    if not (np.isfinite(err[0]) and np.isfinite(err[1])):
        problems.append("covariance of dH/Tm could not be estimated")

    Tg = np.linspace(T[0], T[-1], 4000)
    curve_g = dsc_n(Tg, *p)
    base_g = baseline_n(Tg, *p[1:])
    ipg = int(np.argmax(curve_g - base_g))
    onset, endset = _tangent_onset_endset(Tg, curve_g, base_g, ipg)

    return EnthalpyFit(
        params=dict(zip(PARAM_NAMES, map(float, p))),
        errors=dict(zip(PARAM_NAMES, map(float, err))),
        dH_J_per_g=float(p[0] / heating_rate),
        dH_J_per_g_err=float(err[0] / heating_rate),
        Tm0=float(p[1]),
        Tm0_err=float(err[1]),
        r_squared=r2,
        t_peak=float(Tg[ipg]),
        t_onset=onset,
        t_endset=endset,
        problems=problems,
        fit_curve=dsc_n(T, *p),
        baseline_curve=baseline_n(T, *p[1:]),
    )


# calculate enthalpy from a DSC curve
def analyze_enthalpy(
    T,
    HF,
    *,
    heating_rate: float,
    sample_mass: float | None = None,
    already_normalized=False,
    endo_up=True,
    event="endothermic",
    t_min=None,
    t_max=None,
    window=None,
    fit_dcp=True,
) -> EnthalpyResult:
    """Enthalpy of one thermal event by DSC_N(T) fit and by integration.

    Args:
        T: temperature (deg C).
        HF: heat flow, in mW (give sample_mass) or already per gram
            (already_normalized=True, W/g or mW/mg).
        heating_rate: heating rate; required for J/g.
        sample_mass: sample mass; required unless already_normalized.
        endo_up: True if endothermic events point up in the raw data.
        event: 'endothermic' (melting) or 'exothermic' (crystallization,
            decomposition). The reported enthalpy of an exothermic event is negative.
        t_min, t_max: range in which to look for the event.
        window: explicit (t_start, t_end) overriding the automatic window.
        baseline: integration baseline, 'linear' or 'sigmoidal'.
        fit_dcp: fit the heat-capacity step in the model.
    """
    if event not in ("endothermic", "exothermic"):
        raise ValueError("event must be 'endothermic' or 'exothermic'")
    if not np.isfinite(heating_rate) or heating_rate <= 0:
        raise ValueError("A positive heating rate (°C/min) is required.")
    if not already_normalized and not (sample_mass and sample_mass > 0):
        raise ValueError(
            "Sample mass (mg) is required to normalize the heat flow, or state "
            "that the heat flow is already normalized per gram."
        )

    T = np.asarray(T, dtype=float)
    HF = np.asarray(HF, dtype=float)
    ok = np.isfinite(T) & np.isfinite(HF)
    T, HF = T[ok], HF[ok]
    T, uniq = np.unique(T, return_index=True)  # sorts and drops duplicates
    HF = HF[uniq]

    if already_normalized:
        y = HF
    elif sample_mass is not None:
        y = HF / float(sample_mass)  # mW/mg = W/g
    else:
        raise ValueError("Sample mass (mg) is required to normalize the heat flow.")

    event_sign = 1.0 if event == "endothermic" else -1.0
    orient = (1.0 if endo_up else -1.0) * event_sign
    y = orient * y  # event now points up
    rate = float(heating_rate) / 60.0

    if window is None:
        t_start, t_end, _ = select_peak_window(T, y, t_min, t_max)
    else:
        t_start, t_end = float(window[0]), float(window[1])

    mask = (T >= t_start) & (T <= t_end)
    Tw, yw = T[mask], y[mask]

    fit = fit_dsc_n(Tw, yw, rate, fit_dcp=fit_dcp)

    notes: list[str] = list(fit.problems)

    fit.dH_J_per_g *= event_sign  # pylint: disable=invalid-name
    fit.dH_J_per_g_err = abs(fit.dH_J_per_g_err)  # pylint: disable=invalid-name

    return EnthalpyResult(
        fit=fit,
        window=(float(Tw[0]), float(Tw[-1])),
        event=event,
        warnings=notes,
        T=Tw,
        y=yw,
    )


# added plotting tool function
def plot_enthalpy(result: EnthalpyResult) -> Figure:
    """Fit overlay with residuals (event drawn pointing up)."""

    fig = Figure(figsize=(8, 6), dpi=100)
    ax, ax_res = fig.subplots(2, 1, sharex=True, gridspec_kw={"height_ratios": [3, 1]})
    T, y = result.T, result.y
    fit = result.fit
    ax.plot(T, y, ".", ms=3, color="tab:red", label="Data")
    ax.plot(
        T,
        fit.fit_curve,
        "k-",
        lw=1.5,
        label=f"DSC_N(T) fit, ΔH = {fit.dH_J_per_g:.2f} J/g",
    )
    ax.plot(T, fit.baseline_curve, "--", color="gray", label="Fit baseline")
    ax.axvline(fit.Tm0, color="tab:green", ls="--", label=f"Tm0 = {fit.Tm0:.2f} °C")
    ax.set_ylabel("Heat flow (W/g, event up)")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)
    ax_res.plot(T, y - fit.fit_curve, color="tab:red", lw=0.8)
    ax_res.axhline(0, color="k", lw=0.5)
    ax_res.set_xlabel("Temperature (°C)")
    ax_res.set_ylabel("Residual")
    ax_res.grid(True, alpha=0.3)
    return fig
