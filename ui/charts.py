"""
Small Altair chart helpers used by the Dashboard and Evaluation pages, so every chart
shares the same look: thin rounded bars, value labels, hover tooltips, quiet axes.

Colour rules (validated for colour-blind safety):
  * one series            -> a single blue (SERIES_1)
  * baseline / full / ablation groups -> blue, orange, aqua in that fixed order
  * verdicts              -> the status colours from ui.common, always beside a text label
  * magnitude (heatmaps)  -> one blue, light to dark
"""
import altair as alt
import pandas as pd

SERIES_1 = "#2a78d6"
GROUP_COLORS = {"full": "#2a78d6", "baseline": "#eb6834", "ablation": "#1baf7a"}
BLUE_RAMP = ["#cde2fb", "#86b6ef", "#3987e5", "#1c5cab", "#0d366b"]


def hbar(df: pd.DataFrame, value: str, label: str, *, title: str, fmt: str = ".0%", color: str | None = None,
         color_map: dict | None = None, legend_title: str | None = None, legend: bool = True,
         domain_max: float | None = None,
         tooltip: list | None = None, height_per_bar: int = 30) -> alt.Chart:
    """Horizontal bar chart, longest-to-shortest order kept as given, with a value label on each bar."""
    scale = alt.Scale(domain=[0, domain_max]) if domain_max is not None else alt.Undefined
    order = df[label].tolist()   # keep the rows in the order given (an explicit list is the reliable way)
    base = alt.Chart(df).encode(
        y=alt.Y(f"{label}:N", sort=order, title=None, axis=alt.Axis(labelLimit=260)),
        x=alt.X(f"{value}:Q", title=None, scale=scale, axis=alt.Axis(format=fmt, grid=True, tickCount=5)),
        tooltip=tooltip or [alt.Tooltip(f"{label}:N"), alt.Tooltip(f"{value}:Q", format=fmt)],
    )
    if color_map:
        enc = alt.Color(f"{color}:N", scale=alt.Scale(domain=list(color_map), range=list(color_map.values())),
                        legend=alt.Legend(title=legend_title, orient="top") if legend else None)
    else:
        enc = alt.value(SERIES_1)
    bars = base.mark_bar(cornerRadiusEnd=4, size=16).encode(color=enc)
    # Mid-grey labels read on both the light and the dark theme.
    labels = base.mark_text(align="left", dx=4, fontSize=12, color="#9ca3af").encode(
        text=alt.Text(f"{value}:Q", format=fmt))
    # In Streamlit the height includes the title, axis and legend, so leave room for them.
    overhead = 70 + (30 if color_map and legend else 0)
    return (bars + labels).properties(title=title, height=height_per_bar * len(df) + overhead)


def heatmap(df: pd.DataFrame, x: str, y: str, value: str, *, title: str, x_title: str, y_title: str,
            order: list[str] | None = None) -> alt.Chart:
    """Counts in a grid, one blue ramp, with the number printed in each cell."""
    base = alt.Chart(df).encode(
        x=alt.X(f"{x}:N", sort=order, title=x_title,
                axis=alt.Axis(labelAngle=-20, labelLimit=160, labelOverlap=False)),
        y=alt.Y(f"{y}:N", sort=order, title=y_title, axis=alt.Axis(labelLimit=180)),
        tooltip=[alt.Tooltip(f"{y}:N", title=y_title), alt.Tooltip(f"{x}:N", title=x_title),
                 alt.Tooltip(f"{value}:Q", title="claims")],
    )
    cells = base.mark_rect(cornerRadius=3, stroke="white", strokeWidth=2).encode(
        color=alt.Color(f"{value}:Q", scale=alt.Scale(range=BLUE_RAMP), legend=None))
    text = base.mark_text(fontSize=13, fontWeight="bold").encode(
        text=alt.Text(f"{value}:Q"),
        color=alt.condition(f"datum.{value} > 3", alt.value("white"), alt.value("#0b0b0b")))
    return (cells + text).properties(title=title, height=50 * df[y].nunique() + 80)


def line(df: pd.DataFrame, x: str, y: str, *, title: str, x_title: str, y_fmt: str = ".0%",
         y_domain: list | None = None, x_type: str = "Q") -> alt.Chart:
    """One-series line with visible points and a hover tooltip."""
    base = alt.Chart(df).encode(
        x=alt.X(f"{x}:{x_type}", title=x_title),
        y=alt.Y(f"{y}:Q", title=None, axis=alt.Axis(format=y_fmt),
                scale=alt.Scale(domain=y_domain) if y_domain else alt.Undefined),
        tooltip=[alt.Tooltip(f"{x}:{x_type}", title=x_title), alt.Tooltip(f"{y}:Q", format=y_fmt)],
    )
    return (base.mark_line(strokeWidth=2, color=SERIES_1)
            + base.mark_point(size=70, filled=True, color=SERIES_1)).properties(title=title, height=240)
