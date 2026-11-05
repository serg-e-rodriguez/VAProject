"""
Altair chart factories (UI_Design.md §5, §11.3). Data in, chart out — no Streamlit here.

Colour rules: party sides always use the dem/rep tokens; other categories (channels) use the
validated categorical order in CHANNEL_COLORS, mapped to the entity (never to rank).
"""

from __future__ import annotations

import altair as alt
import pandas as pd

from campaign_intel.config import CHANNEL_LABELS, CHANNELS
from campaign_intel.ui.styles import get_tokens

# Validated with the dataviz palette checker (CVD + contrast) for both surfaces.
CHANNEL_COLORS = {
    "light": ["#1baf7a", "#eb6834", "#6250d6", "#eda100", "#e87ba4"],
    "dark": ["#199e70", "#d95926", "#9085e9", "#c98500", "#d55181"],
}
SIDE_ORDER = ["Dem side", "GOP side", "Nonpartisan / other", "Unclassified"]


def side_scale(theme: str) -> alt.Scale:
    t = get_tokens(theme)
    return alt.Scale(domain=SIDE_ORDER, range=[t["dem"], t["rep"], t["text_muted"], t["border"]])


def channel_scale(theme: str, labels: bool = True) -> alt.Scale:
    dom = [CHANNEL_LABELS[c] for c in CHANNELS] if labels else CHANNELS
    return alt.Scale(domain=dom, range=CHANNEL_COLORS["dark" if theme == "dark" else "light"])


# ----------------------------------------------------------------------------- time series
def area_with_band(df: pd.DataFrame, x_col: str, mid_col: str, low_col: str, high_col: str,
                   series_col: str, theme: str = "light", y_title: str = "NC spend ($)",
                   height: int = 300) -> alt.Chart:
    """Mid line with low–high band per series, plus a vertical crosshair tooltip."""
    color = alt.Color(f"{series_col}:N", scale=side_scale(theme), title=None,
                      legend=alt.Legend(orient="top"))
    base = alt.Chart(df).encode(x=alt.X(f"{x_col}:T", title=None))
    band = base.mark_area(opacity=0.18, interpolate="monotone").encode(
        y=alt.Y(f"{low_col}:Q", title=y_title, axis=alt.Axis(format="$~s")), y2=f"{high_col}:Q", color=color)
    line = base.mark_line(interpolate="monotone", strokeWidth=2).encode(y=f"{mid_col}:Q", color=color)
    hover = alt.selection_point(fields=[x_col], nearest=True, on="pointerover", empty=False, clear="pointerout")
    pts = base.mark_point(size=60, filled=True).encode(
        y=f"{mid_col}:Q", color=color,
        opacity=alt.condition(hover, alt.value(1), alt.value(0)),
        tooltip=[alt.Tooltip(f"{x_col}:T", title="Week of", format="%b %d, %Y"),
                 alt.Tooltip(f"{series_col}:N", title="Side"),
                 alt.Tooltip(f"{mid_col}:Q", title="Mid", format="$,.0f"),
                 alt.Tooltip(f"{low_col}:Q", title="Low", format="$,.0f"),
                 alt.Tooltip(f"{high_col}:Q", title="High", format="$,.0f")],
    ).add_params(hover)
    rule = base.mark_rule(color=get_tokens(theme)["text_muted"]).encode(
        opacity=alt.condition(hover, alt.value(0.6), alt.value(0))).transform_filter(hover)
    return (band + line + rule + pts).properties(height=height)


def share_of_voice_line(df: pd.DataFrame, theme: str = "light", height: int = 260) -> alt.Chart:
    """Dem-side share of partisan spend per week (single series, 50% reference rule)."""
    t = get_tokens(theme)
    line = alt.Chart(df).mark_line(point=alt.OverlayMarkDef(size=50, filled=True), strokeWidth=2,
                                   color=t["dem"]).encode(
        x=alt.X("week_start:T", title=None),
        y=alt.Y("dem_share:Q", title="Dem share of partisan spend", axis=alt.Axis(format="%"),
                scale=alt.Scale(domain=[0, 1])),
        tooltip=[alt.Tooltip("week_start:T", title="Week of", format="%b %d"),
                 alt.Tooltip("dem_share:Q", title="Dem share", format=".1%"),
                 alt.Tooltip("dem:Q", title="Dem side $", format="$,.0f"),
                 alt.Tooltip("gop:Q", title="GOP side $", format="$,.0f")])
    rule = alt.Chart(pd.DataFrame({"y": [0.5]})).mark_rule(strokeDash=[4, 4], color=t["text_muted"]).encode(y="y:Q")
    return (rule + line).properties(height=height)


# ----------------------------------------------------------------------------- bars
def ranked_bar(df: pd.DataFrame, cat_col: str, val_col: str, theme: str = "light", title: str = "",
               fmt: str = "$,.0f", low_col: str | None = None, high_col: str | None = None,
               color_col: str | None = None, color_scale: alt.Scale | None = None,
               height: int | None = None, top: int = 15, label_col: str | None = None) -> alt.Chart:
    """Horizontal ranked bars, optional low–high whiskers and colour by category."""
    t = get_tokens(theme)
    d = df.sort_values(val_col, ascending=False).head(top)
    lab = label_col or cat_col
    tips = [alt.Tooltip(f"{lab}:N", title="Item"), alt.Tooltip(f"{val_col}:Q", title=title or "Value", format=fmt)]
    if low_col and high_col:
        tips += [alt.Tooltip(f"{low_col}:Q", title="Low", format=fmt), alt.Tooltip(f"{high_col}:Q", title="High", format=fmt)]
    enc_color = (alt.Color(f"{color_col}:N", scale=color_scale, title=None, legend=alt.Legend(orient="top"))
                 if color_col else alt.value(t["accent"]))
    y = alt.Y(f"{lab}:N", sort=d[lab].tolist(), title=None, axis=alt.Axis(labelLimit=220))
    bars = alt.Chart(d).mark_bar(cornerRadiusTopRight=4, cornerRadiusBottomRight=4, height={"band": 0.75}).encode(
        y=y, x=alt.X(f"{val_col}:Q", title=title, axis=alt.Axis(format=fmt.replace(",.0f", "~s"))),
        color=enc_color, tooltip=tips)
    layers = [bars]
    if low_col and high_col:
        layers.append(alt.Chart(d).mark_rule(color=t["text_secondary"], strokeWidth=1.5).encode(
            y=y, x=f"{low_col}:Q", x2=f"{high_col}:Q"))
    return alt.layer(*layers).properties(height=height or max(140, 24 * len(d)))


def stacked_weeks(df: pd.DataFrame, theme: str = "light", weeks: int = 8, value_col: str = "dollars",
                  title: str = "Planned dollars", fmt: str = "$,.0f") -> alt.Chart:
    """Week x channel stacked bars (allocation pacing)."""
    d = df.copy()
    d["Channel"] = d["channel"].map(CHANNEL_LABELS)
    d["label"] = d["week"].map(lambda w: f"W{w} · E-{weeks - w}")
    order = [f"W{w} · E-{weeks - w}" for w in range(1, weeks + 1)]
    return alt.Chart(d).mark_bar(stroke=get_tokens(theme)["surface"], strokeWidth=2).encode(
        x=alt.X("label:N", sort=order, title="Week (E- = weeks before Election Day)", scale=alt.Scale(domain=order)),
        y=alt.Y(f"sum({value_col}):Q", title=title, axis=alt.Axis(format=fmt.replace(",.0f", "~s"))),
        color=alt.Color("Channel:N", scale=channel_scale(theme), legend=alt.Legend(orient="top", title=None)),
        order=alt.Order("Channel:N"),
        tooltip=[alt.Tooltip("label:N", title="Week"), alt.Tooltip("Channel:N"),
                 alt.Tooltip(f"sum({value_col}):Q", title=title, format=fmt)],
    ).properties(height=260)


def grouped_bar(df: pd.DataFrame, x_col: str, y_col: str, series_col: str, err_low: str | None = None,
                err_high: str | None = None, y_title: str = "%", theme: str = "light",
                color_scale: alt.Scale | None = None, x_title: str | None = None, height: int = 300) -> alt.Chart:
    t = get_tokens(theme)
    color = alt.Color(f"{series_col}:N", title=None, legend=alt.Legend(orient="top"), scale=color_scale or alt.Undefined)
    tips = [alt.Tooltip(f"{x_col}:N", title="Group"), alt.Tooltip(f"{series_col}:N", title="Series"),
            alt.Tooltip(f"{y_col}:Q", title=y_title, format=",.1f")]
    if err_low and err_high:
        tips += [alt.Tooltip(f"{err_low}:Q", title="95% CI low", format=".1f"),
                 alt.Tooltip(f"{err_high}:Q", title="95% CI high", format=".1f")]
    base = alt.Chart(df).encode(x=alt.X(f"{x_col}:N", title=x_title, sort=None), xOffset=f"{series_col}:N")
    bars = base.mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4, stroke=t["surface"], strokeWidth=2).encode(
        y=alt.Y(f"{y_col}:Q", title=y_title), color=color, tooltip=tips)
    if err_low and err_high:
        err = base.mark_rule(color=t["text_secondary"], strokeWidth=1.5).encode(y=f"{err_low}:Q", y2=f"{err_high}:Q")
        return (bars + err).properties(height=height)
    return bars.properties(height=height)


def heatmap(df: pd.DataFrame, x_col: str, y_col: str, val_col: str, is_gap: bool = False,
            theme: str = "light", x_title: str = "Age group", val_title: str = "% of impressions",
            x_sort: list[str] | None = None) -> alt.Chart:
    t = get_tokens(theme)
    if is_gap:
        m = max(5.0, float(df[val_col].abs().max() or 5))
        scale = alt.Scale(domain=[-m, 0, m], range=[t["rep"], t["border"], t["dem"]])
    else:
        scale = alt.Scale(range=["#E8EEFC" if theme == "light" else "#232B3D", t["dem"]], domainMin=0)
    rect = alt.Chart(df).mark_rect(cornerRadius=3, stroke=t["surface"], strokeWidth=2).encode(
        x=alt.X(f"{x_col}:O", title=x_title, sort=x_sort),
        y=alt.Y(f"{y_col}:N", title=None, sort="-color" if not is_gap else None),
        color=alt.Color(f"{val_col}:Q", scale=scale, title=val_title, legend=alt.Legend(orient="right")),
        tooltip=[alt.Tooltip(f"{y_col}:N", title="Theme"), alt.Tooltip(f"{x_col}:O", title=x_title),
                 alt.Tooltip(f"{val_col}:Q", title=val_title, format="+.1f" if is_gap else ".1f")])
    return rect.properties(height=max(220, 30 * df[y_col].nunique()))


# ----------------------------------------------------------------------------- War Room
def outcome_histogram(df: pd.DataFrame, theme: str = "light", x_title: str = "Statewide margin (votes)",
                      threshold: float = 0.0, discrete: bool = False) -> alt.Chart:
    """Baseline (outline) vs plan (filled) distribution of the simulated outcome."""
    t = get_tokens(theme)
    d = df.copy()
    d["mid"] = (d["bin_start"] + d["bin_end"]) / 2
    fmt = ",d" if discrete else "+,.0f"
    plan = alt.Chart(d[d["series"] == "With plan"]).mark_bar(opacity=0.85, binSpacing=0).encode(
        x=alt.X("bin_start:Q", title=x_title, axis=alt.Axis(format="~s" if not discrete else "d")),
        x2="bin_end:Q", y=alt.Y("count:Q", title="Simulated outcomes"),
        color=alt.condition(alt.datum.is_win, alt.value(t["dem"]), alt.value(t["rep"])),
        tooltip=[alt.Tooltip("mid:Q", title="Outcome ≈", format=fmt), alt.Tooltip("count:Q", title="Draws (plan)"),
                 alt.Tooltip("series:N")])
    base = alt.Chart(d[d["series"] != "With plan"]).mark_line(interpolate="step", color=t["text_secondary"],
                                                               strokeDash=[3, 2], strokeWidth=1.5).encode(
        x="mid:Q", y="count:Q", tooltip=[alt.Tooltip("mid:Q", title="Outcome ≈", format=fmt),
                                         alt.Tooltip("count:Q", title="Draws (baseline)")])
    rule = alt.Chart(pd.DataFrame({"x": [threshold]})).mark_rule(strokeDash=[4, 4], strokeWidth=2,
                                                                  color=t["text_primary"]).encode(x="x:Q")
    return (plan + base + rule).properties(height=240)


def win_prob_bar(win_prob: float, baseline_win_prob: float, interval: tuple[float, float],
                 theme: str = "light") -> alt.Chart:
    t = get_tokens(theme)
    d = pd.DataFrame([{"plan": win_prob * 100, "base": baseline_win_prob * 100, "lo": interval[0] * 100,
                       "hi": interval[1] * 100, "y": "Win probability"}])
    track = alt.Chart(pd.DataFrame([{"x": 100, "y": "Win probability"}])).mark_bar(
        height=22, color=t["border"], cornerRadius=6).encode(x=alt.X("x:Q", scale=alt.Scale(domain=[0, 100]),
                                                                    title="Win probability (%)"), y=alt.Y("y:N", axis=None))
    bar = alt.Chart(d).mark_bar(height=22, cornerRadius=6, color=t["accent"]).encode(
        x="plan:Q", y="y:N", tooltip=[alt.Tooltip("plan:Q", title="With plan (%)", format=".1f"),
                                      alt.Tooltip("base:Q", title="Baseline (%)", format=".1f"),
                                      alt.Tooltip("lo:Q", title="Effect-size 10th pct (%)", format=".1f"),
                                      alt.Tooltip("hi:Q", title="Effect-size 90th pct (%)", format=".1f")])
    err = alt.Chart(d).mark_rule(color=t["text_primary"], strokeWidth=2).encode(x="lo:Q", x2="hi:Q", y="y:N")
    base = alt.Chart(d).mark_tick(color=t["text_primary"], thickness=3, size=34).encode(x="base:Q", y="y:N")
    return (track + bar + err + base).properties(height=60)


def response_curves(df: pd.DataFrame, theme: str = "light", current_x: float | None = None) -> alt.Chart:
    d = df.copy()
    d["Channel"] = d["channel"].map(CHANNEL_LABELS)
    sel = alt.selection_point(fields=["Channel"], bind="legend")
    lines = alt.Chart(d).mark_line(strokeWidth=2).encode(
        x=alt.X("extra_dollars:Q", title="Extra dollars in this unit / audience / week", axis=alt.Axis(format="$~s")),
        y=alt.Y("delta_votes:Q", title="Added net votes (expected)"),
        color=alt.Color("Channel:N", scale=channel_scale(theme), legend=alt.Legend(orient="top", title=None)),
        opacity=alt.condition(sel, alt.value(1), alt.value(0.15)),
        tooltip=[alt.Tooltip("Channel:N"), alt.Tooltip("extra_dollars:Q", title="Extra $", format="$,.0f"),
                 alt.Tooltip("delta_votes:Q", title="Added votes", format=",.0f")]).add_params(sel)
    return lines.properties(height=260)


def tornado(df: pd.DataFrame, theme: str = "light") -> alt.Chart:
    """Sensitivity: win prob with each parameter at its pessimistic / optimistic end."""
    t = get_tokens(theme)
    d = df.copy()
    for c in ["low", "high", "base"]:
        d[c] = d[c] * 100
    order = d["parameter"].tolist()
    y = alt.Y("parameter:N", sort=order, title=None, axis=alt.Axis(labelLimit=200))
    rng = alt.Chart(d).mark_rule(strokeWidth=10, color=t["border"]).encode(
        y=y, x=alt.X("low:Q", title="Win probability (%)"), x2="high:Q")
    lo = alt.Chart(d).mark_point(filled=True, size=110, color=t["rep"]).encode(
        y=y, x="low:Q", tooltip=[alt.Tooltip("parameter:N"), alt.Tooltip("low:Q", title="Pessimistic end (%)", format=".1f")])
    hi = alt.Chart(d).mark_point(filled=True, size=110, color=t["dem"]).encode(
        y=y, x="high:Q", tooltip=[alt.Tooltip("parameter:N"), alt.Tooltip("high:Q", title="Optimistic end (%)", format=".1f")])
    base = alt.Chart(d.head(1)).mark_rule(strokeDash=[4, 4], color=t["text_primary"]).encode(x="base:Q")
    return (rng + lo + hi + base).properties(height=max(160, 34 * len(d)))


# ----------------------------------------------------------------------------- backtest
def backtest_scatter(df: pd.DataFrame, theme: str = "light", label: str = "Unit") -> alt.Chart:
    """Baseline (2024 pres) margin vs 2026 Senate margin per unit; diagonal = no swing."""
    t = get_tokens(theme)
    lo = float(min(df["dem_margin_pct"].min(), df["actual26_margin_pct"].min())) - 5
    hi = float(max(df["dem_margin_pct"].max(), df["actual26_margin_pct"].max())) + 5
    sc = alt.Scale(domain=[lo, hi])
    diag = alt.Chart(pd.DataFrame({"x": [lo, hi], "y": [lo, hi]})).mark_line(
        strokeDash=[4, 4], color=t["text_muted"]).encode(x=alt.X("x:Q", scale=sc), y=alt.Y("y:Q", scale=sc))
    zero_x = alt.Chart(pd.DataFrame({"v": [0]})).mark_rule(color=t["border"]).encode(x="v:Q")
    zero_y = alt.Chart(pd.DataFrame({"v": [0]})).mark_rule(color=t["border"]).encode(y="v:Q")
    d = df.copy()
    d["Outcome"] = d["flip"].map({True: "Flipped to Dem", False: "Same winner"})
    pts = alt.Chart(d).mark_circle(size=70, opacity=0.85, stroke=t["surface"], strokeWidth=1).encode(
        x=alt.X("dem_margin_pct:Q", scale=sc, title="Baseline: 2024 President Dem margin (pts)"),
        y=alt.Y("actual26_margin_pct:Q", scale=sc, title="Actual: 2026 US Senate Dem margin (pts)"),
        color=alt.Color("Outcome:N", scale=alt.Scale(domain=["Flipped to Dem", "Same winner"],
                                                      range=[t["dem"], t["text_muted"]]),
                        legend=alt.Legend(orient="top", title=None)),
        tooltip=[alt.Tooltip("name:N", title=label), alt.Tooltip("dem_margin_pct:Q", title="2024 baseline", format="+.1f"),
                 alt.Tooltip("actual26_margin_pct:Q", title="2026 actual", format="+.1f"),
                 alt.Tooltip("swing:Q", title="Swing", format="+.1f")])
    return (zero_x + zero_y + diag + pts).properties(height=380)
