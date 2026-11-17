"""
Altair chart factories. Data in, chart out — no Streamlit here.

Colour rules: Dem = blue, GOP / Rep = red everywhere; Unaffiliated = violet; other categories
(ad channels) use a fixed categorical order mapped to the entity, never to rank.
"""

from __future__ import annotations

import altair as alt
import numpy as np
import pandas as pd

from campaign_intel.ui.styles import get_tokens

SIDES = ["Dem side", "GOP side"]
LEGEND_PX = 56  # Streamlit fits legend + plot into the declared height; reserve room for a top legend
SIDE_LABELS = {"Dem side": "Democrats", "GOP side": "Republicans"}
PARTIES = ["Dem", "Rep", "Unaffiliated", "Other party"]
CHANNELS = ["Facebook / Instagram", "YouTube", "Google Search", "Google Display"]
CHANNEL_COLORS = {
    "light": ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"],
    "dark": ["#3987e5", "#d95926", "#199e70", "#c98500"],
}


def _short_money(x: float) -> str:
    x = float(x or 0)
    return f"${x / 1e6:.1f}M" if x >= 1e6 else (f"${x / 1e3:.0f}K" if x >= 1e3 else f"${x:,.0f}")


def side_scale(theme: str) -> alt.Scale:
    t = get_tokens(theme)
    return alt.Scale(domain=[SIDE_LABELS[s] for s in SIDES], range=[t["dem"], t["rep"]])


def party_scale(theme: str) -> alt.Scale:
    t = get_tokens(theme)
    return alt.Scale(domain=PARTIES, range=[t["dem"], t["rep"], t["swing"], t["text_muted"]])


def channel_scale(theme: str) -> alt.Scale:
    return alt.Scale(domain=CHANNELS, range=CHANNEL_COLORS["dark" if theme == "dark" else "light"])


def _sides(df: pd.DataFrame, col: str = "side_group") -> pd.DataFrame:
    return df.assign(side=df[col].map(SIDE_LABELS).fillna(df[col]))


# ----------------------------------------------------------------------------- spending
def weekly_sides(df: pd.DataFrame, theme: str, height: int = 260) -> alt.Chart:
    """Weekly spend, one line per side, with a hover crosshair."""
    d = _sides(df.groupby(["week_start", "side_group"], as_index=False)["spend"].sum())
    color = alt.Color("side:N", scale=side_scale(theme), title=None, legend=alt.Legend(orient="top"))
    base = alt.Chart(d).encode(x=alt.X("week_start:T", title=None, axis=alt.Axis(format="%b %d")))
    line = base.mark_line(strokeWidth=2.5, interpolate="monotone").encode(
        y=alt.Y("spend:Q", title="Spend per week", axis=alt.Axis(format="$~s")), color=color)
    hover = alt.selection_point(fields=["week_start"], nearest=True, on="pointerover", empty=False, clear="pointerout")
    pts = base.mark_point(size=70, filled=True).encode(
        y="spend:Q", color=color, opacity=alt.condition(hover, alt.value(1), alt.value(0)),
        tooltip=[alt.Tooltip("week_start:T", title="Week of", format="%b %d"), alt.Tooltip("side:N", title="Side"),
                 alt.Tooltip("spend:Q", title="Spend", format="$,.0f")]).add_params(hover)
    rule = base.mark_rule(color=get_tokens(theme)["text_muted"]).encode(
        opacity=alt.condition(hover, alt.value(0.5), alt.value(0))).transform_filter(hover)
    return (line + rule + pts).properties(height=height)


def ranked_bars(df: pd.DataFrame, label_col: str, value_col: str, theme: str, side_col: str | None = "side_group",
                fmt: str = "$,.0f", axis_fmt: str = "$~s", height: int | None = None,
                extra_tooltips: list[alt.Tooltip] | None = None) -> alt.Chart:
    """Horizontal bars sorted by value, coloured by side, value labelled at the bar end."""
    t = get_tokens(theme)
    d = _sides(df, side_col) if side_col else df.assign(side="")
    d = d.sort_values(value_col, ascending=False)
    d["value_lbl"] = d[value_col].map(_short_money if axis_fmt.startswith("$") else (lambda v: f"{v:,.0f}"))
    enc_color = alt.Color("side:N", scale=side_scale(theme), title=None, legend=None) if side_col else alt.value(t["accent"])
    base = alt.Chart(d).encode(
        y=alt.Y(f"{label_col}:N", sort=d[label_col].tolist(), title=None, axis=alt.Axis(labelLimit=230)),
        x=alt.X(f"{value_col}:Q", title=None, axis=alt.Axis(format=axis_fmt, grid=True),
                scale=alt.Scale(domain=[0, float(d[value_col].max() or 1) * 1.18])),
    )
    bars = base.mark_bar(cornerRadiusEnd=4, height={"band": 0.7}).encode(
        color=enc_color,
        tooltip=[alt.Tooltip(f"{label_col}:N", title="Name"), alt.Tooltip("side:N", title="Side"),
                 alt.Tooltip(f"{value_col}:Q", title="Value", format=fmt)] + (extra_tooltips or []))
    text = base.mark_text(align="left", dx=4, fontSize=11, color=t["text_secondary"]).encode(text="value_lbl:N")
    return (bars + text).properties(height=height or max(120, 30 * len(d)))


def side_pair_bars(df: pd.DataFrame, cat_col: str, value_col: str, theme: str, fmt: str = ".0%",
                   axis_fmt: str = ".0%", order: list[str] | None = None, height: int | None = None) -> alt.Chart:
    """For each category, a Democrats bar and a Republicans bar side by side (horizontal)."""
    d = _sides(df)
    n = d[cat_col].nunique()
    base = alt.Chart(d).encode(
        y=alt.Y(f"{cat_col}:N", sort=order or "-x", title=None, axis=alt.Axis(labelLimit=200)),
        yOffset=alt.YOffset("side:N", sort=[SIDE_LABELS[s] for s in SIDES]),
        x=alt.X(f"{value_col}:Q", title=None, axis=alt.Axis(format=axis_fmt)),
        color=alt.Color("side:N", scale=side_scale(theme), title=None, legend=alt.Legend(orient="top")),
        tooltip=[alt.Tooltip(f"{cat_col}:N", title=" "), alt.Tooltip("side:N", title="Side"),
                 alt.Tooltip(f"{value_col}:Q", title="Value", format=fmt)],
    )
    return base.mark_bar(cornerRadiusEnd=3).properties(height=height or LEGEND_PX + 2 * 18 * n + 16 * n)


def channel_weeks(df: pd.DataFrame, theme: str, height: int = 260) -> alt.Chart:
    """Stacked weekly spend by channel."""
    return alt.Chart(df).mark_bar(cornerRadiusTopLeft=2, cornerRadiusTopRight=2).encode(
        x=alt.X("week_start:T", title=None, axis=alt.Axis(format="%b %d")),
        y=alt.Y("spend:Q", title="Spend per week", axis=alt.Axis(format="$~s")),
        color=alt.Color("channel:N", scale=channel_scale(theme), title=None, legend=alt.Legend(orient="top")),
        order=alt.Order("channel:N"),
        tooltip=[alt.Tooltip("week_start:T", title="Week of", format="%b %d"), alt.Tooltip("channel:N", title="Platform"),
                 alt.Tooltip("spend:Q", title="Spend", format="$,.0f")],
    ).properties(height=height)


# ----------------------------------------------------------------------------- electorate
def registered_vs_voted(pt: pd.DataFrame, theme: str, height: int = 220) -> alt.Chart:
    """Per party: registered voters in 2022 (light bar) with 2022 midterm voters inside it (solid bar)."""
    d = pt[pt["party"].isin(PARTIES[:3])].copy()
    d["party"] = d["party"].astype(str)
    d["turnout_lbl"] = d["turnout22"].map(lambda x: f"{x:.0%} voted in 2022")
    base = alt.Chart(d).encode(y=alt.Y("party:N", sort=PARTIES, title=None))
    reg = base.mark_bar(opacity=0.28, cornerRadiusEnd=4, height={"band": 0.72}).encode(
        x=alt.X("reg22:Q", title=None, axis=alt.Axis(format="~s")),
        color=alt.Color("party:N", scale=party_scale(theme), legend=None),
        tooltip=[alt.Tooltip("party:N", title="Party"), alt.Tooltip("reg22:Q", title="Registered (2022)", format=","),
                 alt.Tooltip("voted22:Q", title="Voted in 2022", format=","),
                 alt.Tooltip("turnout22:Q", title="2022 turnout", format=".0%")])
    voted = base.mark_bar(cornerRadiusEnd=4, height={"band": 0.72}).encode(
        x="voted22:Q", color=alt.Color("party:N", scale=party_scale(theme), legend=None),
        tooltip=[alt.Tooltip("party:N", title="Party"), alt.Tooltip("voted22:Q", title="Voted in 2022", format=","),
                 alt.Tooltip("turnout22:Q", title="2022 turnout", format=".0%")])
    lbl = base.mark_text(align="left", dx=6, fontSize=11, color=get_tokens(theme)["text_secondary"]).encode(
        x="reg22:Q", text="turnout_lbl:N")
    return (reg + voted + lbl).properties(height=height)


def party_mix(df: pd.DataFrame, group_order: list[str], theme: str, height: int | None = None) -> alt.Chart:
    """100% stacked bar per demographic group: party share of registered voters."""
    d = df.groupby(["group", "party"], as_index=False)["reg24"].sum()
    d["total"] = d.groupby("group")["reg24"].transform("sum")
    d = d[d["total"] > 0]
    d["share"] = d["reg24"] / d["total"]
    d["order"] = d["party"].map({p: i for i, p in enumerate(PARTIES)})
    order = [g for g in group_order if g in set(d["group"])]
    d["ylab"] = d["group"] + "  ·  " + d["total"].map(lambda x: f"{x / 1e3:,.0f}K" if x >= 1e3 else f"{x:,.0f}")
    ylab_order = [d[d["group"] == g]["ylab"].iloc[0] for g in order]
    return alt.Chart(d).mark_bar(height={"band": 0.7}).encode(
        y=alt.Y("ylab:N", sort=ylab_order, title=None, axis=alt.Axis(labelLimit=240)),
        x=alt.X("share:Q", stack="normalize", title=None, axis=alt.Axis(format=".0%")),
        color=alt.Color("party:N", scale=party_scale(theme), title=None, legend=alt.Legend(orient="top")),
        order=alt.Order("order:Q"),
        tooltip=[alt.Tooltip("group:N", title="Group"), alt.Tooltip("party:N", title="Party"),
                 alt.Tooltip("share:Q", title="Share of group", format=".0%"),
                 alt.Tooltip("reg24:Q", title="Registered voters", format=",")],
    ).properties(height=height or LEGEND_PX + max(110, 38 * len(order)))


def turnout_gap(df: pd.DataFrame, group_order: list[str], theme: str, height: int | None = None) -> alt.Chart:
    """Dumbbell per group: 2022 turnout of registered Dems vs registered Reps."""
    t = get_tokens(theme)
    d = df[df["party"].isin(["Dem", "Rep"])].groupby(["group", "party"], as_index=False)[["reg22", "voted22"]].sum()
    d = d[d["reg22"] >= 200]
    d["turnout"] = d["voted22"] / d["reg22"]
    d["skipped"] = d["reg22"] - d["voted22"]
    order = [g for g in group_order if g in set(d["group"])]
    base = alt.Chart(d).encode(y=alt.Y("group:N", sort=order, title=None, axis=alt.Axis(labelLimit=200)))
    rng = base.mark_rule(strokeWidth=3, color=t["border"]).encode(
        x=alt.X("min(turnout):Q", title="Voted in the 2022 midterm", axis=alt.Axis(format=".0%"),
                scale=alt.Scale(zero=False, padding=12)), x2="max(turnout):Q")
    dots = base.mark_circle(size=150, opacity=1).encode(
        x="turnout:Q", color=alt.Color("party:N", scale=alt.Scale(domain=["Dem", "Rep"], range=[t["dem"], t["rep"]]),
                                       title=None, legend=alt.Legend(orient="top")),
        tooltip=[alt.Tooltip("group:N", title="Group"), alt.Tooltip("party:N", title="Registered"),
                 alt.Tooltip("turnout:Q", title="2022 turnout", format=".0%"),
                 alt.Tooltip("skipped:Q", title="Registered but didn't vote", format=",")])
    return (rng + dots).properties(height=height or LEGEND_PX + max(110, 38 * len(order)))


def district_board(df: pd.DataFrame, theme: str, height: int = 430) -> alt.Chart:
    """Per CD: 2024 presidential margin (hollow) -> 2026 House result (solid), with nominees."""
    t = get_tokens(theme)
    d = df.copy()
    d["row"] = d["label"] + "  " + d["dem_candidate"].fillna("") + " vs " + d["rep_candidate"].fillna("")
    order = d.sort_values("dem_margin_pct", ascending=False)["row"].tolist()
    d["won26"] = d["result26_margin_pct"].map(lambda m: "Dem won" if m > 0 else "Rep won")
    tips = [alt.Tooltip("label:N", title="District"), alt.Tooltip("dem_candidate:N", title="Democrat"),
            alt.Tooltip("rep_candidate:N", title="Republican"),
            alt.Tooltip("dem_margin_pct:Q", title="2024 president margin (D−R)", format="+.1f"),
            alt.Tooltip("result26_margin_pct:Q", title="2026 House result (D−R)", format="+.1f"),
            alt.Tooltip("holder_2024:N", title="Held after 2024")]
    m = max(20.0, float(d[["dem_margin_pct", "result26_margin_pct"]].abs().max().max()) + 3)
    base = alt.Chart(d).encode(y=alt.Y("row:N", sort=order, title=None, axis=alt.Axis(labelLimit=330)))
    x = alt.X("dem_margin_pct:Q", title="Margin, points (left = Republican, right = Democrat)",
              scale=alt.Scale(domain=[-m, m]))
    zero = alt.Chart(pd.DataFrame({"x": [0]})).mark_rule(color=t["text_muted"], strokeDash=[4, 3]).encode(x="x:Q")
    band = alt.Chart(pd.DataFrame({"a": [-5], "b": [5]})).mark_rect(color=t["swing"], opacity=0.08).encode(x="a:Q", x2="b:Q")
    link = base.mark_rule(strokeWidth=2, color=t["border"]).encode(x=x, x2="result26_margin_pct:Q")
    pres = base.mark_point(size=90, filled=False, strokeWidth=2, color=t["text_secondary"]).encode(x=x, tooltip=tips)
    res = base.mark_circle(size=120, opacity=1).encode(
        x="result26_margin_pct:Q",
        color=alt.Color("won26:N", scale=alt.Scale(domain=["Dem won", "Rep won"], range=[t["dem"], t["rep"]]),
                        title="2026 House result", legend=alt.Legend(orient="top")),
        tooltip=tips)
    return (band + zero + link + pres + res).properties(height=height)


def theme_compare(df: pd.DataFrame, theme: str, top: int = 8) -> alt.Chart:
    keep = df.groupby("theme")["share"].max().sort_values(ascending=False).head(top).index.tolist()
    d = df[df["theme"].isin(keep)]
    return side_pair_bars(d, "theme", "share", theme, order=keep)


def age_reach(df: pd.DataFrame, theme: str) -> alt.Chart:
    d = df[df["age"].isin(["18-24", "25-34", "35-44", "45-54", "55-64", "65+"])]
    d = d.groupby(["side_group", "age"], as_index=False)["share"].sum()
    d = _sides(d)
    return alt.Chart(d).mark_bar(cornerRadiusTopLeft=3, cornerRadiusTopRight=3).encode(
        x=alt.X("age:N", title="Age of people reached", sort=["18-24", "25-34", "35-44", "45-54", "55-64", "65+"]),
        xOffset=alt.XOffset("side:N", sort=[SIDE_LABELS[s] for s in SIDES]),
        y=alt.Y("share:Q", title="Share of impressions", axis=alt.Axis(format=".0%")),
        color=alt.Color("side:N", scale=side_scale(theme), title=None, legend=alt.Legend(orient="top")),
        tooltip=[alt.Tooltip("age:N", title="Age"), alt.Tooltip("side:N", title="Side"),
                 alt.Tooltip("share:Q", title="Share of impressions", format=".0%")],
    ).properties(height=260)


# ----------------------------------------------------------------------------- war room
def win_chance_bar(base: float, plan: float, lo: float, hi: float, theme: str, label: str = "Win chance") -> alt.Chart:
    """0-100% track: shaded plan range, hollow tick = no extra spend, solid dot = with the plan."""
    t = get_tokens(theme)
    track = alt.Chart(pd.DataFrame({"a": [0.0], "b": [1.0]})).mark_bar(height=14, color=t["border"], opacity=0.5,
                                                                         cornerRadius=7).encode(
        x=alt.X("a:Q", scale=alt.Scale(domain=[0, 1]), axis=alt.Axis(format=".0%", values=[0, .25, .5, .75, 1],
                                                                       title=None, grid=False)), x2="b:Q")
    rng = alt.Chart(pd.DataFrame({"a": [lo], "b": [hi]})).mark_bar(height=14, color=t["dem"], opacity=0.35,
                                                                   cornerRadius=7).encode(
        x="a:Q", x2="b:Q", tooltip=[alt.Tooltip("a:Q", title="Low end", format=".0%"),
                                    alt.Tooltip("b:Q", title="High end", format=".0%")])
    half = alt.Chart(pd.DataFrame({"x": [0.5]})).mark_rule(color=t["text_muted"], strokeDash=[3, 3]).encode(x="x:Q")
    pts = pd.DataFrame({"x": [base, plan], "what": ["Without new spend", "With this plan"]})
    b = alt.Chart(pts[pts["what"] == "Without new spend"]).mark_point(size=180, shape="diamond", filled=False,
                                                                      strokeWidth=2, color=t["text_secondary"]).encode(
        x="x:Q", tooltip=[alt.Tooltip("what:N", title=" "), alt.Tooltip("x:Q", title=label, format=".1%")])
    p = alt.Chart(pts[pts["what"] == "With this plan"]).mark_circle(size=220, opacity=1, color=t["dem"]).encode(
        x="x:Q", tooltip=[alt.Tooltip("what:N", title=" "), alt.Tooltip("x:Q", title=label, format=".1%")])
    return (track + rng + half + b + p).properties(height=60)


def outcome_dist(hist: pd.DataFrame, theme: str, threshold: float, x_title: str, seats: bool = False) -> alt.Chart:
    """Baseline (grey outline) vs plan (filled, blue = win side / red = loss side) outcome distribution."""
    t = get_tokens(theme)
    h = hist.copy()
    h["mid"] = (h["bin_start"] + h["bin_end"]) / 2
    tot = h.groupby("series")["count"].transform("sum")
    h["share"] = h["count"] / tot.replace(0, 1)
    h["side"] = np.where(h["mid"] > threshold, "We win", "We lose")
    fmt = "d" if seats else "~s"
    x = alt.X("bin_start:Q", title=x_title, axis=alt.Axis(format=fmt, **({"tickMinStep": 1} if seats else {})),
              bin="binned")
    plan = alt.Chart(h[h["series"] == "With plan"]).mark_bar(opacity=0.85, binSpacing=1).encode(
        x=x, x2="bin_end:Q", y=alt.Y("share:Q", title="Share of simulations", axis=alt.Axis(format=".0%")),
        color=alt.Color("side:N", scale=alt.Scale(domain=["We win", "We lose"], range=[t["dem"], t["rep"]]),
                        title="With this plan", legend=alt.Legend(orient="top")),
        tooltip=[alt.Tooltip("bin_start:Q", title="From", format=",.0f"), alt.Tooltip("bin_end:Q", title="To", format=",.0f"),
                 alt.Tooltip("share:Q", title="Share of simulations", format=".1%")])
    base = alt.Chart(h[h["series"] != "With plan"]).mark_line(interpolate="step", color=t["text_secondary"],
                                                              strokeDash=[4, 3], strokeWidth=1.5).encode(
        x=alt.X("mid:Q"), y="share:Q")
    rule = alt.Chart(pd.DataFrame({"x": [threshold]})).mark_rule(color=t["text_primary"], strokeWidth=1.5).encode(x="x:Q")
    return (plan + base + rule).properties(height=230)


def net_votes_bars(df: pd.DataFrame, theme: str, height: int | None = None) -> alt.Chart:
    """Expected net votes gained per region, with the 10-90% range as a whisker."""
    t = get_tokens(theme)
    d = df.sort_values("delta_votes", ascending=False)
    order = d["label"].tolist()
    base = alt.Chart(d).encode(y=alt.Y("label:N", sort=order, title=None, axis=alt.Axis(labelLimit=180)))
    bars = base.mark_bar(color=t["dem"], cornerRadiusEnd=3, height={"band": 0.65}).encode(
        x=alt.X("delta_votes:Q", title="Net votes gained", axis=alt.Axis(format="~s")),
        tooltip=[alt.Tooltip("label:N", title="Region"), alt.Tooltip("budget:Q", title="Budget", format="$,.0f"),
                 alt.Tooltip("delta_votes:Q", title="Net votes (expected)", format=",.0f"),
                 alt.Tooltip("delta_low:Q", title="Low end", format=",.0f"),
                 alt.Tooltip("delta_high:Q", title="High end", format=",.0f")])
    whisk = base.mark_rule(color=t["text_secondary"]).encode(x="delta_low:Q", x2="delta_high:Q")
    return (bars + whisk).properties(height=height or max(120, 28 * len(d)))


def reveal_board(df: pd.DataFrame, theme: str, height: int | None = None) -> alt.Chart:
    """Per region: 2024 start (grey tick) -> our projection (hollow) -> actual 2026 result (solid)."""
    t = get_tokens(theme)
    d = df.copy()
    d["won"] = np.where(d["actual_pct"] > 0, "We won", "We lost")
    order = d.sort_values("actual_pct", ascending=False)["label"].tolist()
    m = max(15.0, float(d[["start_pct", "proj_pct", "actual_pct"]].abs().max().max()) + 3)
    x = alt.X("proj_pct:Q", title="Margin, points (left = Republican, right = Democrat)", scale=alt.Scale(domain=[-m, m]))
    tips = [alt.Tooltip("label:N", title="Region"), alt.Tooltip("start_pct:Q", title="2024 start", format="+.1f"),
            alt.Tooltip("proj_pct:Q", title="Projected with plan", format="+.1f"),
            alt.Tooltip("actual_pct:Q", title="Actual 2026", format="+.1f"),
            alt.Tooltip("budget:Q", title="Plan money", format="$,.0f")]
    base = alt.Chart(d).encode(y=alt.Y("label:N", sort=order, title=None, axis=alt.Axis(labelLimit=180)))
    zero = alt.Chart(pd.DataFrame({"x": [0]})).mark_rule(color=t["text_muted"], strokeDash=[4, 3]).encode(x="x:Q")
    link = base.mark_rule(strokeWidth=2, color=t["border"]).encode(x=x, x2="actual_pct:Q")
    start = base.mark_tick(thickness=2, size=14, color=t["text_muted"]).encode(x="start_pct:Q", tooltip=tips)
    proj = base.mark_point(size=90, filled=False, strokeWidth=2, color=t["text_secondary"]).encode(x=x, tooltip=tips)
    act = base.mark_circle(size=130, opacity=1).encode(
        x="actual_pct:Q", color=alt.Color("won:N", scale=alt.Scale(domain=["We won", "We lost"], range=[t["dem"], t["rep"]]),
                                          title="Actual 2026", legend=alt.Legend(orient="top")), tooltip=tips)
    return (zero + link + start + proj + act).properties(height=height or LEGEND_PX + max(140, 30 * len(d)))


def plan_weeks(df: pd.DataFrame, order: list[str], theme: str, height: int = 200) -> alt.Chart:
    """Planned spend per week (stacked by platform), weeks as labelled columns."""
    return alt.Chart(df).mark_bar(cornerRadiusTopLeft=2, cornerRadiusTopRight=2).encode(
        x=alt.X("week:O", sort=order, title="Week of", axis=alt.Axis(labelAngle=0)),
        y=alt.Y("dollars:Q", title="Planned spend", axis=alt.Axis(format="$~s")),
        color=alt.Color("channel:N", scale=channel_scale(theme), title=None, legend=alt.Legend(orient="top")),
        order=alt.Order("channel:N"),
        tooltip=[alt.Tooltip("week:O", title="Week of"), alt.Tooltip("channel:N", title="Platform"),
                 alt.Tooltip("dollars:Q", title="Planned", format="$,.0f")],
    ).properties(height=height)
