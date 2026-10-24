"""
Altair chart factories adhering strictly to UI_Design.md §5 and §11.3.
Enforces explicit Altair types (:Q, :N, :O, :T), tooltips, and interactivity.
"""

import altair as alt
import pandas as pd

from campaign_intel.ui.styles import get_tokens


def area_with_band(
    df: pd.DataFrame,
    x_col: str,
    mid_col: str,
    low_col: str,
    high_col: str,
    series_col: str | None = None,
    theme: str = "light",
) -> alt.Chart:
    """
    Renders smooth monotone time series line with range band and gradient fill per §11.3.
    """
    t = get_tokens(theme)

    enc_color = alt.Color(f"{series_col}:N") if series_col else alt.value(t["accent"])

    band = alt.Chart(df).mark_area(
        opacity=0.18,
        interpolate="monotone"
    ).encode(
        x=alt.X(f"{x_col}:T", title="Week Starting"),
        y=alt.Y(f"{low_col}:Q", title="Spend ($ USD)", axis=alt.Axis(format="$,.0f")),
        y2=alt.Y2(f"{high_col}:Q"),
        color=enc_color,
    )

    line = alt.Chart(df).mark_line(
        interpolate="monotone",
        strokeWidth=2.2
    ).encode(
        x=alt.X(f"{x_col}:T"),
        y=alt.Y(f"{mid_col}:Q"),
        color=enc_color,
        tooltip=[
            alt.Tooltip(f"{x_col}:T", title="Date", format="%b %d, %Y"),
            alt.Tooltip(f"{mid_col}:Q", title="Midpoint ($)", format="$,.0f"),
            alt.Tooltip(f"{low_col}:Q", title="Low ($)", format="$,.0f"),
            alt.Tooltip(f"{high_col}:Q", title="High ($)", format="$,.0f"),
        ] + ([alt.Tooltip(f"{series_col}:N", title="Series")] if series_col else [])
    )

    chart = (band + line).interactive(bind_y=False).properties(height=320)
    return chart


def grouped_bar(
    df: pd.DataFrame,
    x_col: str,
    y_col: str,
    series_col: str,
    err_low: str | None = None,
    err_high: str | None = None,
    y_title: str = "Percentage (%)",
    theme: str = "light",
) -> alt.Chart:
    """
    Renders grouped bar chart with rounded top corners and optional error bars per §11.3.
    """
    bars = alt.Chart(df).mark_bar(
        cornerRadiusTopLeft=6,
        cornerRadiusTopRight=6
    ).encode(
        x=alt.X(f"{x_col}:O", title="Demographic Cohort"),
        y=alt.Y(f"{y_col}:Q", title=y_title, axis=alt.Axis(format=".1f")),
        xOffset=alt.XOffset(f"{series_col}:N"),
        color=alt.Color(f"{series_col}:N", title="Platform / Category"),
        tooltip=[
            alt.Tooltip(f"{x_col}:O", title="Cohort"),
            alt.Tooltip(f"{series_col}:N", title="Series"),
            alt.Tooltip(f"{y_col}:Q", title=y_title, format=".1f"),
        ] + ([alt.Tooltip(f"{err_low}:Q", title="95% CI Low", format=".1f"),
              alt.Tooltip(f"{err_high}:Q", title="95% CI High", format=".1f")] if err_low and err_high else [])
    )

    if err_low and err_high and err_low in df.columns and err_high in df.columns:
        error = alt.Chart(df).mark_errorbar(
            ticks=True,
            color="#374151"
        ).encode(
            x=alt.X(f"{x_col}:O"),
            xOffset=alt.XOffset(f"{series_col}:N"),
            y=alt.Y(f"{err_low}:Q"),
            y2=alt.Y2(f"{err_high}:Q")
        )
        return (bars + error).interactive().properties(height=320)

    return bars.interactive().properties(height=320)


def donut(
    df: pd.DataFrame,
    category_col: str,
    value_col: str,
    theme: str = "light",
) -> alt.Chart:
    """
    Renders donut chart with 2px gap and right-hand legend per §11.3.
    """
    t = get_tokens(theme)
    chart = alt.Chart(df).mark_arc(
        innerRadius=65,
        outerRadius=105,
        stroke=t["surface"],
        strokeWidth=2
    ).encode(
        theta=alt.Theta(f"{value_col}:Q"),
        color=alt.Color(f"{category_col}:N", title="Channel / Platform"),
        tooltip=[
            alt.Tooltip(f"{category_col}:N", title="Channel"),
            alt.Tooltip(f"{value_col}:Q", title="Spend ($)", format="$,.0f"),
        ]
    ).properties(height=280)
    return chart


def heatmap(
    df: pd.DataFrame,
    x_col: str,
    y_col: str,
    val_col: str,
    is_gap: bool = False,
    theme: str = "light",
) -> alt.Chart:
    """
    Renders theme x demographic heatmap with single-hue or diverging gap scale per §11.3.
    """
    t = get_tokens(theme)

    if is_gap:
        scale = alt.Scale(
            domain=[-30, 0, 30],
            range=[t["rep"], "#F7F7F7" if theme == "light" else "#2A2F3A", t["dem"]]
        )
    else:
        scale = alt.Scale(scheme="greens" if theme == "light" else "tealblues")

    chart = alt.Chart(df).mark_rect(
        cornerRadius=4
    ).encode(
        x=alt.X(f"{x_col}:O", title="Voter Age Segment"),
        y=alt.Y(f"{y_col}:N", title="Message Theme"),
        color=alt.Color(f"{val_col}:Q", scale=scale, title="Share (%)"),
        tooltip=[
            alt.Tooltip(f"{y_col}:N", title="Theme"),
            alt.Tooltip(f"{x_col}:O", title="Age Group"),
            alt.Tooltip(f"{val_col}:Q", title="Delivery / Concern (%)", format=".1f"),
        ]
    ).properties(height=340)
    return chart


def histogram(
    df: pd.DataFrame,
    theme: str = "light",
) -> alt.Chart:
    """
    Renders pre-binned Monte Carlo margin histogram with 0 rule per §11.3.
    """
    t = get_tokens(theme)

    bars = alt.Chart(df).mark_bar(
        cornerRadiusTopLeft=3,
        cornerRadiusTopRight=3
    ).encode(
        x=alt.X("bin_start:Q", title="Projected Net Margin (Votes)", axis=alt.Axis(format="+,d")),
        x2="bin_end:Q",
        y=alt.Y("count:Q", title="Simulation Frequency"),
        color=alt.condition(
            alt.datum.is_win,
            alt.value(t["dem"]),
            alt.value(t["rep"])
        ),
        tooltip=[
            alt.Tooltip("bin_start:Q", title="Bin Start", format="+,d"),
            alt.Tooltip("bin_end:Q", title="Bin End", format="+,d"),
            alt.Tooltip("count:Q", title="Frequency", format=",d"),
        ]
    )

    zero_rule = alt.Chart(pd.DataFrame({"x": [0]})).mark_rule(
        strokeDash=[4, 4],
        strokeWidth=2.2,
        color=t["text_primary"]
    ).encode(x="x:Q")

    return (bars + zero_rule).interactive().properties(height=260)


def win_prob_bar(
    win_prob: float,
    baseline_win_prob: float,
    interval: tuple[float, float],
    theme: str = "light",
) -> alt.Chart:
    """
    Renders horizontal win probability bar with baseline marker and interval per §11.3.
    """
    t = get_tokens(theme)

    df_bar = pd.DataFrame([{
        "plan_prob": win_prob * 100,
        "base_prob": baseline_win_prob * 100,
        "ci_low": interval[0] * 100,
        "ci_high": interval[1] * 100,
        "y": "Win Prob"
    }])

    bar = alt.Chart(df_bar).mark_bar(
        height=22,
        cornerRadiusTopRight=6,
        cornerRadiusBottomRight=6,
        color=t["accent"]
    ).encode(
        x=alt.X("plan_prob:Q", title="Win Probability (%)", scale=alt.Scale(domain=[0, 100])),
        y=alt.Y("y:N", axis=None),
        tooltip=[
            alt.Tooltip("plan_prob:Q", title="Simulated Win Prob (%)", format=".1f"),
            alt.Tooltip("ci_low:Q", title="80% Interval Low (%)", format=".1f"),
            alt.Tooltip("ci_high:Q", title="80% Interval High (%)", format=".1f"),
        ]
    )

    error = alt.Chart(df_bar).mark_errorbar(
        ticks=True,
        color=t["text_primary"],
        thickness=2
    ).encode(
        x=alt.X("ci_low:Q"),
        x2="ci_high:Q",
        y=alt.Y("y:N")
    )

    base_rule = alt.Chart(df_bar).mark_rule(
        color=t["dem"],
        strokeWidth=2.5,
        strokeDash=[4, 3]
    ).encode(
        x="base_prob:Q",
        tooltip=[alt.Tooltip("base_prob:Q", title="Baseline Win Prob (%)", format=".1f")]
    )

    return (bar + error + base_rule).properties(height=65)


def marginal_votes_ranked(
    df: pd.DataFrame,
    unit_col: str = "unit_id",
    votes_col: str = "delta_votes",
    theme: str = "light",
) -> alt.Chart:
    """
    Renders horizontal bar chart of net votes gained by unit per §11.3.
    """
    t = get_tokens(theme)
    top_df = df.head(15) if len(df) > 15 else df

    chart = alt.Chart(top_df).mark_bar(
        cornerRadiusTopRight=4,
        cornerRadiusBottomRight=4,
        color=t["accent"]
    ).encode(
        y=alt.Y(f"{unit_col}:N", sort="-x", title="District / County"),
        x=alt.X(f"{votes_col}:Q", title="Marginal Net Votes Gained (ΔV)", axis=alt.Axis(format="+,d")),
        tooltip=[
            alt.Tooltip(f"{unit_col}:N", title="Unit"),
            alt.Tooltip(f"{votes_col}:Q", title="Net Votes", format="+,d"),
        ]
    ).interactive().properties(height=280)
    return chart
