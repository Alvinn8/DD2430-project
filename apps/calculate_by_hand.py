"""
Modern CSV Data Analyzer - Auto-Initialization with Interactive 1D Span Adjustment
"""

# 1. Standard Library Imports
from dataclasses import dataclass, field
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import Optional, Tuple

# 2. Third-Party Imports
import customtkinter as ctk
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.axes import Axes
from matplotlib.backend_bases import MouseButton
from matplotlib.backends._backend_tk import NavigationToolbar2Tk
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from matplotlib.widgets import SpanSelector

# 3. Local Imports
from tools.DSCReader import read_dsc_file
from tools.MeltingPointAnalysis import find_break_points, find_intersection, linear_fit


@dataclass
class FitState:
    """Stores the data points and linear fit parameters for a selected region."""

    points: pd.DataFrame = field(default_factory=pd.DataFrame)
    slope: Optional[float] = None
    intercept: Optional[float] = None


@dataclass
class UIElements:  # pylint: disable=too-many-instance-attributes
    """Stores references to UI widgets to reduce instance attribute count."""

    plot_container: Optional[ctk.CTkFrame] = None
    status_label: Optional[ctk.CTkLabel] = None
    baseline_btn: Optional[ctk.CTkButton] = None
    decline_btn: Optional[ctk.CTkButton] = None
    confirm_btn: Optional[ctk.CTkButton] = None
    baseline_count: Optional[ctk.CTkLabel] = None
    baseline_fit: Optional[ctk.CTkLabel] = None
    decline_count: Optional[ctk.CTkLabel] = None
    decline_fit: Optional[ctk.CTkLabel] = None
    intersection_result: Optional[ctk.CTkLabel] = None
    save_btn: Optional[ctk.CTkButton] = None


class CSVAnalyzerApp:  # pylint: disable=too-many-instance-attributes
    """Modern CSV analyzer with automated region detection and manual span overrides."""

    def __init__(self, root: ctk.CTk) -> None:
        """Initialize the application."""
        self.root = root
        self.root.title("CSV Data Analyzer")
        self.root.geometry("1400x950")

        # Data and Plotting storage
        self.df: Optional[pd.DataFrame] = None
        self.fig: Optional[Figure] = None
        self.ax: Optional[Axes] = None
        self.canvas: Optional[FigureCanvasTkAgg] = None
        self.toolbar: Optional[NavigationToolbar2Tk] = None

        # State encapsulation to avoid R0902 (Too many instance attributes)
        self.baseline = FitState()
        self.decline = FitState()
        self.ui = UIElements()

        # Interactive selection tools and state
        self.span_selector: Optional[SpanSelector] = None
        self.is_baseline_mode: bool = False
        self.is_decline_mode: bool = False
        self.intersection_pt: Optional[Tuple[float, float]] = None

        # Store initial axis view limits for resetting
        self.orig_xlim: Optional[Tuple[float, float]] = None
        self.orig_ylim: Optional[Tuple[float, float]] = None

        # Color scheme
        self.colors = {
            "primary": "#2E7D32",
            "baseline": "#1F2FAC",
            "decline": "#E53935",
            "accent": "#F57C00",
            "text": "#212121",
            "text_light": "#616161",
            "bg": "#F5F5F5",
        }

        ctk.set_appearance_mode("light")
        ctk.set_default_color_theme("green")

        self._create_ui()

    def _create_ui(self) -> None:
        """Create the main user interface structure."""
        main_frame = ctk.CTkFrame(self.root, fg_color=self.colors["bg"])
        main_frame.pack(fill="both", expand=True, padx=0, pady=0)

        self._create_top_panel(main_frame)

        content_frame = ctk.CTkFrame(main_frame, fg_color=self.colors["bg"])
        content_frame.pack(fill="both", expand=True, padx=12, pady=12)

        plot_frame = ctk.CTkFrame(content_frame, fg_color="white")
        plot_frame.pack(side="left", fill="both", expand=True, padx=(0, 8))

        plot_label = ctk.CTkLabel(
            plot_frame,
            text="Data Visualization",
            font=("Segoe UI", 16, "bold"),
            text_color=self.colors["text"],
        )
        plot_label.pack(pady=(8, 4), padx=8)

        self.ui.plot_container = ctk.CTkFrame(plot_frame, fg_color="white")
        self.ui.plot_container.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        self._create_right_panel(content_frame)

    def _create_top_panel(self, parent: ctk.CTkFrame) -> None:
        """Create the top control panel for loading and resetting views."""
        top_frame = ctk.CTkFrame(parent, fg_color=self.colors["bg"])
        top_frame.pack(fill="x", padx=12, pady=12)

        title = ctk.CTkLabel(
            top_frame,
            text="CSV Data Analyzer",
            font=("Segoe UI", 18, "bold"),
            text_color=self.colors["text"],
        )
        title.pack(side="left", padx=(0, 20))

        load_btn = ctk.CTkButton(
            top_frame,
            text="Load CSV File",
            command=self._load_csv,
            fg_color=self.colors["primary"],
            text_color="white",
            font=("Segoe UI", 11, "bold"),
            hover_color="#1b5e20",
            width=140,
            height=36,
        )
        load_btn.pack(side="left", padx=6)

        reset_view_btn = ctk.CTkButton(
            top_frame,
            text="Reset Graph View",
            command=self._reset_view,
            fg_color=self.colors["accent"],
            text_color="white",
            font=("Segoe UI", 11, "bold"),
            hover_color="#E65100",
            width=140,
            height=36,
        )
        reset_view_btn.pack(side="left", padx=6)

        self.ui.status_label = ctk.CTkLabel(
            top_frame,
            text="No file loaded",
            font=("Segoe UI", 10),
            text_color=self.colors["text_light"],
        )
        self.ui.status_label.pack(side="left", padx=12)

    def _create_right_panel(self, parent: ctk.CTkFrame) -> None:
        """Create the right sidebar for manual adjustments and results."""
        right_frame = ctk.CTkFrame(parent, fg_color="white", corner_radius=8, width=340)
        right_frame.pack(side="right", fill="y", padx=(8, 0))
        right_frame.pack_propagate(False)

        inner_frame = ctk.CTkFrame(right_frame, fg_color="white")
        inner_frame.pack(fill="both", expand=True, padx=16, pady=16)

        # --- Manual Adjustment Controls ---
        controls_label = ctk.CTkLabel(
            inner_frame,
            text="Manual Adjustments",
            font=("Segoe UI", 14, "bold"),
            text_color=self.colors["text"],
        )
        controls_label.pack(pady=(0, 12))

        self.ui.baseline_btn = ctk.CTkButton(
            inner_frame,
            text="Adjust Baseline Span",
            command=self._activate_baseline_selection,
            fg_color=self.colors["baseline"],
            text_color="white",
            font=("Segoe UI", 11, "bold"),
            hover_color="#3E388E",
            height=36,
        )
        self.ui.baseline_btn.pack(fill="x", pady=4)

        self.ui.decline_btn = ctk.CTkButton(
            inner_frame,
            text="Adjust Decline Span",
            command=self._activate_decline_selection,
            fg_color=self.colors["decline"],
            text_color="white",
            font=("Segoe UI", 11, "bold"),
            hover_color="#C62828",
            height=36,
        )
        self.ui.decline_btn.pack(fill="x", pady=4)

        self.ui.confirm_btn = ctk.CTkButton(
            inner_frame,
            text="Confirm Adjustment",
            command=self._confirm_selection,
            fg_color="#2E7D32",
            text_color="white",
            font=("Segoe UI", 11, "bold"),
            hover_color="#1B5E20",
            height=36,
            state="disabled",
        )
        self.ui.confirm_btn.pack(fill="x", pady=4)

        divider1 = ctk.CTkFrame(inner_frame, fg_color="#E0E0E0", height=1)
        divider1.pack(fill="x", pady=10)

        # --- Results Section ---
        results_label = ctk.CTkLabel(
            inner_frame,
            text="Analysis Results",
            font=("Segoe UI", 14, "bold"),
            text_color=self.colors["text"],
        )
        results_label.pack(pady=(0, 8))

        baseline_box = ctk.CTkFrame(inner_frame, fg_color="#E8E9F5", corner_radius=6)
        baseline_box.pack(fill="x", pady=4)

        ctk.CTkLabel(
            baseline_box,
            text="Baseline Region",
            font=("Segoe UI", 11, "bold"),
            text_color=self.colors["baseline"],
        ).pack(pady=(6, 2), padx=8)

        self.ui.baseline_count = ctk.CTkLabel(
            baseline_box,
            text="Count: 0",
            font=("Segoe UI", 10),
            text_color=self.colors["text"],
        )
        self.ui.baseline_count.pack(padx=8, pady=1)

        self.ui.baseline_fit = ctk.CTkLabel(
            baseline_box,
            text="Fit: —",
            font=("Segoe UI", 11, "bold"),
            text_color=self.colors["baseline"],
        )
        self.ui.baseline_fit.pack(padx=8, pady=(1, 6))

        decline_box = ctk.CTkFrame(inner_frame, fg_color="#FFEBEE", corner_radius=6)
        decline_box.pack(fill="x", pady=4)

        ctk.CTkLabel(
            decline_box,
            text="Decline Region",
            font=("Segoe UI", 11, "bold"),
            text_color=self.colors["decline"],
        ).pack(pady=(6, 2), padx=8)

        self.ui.decline_count = ctk.CTkLabel(
            decline_box,
            text="Count: 0",
            font=("Segoe UI", 10),
            text_color=self.colors["text"],
        )
        self.ui.decline_count.pack(padx=8, pady=1)

        self.ui.decline_fit = ctk.CTkLabel(
            decline_box,
            text="Fit: —",
            font=("Segoe UI", 11, "bold"),
            text_color=self.colors["decline"],
        )
        self.ui.decline_fit.pack(padx=8, pady=(1, 6))

        intersection_box = ctk.CTkFrame(
            inner_frame, fg_color="#E0F7FA", corner_radius=6
        )
        intersection_box.pack(fill="x", pady=4)

        ctk.CTkLabel(
            intersection_box,
            text="Melting Point",
            font=("Segoe UI", 11, "bold"),
            text_color="#00838F",
        ).pack(pady=(6, 2), padx=8)

        self.ui.intersection_result = ctk.CTkLabel(
            intersection_box,
            text="—",
            font=("Segoe UI", 11, "bold"),
            text_color="#006064",
        )
        self.ui.intersection_result.pack(padx=8, pady=(1, 6))

        self.ui.save_btn = ctk.CTkButton(
            inner_frame,
            text="Save Data & Results",
            command=self._save_csv,
            fg_color="#00695C",
            text_color="white",
            font=("Segoe UI", 11, "bold"),
            hover_color="#004D40",
            height=36,
        )
        self.ui.save_btn.pack(fill="x", pady=(12, 6))

        divider2 = ctk.CTkFrame(inner_frame, fg_color="#E0E0E0", height=1)
        divider2.pack(fill="x", pady=10)

        inst_label = ctk.CTkLabel(
            inner_frame,
            text="Instructions",
            font=("Segoe UI", 12, "bold"),
            text_color=self.colors["text"],
        )
        inst_label.pack(pady=(0, 6))

        inst_text = ctk.CTkTextbox(
            inner_frame,
            height=130,
            font=("Segoe UI", 9),
            text_color=self.colors["text"],
            fg_color="#FAFAFA",
            border_color="#E0E0E0",
            border_width=1,
        )
        inst_text.pack(fill="both", expand=True)

        inst_content = """1. Load CSV to auto-calculate regions.
2. If incorrect, click "Adjust..." to open the selector tool.
3. Click & drag a horizontal span. Drag edges to resize.
4. Click "Confirm Adjustment" to lock it.
5. Click "Save Data & Results" to export.
6. Zooming: Use mouse scroll wheel."""

        inst_text.insert("1.0", inst_content)
        inst_text.configure(state="disabled")

    def _load_csv(self) -> None:
        """Load CSV, sort it, run automated initialization, and plot."""
        file_path = filedialog.askopenfilename(
            title="Select CSV File",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
        )
        if not file_path:
            return

        try:
            self.df = read_dsc_file(file_path)

            if (
                "Temperature" not in self.df.columns
                or "HeatFlow" not in self.df.columns
            ):
                messagebox.showerror(
                    "Error", "CSV must contain 'Temperature' and 'HeatFlow' columns"
                )
                self.df = None
                return

            self.df = self.df.sort_values("Temperature").reset_index(drop=True)
            self.ui.status_label.configure(text=f"✓ Loaded: {Path(file_path).name}")

            self._reset_state(replot=False)
            self._auto_initialize()
            self._plot_data()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load file: {str(e)}")
            self.df = None

    def _auto_initialize(self) -> None:
        """Automatically find break points and pre-calculate regions."""
        if self.df is None:
            return

        try:
            start_p, end_p, start_d, valley = find_break_points(
                self.df, smoothing_window=11
            )
            self.baseline.points = self.df.loc[start_p:end_p].copy()
            self.decline.points = self.df.loc[start_d:valley].copy()

            self._update_baseline_display()
            self._update_decline_display()
        except Exception as e:
            print(f"Auto-initialization failed: {e}")

    def _save_csv(self) -> None:
        """Export the current dataframe and calculated melting point to a CSV."""
        if self.df is None:
            messagebox.showwarning(
                "Warning", "No data to save. Please load a CSV first."
            )
            return

        file_path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            title="Save CSV File",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
        )
        if not file_path:
            return

        try:
            with open(file_path, "w", encoding="utf-8") as f:
                if self.intersection_pt is not None:
                    melting_point = self.intersection_pt[0]
                    f.write(f"# MELTING_POINT: {melting_point:.2f}\n")
                else:
                    f.write("# MELTING_POINT: Not Calculated\n")
                self.df.to_csv(f, index=False, lineterminator="\n")

            messagebox.showinfo(
                "Success", f"Data successfully saved to {Path(file_path).name}"
            )
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save file: {str(e)}")

    def _plot_data(self) -> None:
        """Create the Matplotlib figure canvas and initially draw everything."""
        if self.df is None:
            return

        if self.toolbar is not None:
            self.toolbar.destroy()
            self.toolbar = None
        if self.fig is not None:
            plt.close(self.fig)
        if self.span_selector is not None:
            self.span_selector.disconnect_events()
            self.span_selector = None

        for widget in self.ui.plot_container.winfo_children():
            widget.destroy()

        self.fig, self.ax = plt.subplots(figsize=(9, 6), dpi=100)
        assert self.ax is not None

        self.canvas = FigureCanvasTkAgg(self.fig, master=self.ui.plot_container)
        self.canvas.mpl_connect("scroll_event", self._on_scroll)
        tk_widget = self.canvas.get_tk_widget()
        tk_widget.pack(fill="both", expand=True)

        self.toolbar = NavigationToolbar2Tk(self.canvas, self.ui.plot_container)
        self.toolbar.update()

        self._redraw_plot(preserve_limits=False)

        self.orig_xlim = self.ax.get_xlim()
        self.orig_ylim = self.ax.get_ylim()

    def _on_scroll(self, event) -> None:
        """Handle mouse scroll events for zooming the plot."""
        if self.ax is None or event.inaxes != self.ax:
            return
        xdata, ydata = event.xdata, event.ydata
        if xdata is None or ydata is None:
            return

        scale_factor = 0.85 if event.button == "up" else 1.15
        cur_xlim = self.ax.get_xlim()
        cur_ylim = self.ax.get_ylim()

        self.ax.set_xlim(
            [
                xdata - (xdata - cur_xlim[0]) * scale_factor,
                xdata + (cur_xlim[1] - xdata) * scale_factor,
            ]
        )
        self.ax.set_ylim(
            [
                ydata - (ydata - cur_ylim[0]) * scale_factor,
                ydata + (cur_ylim[1] - ydata) * scale_factor,
            ]
        )

        if self.canvas is not None:
            self.canvas.draw_idle()

    def _reset_view(self) -> None:
        """Reset the plot view to its original zoom boundaries."""
        if self.ax is None or self.orig_xlim is None or self.orig_ylim is None:
            return
        self.ax.set_xlim(self.orig_xlim)
        self.ax.set_ylim(self.orig_ylim)
        if self.canvas is not None:
            self.canvas.draw_idle()

    def _activate_baseline_selection(self) -> None:
        """Activate the interactive span selector for the baseline."""
        if self.df is None:
            return
        self.is_baseline_mode = True
        self.is_decline_mode = False

        self.baseline.points = pd.DataFrame()
        self.baseline.slope, self.baseline.intercept = None, None
        self._update_baseline_display()
        self._redraw_plot(preserve_limits=True)

        self._enable_span_selector()
        self.ui.baseline_btn.configure(fg_color="#2E377D")
        self.ui.decline_btn.configure(fg_color=self.colors["decline"])

    def _activate_decline_selection(self) -> None:
        """Activate the interactive span selector for the decline region."""
        if self.df is None:
            return
        self.is_baseline_mode = False
        self.is_decline_mode = True

        self.decline.points = pd.DataFrame()
        self.decline.slope, self.decline.intercept = None, None
        self._update_decline_display()
        self._redraw_plot(preserve_limits=True)

        self._enable_span_selector()
        self.ui.decline_btn.configure(fg_color="#B71C1C")
        self.ui.baseline_btn.configure(fg_color=self.colors["baseline"])

    def _enable_span_selector(self) -> None:
        """Initialize and display the matplotlib SpanSelector."""
        if self.canvas is None or self.ax is None:
            return

        if self.span_selector is not None:
            self.span_selector.set_active(False)
            self.span_selector.disconnect_events()
            self.span_selector = None

        color = (
            self.colors["baseline"] if self.is_baseline_mode else self.colors["decline"]
        )

        self.span_selector = SpanSelector(
            self.ax,
            self._on_select,
            direction="horizontal",
            useblit=True,
            button=MouseButton.LEFT,
            interactive=True,
            props={"facecolor": color, "alpha": 0.25},
            handle_props={"alpha": 0.5, "color": color},
        )
        self.span_selector.set_active(True)
        self.ui.confirm_btn.configure(state="normal")

    def _on_select(self, xmin: float, xmax: float) -> None:
        """Update region data dynamically upon releasing the mouse selection drag."""
        if self.df is None or self.span_selector is None:
            return

        mask = (self.df["Temperature"] >= xmin) & (self.df["Temperature"] <= xmax)
        selected_data = self.df[mask].copy()

        if self.is_baseline_mode:
            self.baseline.points = selected_data
            self._update_baseline_display()
        elif self.is_decline_mode:
            self.decline.points = selected_data
            self._update_decline_display()

    def _confirm_selection(self) -> None:
        """Lock in points, clear the interactive widget, and bake the region into the plot."""
        if self.span_selector is not None:
            self.span_selector.set_active(False)
            self.span_selector.disconnect_events()
            self.span_selector = None

        self._redraw_plot(preserve_limits=True)

        self.is_baseline_mode = False
        self.is_decline_mode = False
        self.ui.baseline_btn.configure(fg_color=self.colors["baseline"])
        self.ui.decline_btn.configure(fg_color=self.colors["decline"])
        self.ui.confirm_btn.configure(state="disabled")

    def _update_baseline_display(self) -> None:
        """Recalculate the baseline fit and update the UI panel."""
        if len(self.baseline.points) > 1:
            slope, intercept = linear_fit(
                self.baseline.points["Temperature"].values,
                self.baseline.points["HeatFlow"].values,
            )
            self.baseline.slope, self.baseline.intercept = slope, intercept
            self.ui.baseline_count.configure(text=f"Count: {len(self.baseline.points)}")
            self.ui.baseline_fit.configure(text=f"m={slope:.3f}, b={intercept:.2f}")
        else:
            self.baseline.slope, self.baseline.intercept = None, None
            self.ui.baseline_count.configure(text="Count: 0")
            self.ui.baseline_fit.configure(text="Fit: —")
        self._update_intersection_display()

    def _update_decline_display(self) -> None:
        """Recalculate the decline fit and update the UI panel."""
        if len(self.decline.points) > 1:
            slope, intercept = linear_fit(
                self.decline.points["Temperature"].values,
                self.decline.points["HeatFlow"].values,
            )
            self.decline.slope, self.decline.intercept = slope, intercept
            self.ui.decline_count.configure(text=f"Count: {len(self.decline.points)}")
            self.ui.decline_fit.configure(text=f"m={slope:.3f}, b={intercept:.2f}")
        else:
            self.decline.slope, self.decline.intercept = None, None
            self.ui.decline_count.configure(text="Count: 0")
            self.ui.decline_fit.configure(text="Fit: —")
        self._update_intersection_display()

    def _update_intersection_display(self) -> None:
        """Calculate the intersection of both fits and update the results panel."""
        if (
            self.baseline.slope is not None
            and self.baseline.intercept is not None
            and self.decline.slope is not None
            and self.decline.intercept is not None
        ):
            try:
                x_int, y_int = find_intersection(
                    self.baseline.slope,
                    self.baseline.intercept,
                    self.decline.slope,
                    self.decline.intercept,
                )
                self.intersection_pt = (x_int, y_int)
                self.ui.intersection_result.configure(text=f"{x_int:.2f} °C")
            except ValueError:
                self.intersection_pt = None
                self.ui.intersection_result.configure(text="Parallel lines")
        else:
            self.intersection_pt = None
            self.ui.intersection_result.configure(text="—")

    # --- Plot Rendering Sub-methods ---

    def _plot_base_series(self, x_all: np.ndarray, y_all: np.ndarray) -> None:
        """Helper to plot the primary dataset line."""
        self.ax.plot(
            x_all,
            y_all,
            color=self.colors["primary"],
            linewidth=1.5,
            alpha=0.8,
            label="DSC Data",
        )

    def _plot_regions(self) -> None:
        """Helper to plot the shaded background regions for selected data."""
        if not self.baseline.points.empty:
            b_min = self.baseline.points["Temperature"].min()
            b_max = self.baseline.points["Temperature"].max()
            self.ax.axvspan(
                b_min,
                b_max,
                color=self.colors["baseline"],
                alpha=0.15,
                label="Baseline Region",
            )

        if not self.decline.points.empty:
            d_min = self.decline.points["Temperature"].min()
            d_max = self.decline.points["Temperature"].max()
            self.ax.axvspan(
                d_min,
                d_max,
                color=self.colors["decline"],
                alpha=0.15,
                label="Decline Region",
            )

    def _plot_fit_lines(self, x_all: np.ndarray) -> None:
        """Helper to plot the linear fit projections for both sections."""
        offset = (x_all.max() - x_all.min()) * 0.05

        if self.baseline.slope is not None and self.baseline.intercept is not None:
            x_min = self.baseline.points["Temperature"].min()
            x_max = (
                max(
                    self.baseline.points["Temperature"].max(),
                    self.intersection_pt[0] + offset,
                )
                if self.intersection_pt
                else self.baseline.points["Temperature"].max() + offset
            )
            x_span = np.array([x_min, x_max])
            y_span = self.baseline.slope * x_span + self.baseline.intercept
            self.ax.plot(
                x_span,
                y_span,
                color=self.colors["baseline"],
                linestyle="--",
                linewidth=1.5,
                label="Baseline Fit",
            )

        if self.decline.slope is not None and self.decline.intercept is not None:
            x_max = self.decline.points["Temperature"].max()
            x_min = (
                min(
                    self.decline.points["Temperature"].min(),
                    self.intersection_pt[0] - offset,
                )
                if self.intersection_pt
                else self.decline.points["Temperature"].min() - offset
            )
            x_span = np.array([x_min, x_max])
            y_span = self.decline.slope * x_span + self.decline.intercept
            self.ax.plot(
                x_span,
                y_span,
                color=self.colors["decline"],
                linestyle="--",
                linewidth=1.5,
                label="Decline Fit",
            )

    def _style_axes(self) -> None:
        """Helper to apply standard styling to the Matplotlib axes."""
        self.ax.set_xlabel(
            "Temperature", fontsize=11, fontweight="bold", color=self.colors["text"]
        )
        self.ax.set_ylabel(
            "HeatFlow", fontsize=11, fontweight="bold", color=self.colors["text"]
        )
        self.ax.grid(True, alpha=0.2, linestyle="--", linewidth=0.5)
        self.ax.set_axisbelow(True)

        for spine in self.ax.spines.values():
            spine.set_color("#BDBDBD")
            spine.set_linewidth(1)

        self.ax.tick_params(colors=self.colors["text_light"], labelsize=9)

        has_legends = (
            not self.baseline.points.empty
            or not self.decline.points.empty
            or self.baseline.slope is not None
            or self.decline.slope is not None
        )
        if has_legends:
            self.ax.legend(loc="upper right", framealpha=0.95, fontsize=9)

        self.fig.patch.set_facecolor("white")
        self.ax.set_facecolor("white")

    def _redraw_plot(self, preserve_limits: bool = True) -> None:
        """Redraw the plot utilizing modular helper methods."""
        if (
            self.fig is None
            or self.ax is None
            or self.df is None
            or self.canvas is None
        ):
            return

        curr_xlim = self.ax.get_xlim() if preserve_limits else None
        curr_ylim = self.ax.get_ylim() if preserve_limits else None

        self.ax.clear()

        x_all = np.asarray(self.df["Temperature"], dtype=float)
        y_all = np.asarray(self.df["HeatFlow"], dtype=float)

        self._plot_base_series(x_all, y_all)
        self._plot_regions()
        self._plot_fit_lines(x_all)

        if self.intersection_pt is not None:
            x_int, y_int = self.intersection_pt
            self.ax.scatter(
                x_int,
                y_int,
                color="black",
                zorder=5,
                s=50,
                label=f"Melting Point: {x_int:.2f} °C",
            )

        self._style_axes()

        if preserve_limits and curr_xlim and curr_ylim:
            self.ax.set_xlim(curr_xlim)
            self.ax.set_ylim(curr_ylim)

        self.canvas.draw()

    def _reset_state(self, replot: bool = True) -> None:
        """Clear all stored data points and fitted variables."""
        self.baseline = FitState()
        self.decline = FitState()
        self.intersection_pt = None

        self._update_baseline_display()
        self._update_decline_display()
        self._update_intersection_display()

        if replot and self.df is not None:
            self._redraw_plot(preserve_limits=True)


def main() -> None:
    """Instantiate and run the main application loop."""
    root = ctk.CTk()
    CSVAnalyzerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
